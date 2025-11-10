#!/usr/bin/env python3
"""Convert PDFs to Markdown using the Mistral Document AI OCR service."""

from __future__ import annotations

import argparse
import base64
import difflib
import json
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Optional, Sequence

from mistralai import Mistral
from dotenv import load_dotenv
from openai import OpenAI


try:  # Optional import used for retry logic.
    import httpx
except ImportError:  # pragma: no cover - optional dependency
    httpx = None  # type: ignore[assignment]

try:  # Additional OpenAI exception types for better error handling.
    from openai import (  # type: ignore[import]
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        RateLimitError,
    )
except ImportError:  # pragma: no cover - optional dependency
    APIConnectionError = APIStatusError = APITimeoutError = AuthenticationError = RateLimitError = None  # type: ignore[assignment]
try:  # pragma: no cover - allow running from repository root or scripts folder
    from scripts._shared import iter_pdfs, normalize_toc_markdown, setup_logging
except ModuleNotFoundError:  # pragma: no cover
    from _shared import iter_pdfs, normalize_toc_markdown, setup_logging

LOGGER = logging.getLogger(__name__)

# Default vision model for page refinement
VISION_LLM = "anthropic/claude-haiku-4.5"


class VisionRefinementError(RuntimeError):
    """Raised when the vision refinement step fails and should abort the pipeline."""


def _extract_attr(
    entry: object, name: str, default: Optional[object] = None
) -> Optional[object]:
    if isinstance(entry, dict):
        return entry.get(name, default)
    return getattr(entry, name, default)


def _ensure_client(api_key: Optional[str] = None) -> Mistral:
    key = api_key or os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing Mistral API key. Provide --api-key or set the MISTRAL_API_KEY environment variable."
        )
    return Mistral(api_key=key)


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


def _ensure_vision_client(
    api_key: Optional[str] = None,
    *,
    base_url: Optional[str] = None,
) -> OpenAI:
    if OpenAI is None:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Missing optional dependency 'openai'. Install it to enable the vision refinement step."
        )

    key = (
        api_key
        or os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not key:
        raise RuntimeError(
            "Missing OpenRouter/OpenAI API key. Provide --vision-api-key or set OPENROUTER_API_KEY / OPENAI_API_KEY."
        )

    resolved_base_url = (
        base_url or os.environ.get("OPENAI_BASE_URL") or "https://openrouter.ai/api/v1"
    )

    # Set HTTP-Referer for OpenRouter (required for their API)
    default_headers = {
        "HTTP-Referer": "https://github.com/docling/pdf-ocr-refinement",
    }

    return OpenAI(  # type: ignore[return-value]
        api_key=key,
        base_url=resolved_base_url,
        default_headers=default_headers,
    )


def _render_unified_diff(before: str, after: str) -> str:
    diff_lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before.md",
        tofile="after.md",
        lineterm="",
    )
    return "\n".join(diff_lines)


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
        f"Give special attention to content that spans across {page_label}."
    )


