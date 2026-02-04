from pathlib import Path
from typing import Optional, Sequence
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from pdf2markdown.utils.clients import create_mistral_client, create_vision_client
import logging
import base64
from pdf2markdown.utils.markdown_utils import normalize_toc_markdown
from mistralai import Mistral
import time
import httpx
import json

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
import difflib
import re
import tempfile

logger = logging.getLogger(__name__)


class VisionRefinementError(RuntimeError):
    """Raised when the vision refinement step fails and should abort the pipeline."""


def _extract_attr(
    entry: object, name: str, default: Optional[object] = None
) -> Optional[object]:
    if isinstance(entry, dict):
        return entry.get(name, default)
    return getattr(entry, name, default)


def _encode_pdf(pdf_path: Path) -> str:
    data = pdf_path.read_bytes()
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:application/pdf;base64,{encoded}"


def _persist_response(content: object, target_dir: Path) -> None:
    json_path = target_dir / "mistral_response.json"
    try:
        json_payload = json.dumps(content, indent=2)
    except TypeError:
        if hasattr(content, "model_dump"):
            json_payload = json.dumps(content.model_dump(), indent=2)  # type: ignore[attr-defined]
        elif hasattr(content, "to_dict"):
            json_payload = json.dumps(content.to_dict(), indent=2)  # type: ignore[attr-defined]
        else:
            raise RuntimeError("Unable to serialise Mistral OCR response to JSON.")
    json_path.write_text(json_payload, encoding="utf-8")


def _render_unified_diff(before: str, after: str) -> str:
    diff_lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before.md",
        tofile="after.md",
        lineterm="",
    )
    return "\n".join(diff_lines)


def _sanitize_markdown_from_tool(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # Normalize platform newlines
    sanitized = text.replace("\r\n", "\n")
    # Convert literal escape sequences produced by the tool into actual characters
    sanitized = (
        sanitized.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
    )
    # Collapse excessive blank lines
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized


def _should_split_document(pdf_path: Path, max_upload_bytes: int) -> bool:
    return max_upload_bytes > 0 and pdf_path.stat().st_size > max_upload_bytes


def _prepare_pdf_page_chunks(pdf_path: Path):
    """
    Context manager that creates temporary PDF files for each page.
    Yields a list of (page_index, chunk_path) tuples.
    The temporary directory is kept alive until the context manager exits.
    """
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Splitting large PDFs requires the 'pypdf' package. "
            "Install it with `pip install pypdf` or increase --max-upload-bytes."
        ) from exc

    class ChunksContextManager:
        def __init__(self, pdf_path: Path):
            self.pdf_path = pdf_path
            self.tmpdir = None
            self.chunks = []

        def __enter__(self):
            self.tmpdir = tempfile.TemporaryDirectory()
            tmpdir_path = Path(self.tmpdir.__enter__())
            reader = PdfReader(str(self.pdf_path))
            for page_index, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                chunk_path = tmpdir_path / f"page-{page_index + 1:04d}.pdf"
                with chunk_path.open("wb") as handle:
                    writer.write(handle)
                self.chunks.append((page_index, chunk_path))
            return self.chunks

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.tmpdir:
                self.tmpdir.__exit__(exc_type, exc_val, exc_tb)
            return False

    return ChunksContextManager(pdf_path)


def _normalise_page_entry(page: object) -> dict[str, Optional[object]]:
    return {
        "markdown": _extract_attr(page, "markdown", "") or "",
        "image_base64": _extract_attr(page, "image_base64"),
        "index": _extract_attr(page, "index"),
    }


def _is_retryable_vision_error(exc: Exception) -> bool:
    if AuthenticationError is not None and isinstance(exc, AuthenticationError):
        return False

    status_code = getattr(exc, "status_code", None)
    if status_code in (401, 403):
        return False

    if RateLimitError is not None and isinstance(exc, RateLimitError):
        return True
    if APIConnectionError is not None and isinstance(exc, APIConnectionError):
        return True
    if APITimeoutError is not None and isinstance(exc, APITimeoutError):
        return True

    if APIStatusError is not None and isinstance(exc, APIStatusError):
        if status_code is None:
            status_code = exc.status_code  # type: ignore[attr-defined]
        if status_code is not None:
            if status_code == 429 or 500 <= status_code < 600:
                return True
            return False

    retryable_types = (TimeoutError, ConnectionError)
    if isinstance(exc, retryable_types):
        return True

    if httpx is not None and isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.RemoteProtocolError,
        ),
    ):
        return True

    return False


def _build_vision_prompt(page_numbers: Sequence[int]) -> str:
    if not page_numbers:
        page_label = "the provided page(s)"
    elif len(page_numbers) == 1:
        page_label = f"page {page_numbers[0]}"
    else:
        joined = ", ".join(str(number) for number in page_numbers)
        page_label = f"pages {joined}"

    return (
        "You are a meticulous layout-aware editor. "
        "Review the provided PDF page images and their current Markdown transcriptions. "
        "Fix OCR mistakes, preserve structure, and capture tables, lists, and headings faithfully. "
        "Use the available tools: call `apply_page_group_edits` to submit improved Markdown when changes "
        "are needed or `approve_page_group` when the transcriptions are correct. "
        f"Give special attention to content that spans across {page_label}. "
        "Do not remove or truncate content that plausibly continues across the page boundary "
        "(e.g., hyphenated words, continued lists, or tables). If uncertain, prefer preserving and continuing "
        "the structure rather than deleting lines. Ensure that table rows and paragraphs that cross page "
        "boundaries remain contiguous and consistent across both pages. "
        "Return Markdown with actual newline characters (no literal \\n sequences)."
    )