def _refine_page_group_with_vision(  # noqa: PLR0912
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
        LOGGER.debug(
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
                LOGGER.warning(
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
            raise VisionRefinementError(
                f"Vision refinement failed for pages {page_label} with no response."
            )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            LOGGER.warning(
                "Vision model response for pages %s did not invoke a tool; skipping further refinement.",
                page_label,
            )
            break

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                LOGGER.warning(
                    "Unable to decode arguments for tool call %s on pages %s.",
                    tool_name,
                    page_label,
                )
                continue

            if tool_name == "apply_page_group_edits":
                updated_pages = arguments.get("updated_pages")
                if not isinstance(updated_pages, list):
                    LOGGER.warning(
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
                    updated_markdown = entry.get("updated_markdown")
                    if not isinstance(page_number, int) or not isinstance(
                        updated_markdown, str
                    ):
                        LOGGER.warning(
                            "Vision model returned invalid update entry for pages %s.",
                            page_label,
                        )
                        continue
                    target_idx = number_to_index.get(page_number)
                    if target_idx is None:
                        LOGGER.warning(
                            "Vision model referenced unknown page number %s (pages %s).",
                            page_number,
                            page_label,
                        )
                        continue
                    previous_markdown = current_markdowns[target_idx]
                    diff_text = _render_unified_diff(
                        previous_markdown, updated_markdown
                    )
                    diff_path = None
                    if diff_text:
                        diff_path = (
                            output_dir
                            / f"page-{page_number:04d}-round-{round_index}.diff"
                        )
                        diff_path.write_text(diff_text, encoding="utf-8")
                    LOGGER.debug(
                        "Applied vision refinement round %d for page %d. Diff saved to %s",
                        round_index,
                        page_number,
                        diff_path or "N/A",
                    )
                    current_markdowns[target_idx] = updated_markdown

            elif tool_name == "approve_page_group":
                LOGGER.debug(
                    "Vision model approved pages %s after %d round(s).",
                    page_label,
                    round_index,
                )
                return current_markdowns
            else:
                LOGGER.debug("Unhandled tool %s for pages %s.", tool_name, page_label)

    LOGGER.info(
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


def _request_mistral_ocr(
    client: Mistral,
    *,
    document_payload: dict[str, object],
    include_images: bool,
    max_attempts: int = 3,
    base_delay: float = 2.0,
) -> object:
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.ocr.process(
                model="mistral-ocr-latest",
                document=document_payload,
                include_image_base64=include_images,
            )
        except Exception as exc:  # pragma: no cover - defensive
            last_error = exc
            if attempt >= max_attempts or not _is_retryable_ocr_error(exc):
                raise
            wait = base_delay * attempt
            LOGGER.warning(
                "Mistral OCR request failed (%s). Retrying in %.1f seconds (%d/%d).",
                exc.__class__.__name__,
                wait,
                attempt,
                max_attempts,
            )
            time.sleep(wait)
    if last_error:  # pragma: no cover - defensive
        raise last_error
    raise RuntimeError("Unexpected OCR retry loop termination.")


def _process_pdf_chunk(
    *,
    local_page_index: int,
    chunk_path: Path,
    client: Mistral,
    include_images: bool,
) -> tuple[int, object, list[dict[str, Optional[object]]]]:
    """Process a single PDF chunk and return (page_index, response, normalized_pages)."""
    document_payload = {
        "type": "document_url",
        "document_url": _encode_pdf(chunk_path),
    }
    chunk_response = _request_mistral_ocr(
        client,
        document_payload=document_payload,
        include_images=include_images,
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
    if not pages:
        return

    batch: list[tuple[int, dict[str, Optional[object]]]] = []
    total_pages = len(pages)
    for idx, page in enumerate(pages):
        page_number = idx + 1
        batch.append((page_number, page))
        is_last = idx == total_pages - 1
        if len(batch) < 2 and not is_last:
            continue

        page_numbers = [entry[0] for entry in batch]
        original_markdowns = [
            (_extract_attr(entry[1], "markdown", "") or "") for entry in batch
        ]
        images_b64 = [_extract_attr(entry[1], "image_base64") for entry in batch]
        if not any(markdown.strip() for markdown in original_markdowns):
            batch.clear()
            continue

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

        if len(updated_markdowns) != len(batch):
            LOGGER.warning(
                "Vision refinement returned %d page(s) for group %s; expected %d.",
                len(updated_markdowns),
                page_numbers,
                len(batch),
            )

        for (page_number, page_entry), updated_markdown in zip(
            batch, updated_markdowns
        ):
            if isinstance(page_entry, dict):
                page_entry["markdown"] = updated_markdown
            else:  # pragma: no cover - fallback for unexpected objects
                try:
                    setattr(page_entry, "markdown", updated_markdown)
                except Exception:  # pragma: no cover - defensive
                    LOGGER.debug(
                        "Unable to assign updated markdown for page %d (non-dict entry).",
                        page_number,
                    )
        batch.clear()


def pdf_to_markdown_mistral(
    pdf_path: Path,
    output_root: Path,
    *,
    client: Optional[Mistral] = None,
    include_images: bool = True,
    save_response: bool = False,
    save_page_markdown: bool = True,
    vision_client: Optional[OpenAI] = None,
    vision_model: Optional[str] = None,
    vision_max_rounds: int = 3,
    vision_temperature: float = 0.0,
    vision_max_attempts: int = 3,
    vision_retry_base_delay: float = 2.0,
    max_upload_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Perform OCR with Mistral and persist Markdown (and optional page images)."""
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_root = output_root.resolve()
    document_dir = output_root / pdf_path.stem
    document_dir.mkdir(parents=True, exist_ok=True)
    images_dir = document_dir / "images"
    if include_images:
        images_dir.mkdir(exist_ok=True)

    mistral_client = client or _ensure_client()
    pdf_size_bytes = pdf_path.stat().st_size
    requires_split = _should_split_document(pdf_path, max_upload_bytes)
    aggregated_pages: list[dict[str, Optional[object]]] = []
    persistence_payload: object

    if not requires_split:
        LOGGER.debug("Submitting %s to Mistral OCR.", pdf_path)
        document_payload = {
            "type": "document_url",
            "document_url": _encode_pdf(pdf_path),
        }
        response = _request_mistral_ocr(
            mistral_client,
            document_payload=document_payload,
            include_images=include_images,
        )
        pages: Sequence[object] = _extract_attr(response, "pages", [])  # type: ignore[arg-type]
        if isinstance(response, dict):
            pages = response.get("pages", [])
        aggregated_pages.extend(_normalise_page_entry(page) for page in pages)
        persistence_payload = response
    else:
        LOGGER.info(
            "PDF %s size %d bytes exceeds max upload threshold (%d). Splitting into per-page OCR requests.",
            pdf_path.name,
            pdf_size_bytes,
            max_upload_bytes,
        )
        chunk_metadata: list[dict[str, object]] = []
        with _prepare_pdf_page_chunks(pdf_path) as page_chunks:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(
                        _process_pdf_chunk,
                        local_page_index=local_page_index,
                        chunk_path=chunk_path,
                        client=mistral_client,
                        include_images=include_images,
                    ): (local_page_index, chunk_path)
                    for local_page_index, chunk_path in page_chunks
                }

                for future in as_completed(futures):
                    local_page_index, chunk_path = futures[future]
                    try:
                        _, chunk_response, normalised_pages = future.result()
                    except Exception as exc:  # pragma: no cover - defensive
                        LOGGER.exception(
                            "Error processing chunk %s (page %d) for %s: %s",
                            chunk_path.name,
                            local_page_index + 1,
                            pdf_path.name,
                            exc,
                        )
                        continue

                    if not normalised_pages:
                        LOGGER.warning(
                            "Empty OCR result returned for %s page %d while splitting.",
                            pdf_path.name,
                            local_page_index + 1,
                        )
                    aggregated_pages.extend(normalised_pages)
                    chunk_metadata.append(
                        {
                            "page_number": local_page_index + 1,
                            "pages": normalised_pages,
                        }
                    )
        persistence_payload = {
            "mode": "split_per_page",
            "chunks": chunk_metadata,
            "pages": aggregated_pages,
        }

    pages = aggregated_pages
    markdown_chunks: list[str] = []
    vision_diff_dir = document_dir / "vision_diffs"

    if vision_client and vision_model:
        try:
            _apply_pairwise_vision_refinement(
                pages,
                client=vision_client,
                model=vision_model,
                output_dir=vision_diff_dir,
                max_rounds=vision_max_rounds,
                temperature=vision_temperature,
                max_attempts=vision_max_attempts,
                retry_base_delay=vision_retry_base_delay,
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("Vision refinement failed for %s: %s", pdf_path.name, exc)
            raise

    for idx, page in enumerate(pages):
        page_markdown = _extract_attr(page, "markdown", "") or ""
        if not page_markdown.strip():
            LOGGER.warning(
                "Empty markdown returned for %s page %d", pdf_path.name, idx + 1
            )
        page_index = idx + 1

        image_b64 = None
        if include_images:
            image_b64 = _extract_attr(page, "image_base64")

        markdown_chunks.append(page_markdown)

        if save_page_markdown:
            page_markdown_path = document_dir / f"page-{page_index:04d}.md"
            page_markdown_path.write_text(page_markdown, encoding="utf-8")
            LOGGER.debug("Wrote per-page markdown: %s", page_markdown_path.name)

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

    final_markdown = "\n\n---\n\n".join(
        chunk.strip() for chunk in markdown_chunks
    ).strip()
    final_markdown = normalize_toc_markdown(final_markdown) if final_markdown else ""

    markdown_path = document_dir / "combined_markdown.md"
    markdown_path.write_text(final_markdown, encoding="utf-8")
    LOGGER.info("Wrote Markdown to %s", markdown_path)

    if save_response:
        _persist_response(persistence_payload, document_dir)

    return markdown_path


def _resolve_inputs(
    input_path: Path, pattern: str, excluded_dirs: Iterable[str]
) -> list[Path]:
    excluded = {entry.lower() for entry in excluded_dirs}
    if input_path.is_file():
        return [input_path]
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    pdfs: list[Path] = []
    for pdf in iter_pdfs(input_path, pattern):
        try:
            relative_parts = pdf.relative_to(input_path).parts
        except ValueError:
            relative_parts = pdf.parts
        if any(part.lower() in excluded for part in relative_parts):
            LOGGER.debug("Skipping %s (excluded directory)", pdf)
            continue
        pdfs.append(pdf)
    return pdfs


def main(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)

    input_path = Path(args.input).expanduser()
    output_root = Path(args.output_dir).expanduser()

    try:
        pdfs = _resolve_inputs(input_path, args.pattern, args.exclude_subdir or [])
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 1

    if not pdfs:
        LOGGER.warning("No PDF files found for conversion.")
        return 1

    try:
        client = _ensure_client(args.api_key)
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1

    vision_client = None
    vision_model = args.vision_model
    if vision_model:
        try:
            vision_client = _ensure_vision_client()
        except RuntimeError as exc:
            LOGGER.error("Failed to initialise vision refinement client: %s", exc)
            return 1

    # Use hardcoded defaults for vision refinement parameters
    vision_max_rounds = 3
    vision_max_attempts = 3
    vision_retry_delay = 2.0
    vision_temperature = 0.1

    successes = 0
    LOGGER.info("Found %d PDF(s) to process.", len(pdfs))
    for pdf in pdfs:
        LOGGER.info("Processing %s", pdf)
        try:
            pdf_to_markdown_mistral(
                pdf,
                output_root,
                client=client,
                include_images=not args.no_images,
                save_response=args.save_response,
                save_page_markdown=True,
                vision_client=vision_client,
                vision_model=vision_model,
                vision_max_rounds=vision_max_rounds,
                vision_temperature=vision_temperature,
                vision_max_attempts=vision_max_attempts,
                vision_retry_base_delay=vision_retry_delay,
                max_upload_bytes=args.max_upload_bytes,
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("Failed to convert %s: %s", pdf, exc)
        else:
            successes += 1

    LOGGER.info("Completed %d/%d conversions.", successes, len(pdfs))
    return 0 if successes else 2


if __name__ == "__main__":  # pragma: no cover
    # Load environment variables first
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Convert PDFs to Markdown using Mistral OCR.",
    )
    parser.add_argument(
        "input",
        help="Path to a PDF file or a directory containing PDFs.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("output") / "mistral_OCR"),
        help="Directory where conversion artefacts will be written.",
    )
    parser.add_argument(
        "--pattern",
        default="*.pdf",
        help="Glob pattern to select PDFs when input is a directory.",
    )
    parser.add_argument(
        "--exclude-subdir",
        action="append",
        default=["old"],
        help="Directory name to skip when discovering PDFs (can be used multiple times).",
    )
    parser.add_argument(
        "--api-key",
        help="Mistral API key. Defaults to the MISTRAL_API_KEY environment variable.",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip saving page images returned by the OCR service.",
    )
    parser.add_argument(
        "--save-response",
        action="store_true",
        help="Persist the raw OCR response JSON alongside the Markdown output.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    parser.add_argument(
        "--vision-model",
        default=VISION_LLM,
        help=f"Vision model identifier (OpenRouter/OpenAI). Enables the refinement step when provided (default: {VISION_LLM}).",
    )
    parser.add_argument(
        "--max-upload-bytes",
        type=int,
        default=int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        help="Maximum PDF size (bytes) to send in a single OCR request before splitting per page (default: 10485760). "
        "Smaller values reduce per-request payload and enable parallel processing (up to 3 requests).",
    )
    args = parser.parse_args()
    raise SystemExit(main(args))