def _refine_page_group_with_vision(
    *,
    client: OpenAI,
    model: str,
    page_numbers: Sequence[int],
    original_markdowns: Sequence[str],
    images_b64: Sequence[Optional[str]],
    output_dir: Path,
    max_rounds: int,
    temperature: float,
    max_attempts: int,
    retry_base_delay: float,
) -> list[str]:
    if not original_markdowns:
        return []

    current_markdowns = list(original_markdowns)
    output_dir.mkdir(parents=True, exist_ok=True)
    system_prompt = _build_vision_prompt(page_numbers)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "apply_page_group_edits",
                "description": (
                    "Submit revised Markdown for one or more pages in the current group when changes are required."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "updated_pages": {
                            "type": "array",
                            "description": "List of per-page Markdown updates.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "page_number": {
                                        "type": "integer",
                                        "description": "The page number being updated.",
                                    },
                                    "updated_markdown": {
                                        "type": "string",
                                        "description": "The fully updated Markdown representation for the page.",
                                    },
                                    "notes": {
                                        "type": "string",
                                        "description": "Brief summary of the applied fixes.",
                                    },
                                },
                                "required": ["page_number", "updated_markdown"],
                            },
                        },
                    },
                    "required": ["updated_pages"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "approve_page_group",
                "description": "Call when the Markdown accurately reflects the page content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "justification": {
                            "type": "string",
                            "description": "Explain why no further edits are necessary.",
                        }
                    },
                },
            },
        },
    ]

    for round_index in range(1, max_rounds + 1):
        if not any(markdown.strip() for markdown in current_markdowns):
            return current_markdowns

        page_label = ", ".join(str(number) for number in page_numbers)
        round_t0 = time.perf_counter()
        logger.info(
            "Pages %s round %d: requesting vision refinement", page_label, round_index
        )
        user_content = [
            {
                "type": "text",
                "text": (
                    "You are provided with one or two consecutive PDF page transcriptions. "
                    "Compare them with the corresponding page images and correct any mistakes, "
                    "keeping tables and sentences continuous when they span both pages."
                ),
            }
        ]

        for idx, page_number in enumerate(page_numbers):
            image_b64 = images_b64[idx] if idx < len(images_b64) else None
            if image_b64:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                        },
                    }
                )
            current_markdown = (
                current_markdowns[idx] if idx < len(current_markdowns) else ""
            )
            user_content.append(
                {
                    "type": "text",
                    "text": f"Current Markdown (page {page_number}):\n\n{current_markdown}",
                }
            )

        messages: list[dict[str, object]] = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": user_content},
        ]
        response = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice="required",
                    temperature=temperature,
                )
            except Exception as exc:  # pragma: no cover - defensive
                if not _is_retryable_vision_error(exc) or attempt >= max_attempts:
                    raise VisionRefinementError(
                        f"Vision refinement failed after {attempt} attempt(s) for pages {page_label}."
                    ) from exc
                wait = max(retry_base_delay, 0.0) * attempt
                logger.warning(
                    "Vision refinement request failed (%s) for pages %s. Retrying in %.1f seconds (%d/%d).",
                    exc.__class__.__name__,
                    page_label,
                    wait,
                    attempt,
                    max_attempts,
                )
                time.sleep(wait)
            else:
                break
        if response is None:  # pragma: no cover - defensive
            logger.warning(
                "Vision refinement failed for pages %s with no response; using original markdown.",
                page_label,
            )
            return current_markdowns

        choices = getattr(response, "choices", None)
        if not choices:
            logger.warning(
                "Vision refinement returned no choices for pages %s; using original markdown.",
                page_label,
            )
            return current_markdowns

        assistant_choice = choices[0] if choices else None
        assistant_message = getattr(assistant_choice, "message", None)
        if assistant_message is None:
            logger.warning(
                "Vision refinement returned empty message for pages %s; using original markdown.",
                page_label,
            )
            return current_markdowns

        if not assistant_message.tool_calls:
            logger.warning(
                "Vision model response for pages %s did not invoke a tool; skipping further refinement.",
                page_label,
            )
            break

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                logger.warning(
                    "Unable to decode arguments for tool call %s on pages %s.",
                    tool_name,
                    page_label,
                )
                continue

            if tool_name == "apply_page_group_edits":
                updated_pages = arguments.get("updated_pages")
                if not isinstance(updated_pages, list):
                    logger.warning(
                        "Vision model returned invalid updated_pages payload for pages %s.",
                        page_label,
                    )
                    continue

                number_to_index = {
                    number: idx for idx, number in enumerate(page_numbers)
                }
                for entry in updated_pages:
                    if not isinstance(entry, dict):
                        continue
                    page_number = entry.get("page_number")
                    updated_markdown_raw = entry.get("updated_markdown")
                    if not isinstance(page_number, int) or not isinstance(
                        updated_markdown_raw, str
                    ):
                        logger.warning(
                            "Vision model returned invalid update entry for pages %s.",
                            page_label,
                        )
                        continue
                    sanitized_markdown = _sanitize_markdown_from_tool(
                        updated_markdown_raw
                    )
                    target_idx = number_to_index.get(page_number)
                    if target_idx is None:
                        logger.warning(
                            "Vision model referenced unknown page number %s (pages %s).",
                            page_number,
                            page_label,
                        )
                        continue
                    previous_markdown = current_markdowns[target_idx]
                    diff_text = _render_unified_diff(
                        previous_markdown, sanitized_markdown
                    )
                    diff_path = None
                    if diff_text:
                        # Include the pair context in the filename to avoid overwriting diffs
                        if len(page_numbers) >= 2:
                            pair_label = f"{page_numbers[0]:04d}-{page_numbers[1]:04d}"
                        else:
                            pair_label = f"{page_numbers[0]:04d}"
                        diff_path = output_dir / (
                            f"page-{page_number:04d}-pair-{pair_label}-round-{round_index}.diff"
                        )
                        diff_path.write_text(diff_text, encoding="utf-8")
                    logger.debug(
                        "Applied vision refinement round %d for page %d. Diff saved to %s",
                        round_index,
                        page_number,
                        diff_path or "N/A",
                    )
                    current_markdowns[target_idx] = sanitized_markdown

            elif tool_name == "approve_page_group":
                logger.debug(
                    "Vision model approved pages %s after %d round(s).",
                    page_label,
                    round_index,
                )
                return current_markdowns
            else:
                logger.debug("Unhandled tool %s for pages %s.", tool_name, page_label)

        round_elapsed = time.perf_counter() - round_t0
        logger.info(
            "Vision refinement round %d for pages %s took %.2fs",
            round_index,
            page_label,
            round_elapsed,
        )

    logger.info(
        "Vision refinement reached max rounds (%d) for pages %s without explicit approval.",
        max_rounds,
        ", ".join(str(number) for number in page_numbers),
    )
    return current_markdowns


def _is_retryable_ocr_error(exc: Exception) -> bool:
    retryable_types = (
        TimeoutError,
        ConnectionError,
    )
    if isinstance(exc, retryable_types):
        return True
    if httpx is not None:
        retryable_httpx = (
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.ReadError,  # SSL and network read errors
        )
        if isinstance(exc, retryable_httpx):
            return True
    return False


def _process_pdf_chunk(
    *,
    local_page_index: int,
    chunk_path: Path,
    client: Mistral,
    include_images: bool,
    ocr_model: str,
) -> tuple[int, object, list[dict[str, Optional[object]]]]:
    """Process a single PDF chunk and return (page_index, response, normalized_pages)."""
    document_payload = {
        "type": "document_url",
        "document_url": _encode_pdf(chunk_path),
    }
    t0 = time.perf_counter()
    chunk_response = _request_mistral_ocr(
        client,
        document_payload=document_payload,
        include_images=include_images,
        ocr_model=ocr_model,
    )
    elapsed = time.perf_counter() - t0
    logger.info(
        "OCR chunk for page %d took %.2fs",
        local_page_index + 1,
        elapsed,
    )
    chunk_pages: Sequence[object] = _extract_attr(chunk_response, "pages", [])  # type: ignore[arg-type]
    if isinstance(chunk_response, dict):
        chunk_pages = chunk_response.get("pages", [])
    normalised_pages = [_normalise_page_entry(page) for page in chunk_pages]
    return local_page_index, chunk_response, normalised_pages


def _apply_pairwise_vision_refinement(
    pages: Sequence[dict[str, Optional[object]]],
    *,
    client: OpenAI,
    model: str,
    output_dir: Path,
    max_rounds: int,
    temperature: float,
    max_attempts: int,
    retry_base_delay: float,
) -> None:
    if not pages or len(pages) < 2:
        return

    total_pages = len(pages)
    for i in range(total_pages - 1):
        # Sliding window of consecutive pages: [i, i+1] => page numbers [i+1, i+2]
        left_entry = pages[i]
        right_entry = pages[i + 1]
        page_numbers = [i + 1, i + 2]

        original_markdowns = [
            (_extract_attr(left_entry, "markdown", "") or ""),
            (_extract_attr(right_entry, "markdown", "") or ""),
        ]
        images_b64 = [
            _extract_attr(left_entry, "image_base64"),
            _extract_attr(right_entry, "image_base64"),
        ]

        # Skip windows that contain no text content at all
        if not any(markdown.strip() for markdown in original_markdowns):
            continue

        win_t0 = time.perf_counter()
        updated_markdowns = _refine_page_group_with_vision(
            client=client,
            model=model,
            page_numbers=page_numbers,
            original_markdowns=original_markdowns,
            images_b64=images_b64,
            output_dir=output_dir,
            max_rounds=max_rounds,
            temperature=temperature,
            max_attempts=max_attempts,
            retry_base_delay=retry_base_delay,
        )
        logger.info(
            "Vision refinement for pages %s took %.2fs",
            page_numbers,
            time.perf_counter() - win_t0,
        )

        if len(updated_markdowns) != 2:
            logger.warning(
                "Vision refinement returned %d page(s) for window %s; expected 2.",
                len(updated_markdowns),
                page_numbers,
            )

        pair = [
            (page_numbers[0], left_entry),
            (page_numbers[1], right_entry),
        ]
        for (page_number, page_entry), updated_markdown in zip(pair, updated_markdowns):
            if isinstance(page_entry, dict):
                page_entry["markdown"] = updated_markdown
            else:
                try:
                    setattr(page_entry, "markdown", updated_markdown)
                except Exception:
                    logger.debug(
                        "Unable to assign updated markdown for page %d (non-dict entry).",
                        page_number,
                    )


def _request_mistral_ocr(
    client: Mistral,
    *,
    document_payload: dict[str, object],
    include_images: bool,
    ocr_model: str,
    max_attempts: int = 3,
    base_delay: float = 2.0,
) -> object:
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.ocr.process(
                model=ocr_model,
                document=document_payload,
                include_image_base64=include_images,
            )
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts or not _is_retryable_ocr_error(exc):
                raise
            wait = base_delay * attempt
            logger.warning(
                "Mistral OCR request failed (%s). Retrying in %.1f seconds (%d/%d).",
                exc.__class__.__name__,
                wait,
                attempt,
                max_attempts,
            )
            time.sleep(wait)
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected OCR retry loop termination.")


def pdf_to_markdown_pipeline(
    pdf_path: Path,
    output_root: Path,
    *,
    include_images: bool = True,
    ocr_model: str = "mistral-ocr-latest",
    save_response: bool = False,
    save_page_markdown: bool = True,
    vision_model: Optional[str] = None,
    vision_max_rounds: int = 3,
    vision_temperature: float = 0.0,
    vision_max_retries: int = 3,
    vision_retry_base_delay: float = 2.0,
    max_upload_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Perform OCR with Mistral and persist Markdown (and optional page images)."""
    pipeline_t0 = time.perf_counter()
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_root = output_root.resolve()
    timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
    document_dir = output_root / f"{timestamp_prefix}_{pdf_path.stem}"
    document_dir.mkdir(parents=True, exist_ok=True)
    images_dir = document_dir / "images"
    if include_images:
        images_dir.mkdir(exist_ok=True)

    mistral_client = create_mistral_client()
    pdf_size_bytes = pdf_path.stat().st_size
    requires_split = _should_split_document(pdf_path, max_upload_bytes)
    aggregated_pages: list[dict[str, Optional[object]]] = []
    persistence_payload: object

    if not requires_split:
        logger.debug("Submitting %s to Mistral OCR.", pdf_path)
        document_payload = {
            "type": "document_url",
            "document_url": _encode_pdf(pdf_path),
        }
        t_doc_ocr0 = time.perf_counter()
        response = _request_mistral_ocr(
            mistral_client,
            document_payload=document_payload,
            include_images=include_images,
            ocr_model=ocr_model,
        )
        logger.info(
            "OCR (full document) for %s took %.2fs",
            pdf_path.name,
            time.perf_counter() - t_doc_ocr0,
        )
        pages: Sequence[object] = _extract_attr(response, "pages", [])  # type: ignore[arg-type]
        if isinstance(response, dict):
            pages = response.get("pages", [])
        aggregated_pages.extend(_normalise_page_entry(page) for page in pages)
        persistence_payload = response
    else:
        logger.info(
            "PDF %s size %d bytes exceeds max upload threshold (%d). Splitting into per-page OCR requests.",
            pdf_path.name,
            pdf_size_bytes,
            max_upload_bytes,
        )
        chunk_metadata: list[dict[str, object]] = []
        with _prepare_pdf_page_chunks(pdf_path) as page_chunks:
            split_phase_t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(
                        _process_pdf_chunk,
                        local_page_index=local_page_index,
                        chunk_path=chunk_path,
                        client=mistral_client,
                        include_images=include_images,
                        ocr_model=ocr_model,
                    ): (local_page_index, chunk_path)
                    for local_page_index, chunk_path in page_chunks
                }

                # Collect results keyed by original page order to avoid reordering
                per_page_results: dict[int, list[dict[str, Optional[object]]]] = {}
                per_page_metadata: list[dict[str, object]] = []

                for future in as_completed(futures):
                    local_page_index, chunk_path = futures[future]
                    try:
                        _, chunk_response, normalised_pages = future.result()
                    except Exception as exc:
                        logger.exception(
                            "Error processing chunk %s (page %d) for %s: %s",
                            chunk_path.name,
                            local_page_index + 1,
                            pdf_path.name,
                            exc,
                        )
                        continue

                    if not normalised_pages:
                        logger.warning(
                            "Empty OCR result returned for %s page %d while splitting.",
                            pdf_path.name,
                            local_page_index + 1,
                        )
                    per_page_results[local_page_index] = normalised_pages
                    per_page_metadata.append(
                        {
                            "page_number": local_page_index + 1,
                            "pages": normalised_pages,
                        }
                    )

                # Assemble pages in correct order
                for local_page_index in sorted(per_page_results.keys()):
                    aggregated_pages.extend(per_page_results[local_page_index])

                # Keep metadata in sorted page_number order as well
                chunk_metadata = sorted(
                    per_page_metadata, key=lambda m: int(m.get("page_number", 0))
                )
            logger.info(
                "OCR split phase for %s took %.2fs across %d page(s)",
                pdf_path.name,
                time.perf_counter() - split_phase_t0,
                len(per_page_results),
            )
        persistence_payload = {
            "mode": "split_per_page",
            "chunks": chunk_metadata,
            "pages": aggregated_pages,
        }

    pages = aggregated_pages
    markdown_chunks: list[str] = []
    vision_diff_dir = document_dir / "vision_diffs"

    if vision_model:
        try:
            vision_client = create_vision_client()
            _apply_pairwise_vision_refinement(
                pages,
                client=vision_client,
                model=vision_model,
                output_dir=vision_diff_dir,
                max_rounds=vision_max_rounds,
                temperature=vision_temperature,
                max_attempts=vision_max_retries,
                retry_base_delay=vision_retry_base_delay,
            )
        except Exception as exc:
            logger.exception("Vision refinement failed for %s: %s", pdf_path.name, exc)
            raise

    for idx, page in enumerate(pages):
        page_markdown = _extract_attr(page, "markdown", "") or ""
        if not page_markdown.strip():
            logger.warning(
                "Empty markdown returned for %s page %d", pdf_path.name, idx + 1
            )
        page_index = idx + 1

        image_b64 = None
        if include_images:
            image_b64 = _extract_attr(page, "image_base64")

        markdown_chunks.append(page_markdown)

        if save_page_markdown:
            pages_dir = document_dir / "pages"
            pages_dir.mkdir(exist_ok=True)
            page_markdown_path = pages_dir / f"page-{page_index:04d}.md"
            page_markdown_path.write_text(page_markdown, encoding="utf-8")
            logger.debug("Wrote per-page markdown: %s", page_markdown_path.name)

        if not include_images:
            continue

        if not image_b64:
            continue

        raw_page_index = _extract_attr(page, "index")
        if isinstance(raw_page_index, int):
            file_index = raw_page_index + 1
        else:
            file_index = page_index
        image_bytes = base64.b64decode(image_b64)
        image_path = images_dir / f"page-{file_index:04d}.jpeg"
        image_path.write_bytes(image_bytes)

    # Join pages into a single markdown file with a single newline between pages.
    final_markdown = "\n".join(
        (chunk or "").strip() for chunk in markdown_chunks
    ).strip()

    final_markdown = normalize_toc_markdown(final_markdown) if final_markdown else ""

    # Name the combined markdown file after the PDF stem (city name)
    markdown_path = document_dir / f"{pdf_path.stem}.md"
    markdown_path.write_text(final_markdown, encoding="utf-8")
    logger.info("Wrote Markdown to %s", markdown_path)

    if save_response:
        _persist_response(persistence_payload, document_dir)

    # Final summary timing
    total_elapsed = time.perf_counter() - pipeline_t0
    total_pages = len(pages)
    logger.info(
        "Completed %s with %d page(s) in %.2fs",
        pdf_path.name,
        total_pages,
        total_elapsed,
    )

    return markdown_path
