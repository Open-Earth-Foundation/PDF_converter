# PDF Converter Pipeline

Production pipeline: **PDF → Markdown → Structured Data → Linked Records**

- **Stage 1:** PDF → Markdown (Mistral OCR + Vision refinement)
- **Stage 2:** Markdown → Structured JSON (LLM extraction of 16 classes)
- **Stage 3:** Link records by foreign keys (optional)

---

## Quick Start

### Full Pipeline (Default)

```bash
python run_pipeline.py
```

Processes all PDFs in `documents/` through all three stages. All output saved to `output/` folder.

### Command Options

**Single PDF with vision refinement:**

```bash
python run_pipeline.py --input documents/ccc_dresden.pdf
```

**OCR only (no vision refinement - faster):**

```bash
python run_pipeline.py --no-vision
```

**Single PDF + OCR only (fastest for testing):**

```bash
python run_pipeline.py --input documents/ccc_dresden.pdf --no-vision
```

**Skip mapping stage:**

```bash
python run_pipeline.py --no-mapping
```

**Help:**

```bash
python run_pipeline.py --help
```

### Typical Workflow

```bash
# 1. Test single file with OCR only (~10-15 min for 35MB)
python run_pipeline.py --input documents/ccc_dresden.pdf --no-vision

# 2. If OK, full pipeline with vision (~25-35 min)
python run_pipeline.py --input documents/ccc_dresden.pdf

# 3. If working, process all PDFs
python run_pipeline.py
```

### Output Structure

```
output/
├── pdf2markdown/          # Markdown files (TIMESTAMP_docname/)
├── extraction/            # Extracted JSON (all classes)
└── mapping/               # Linked records
```

---

## Setup

```bash
pip install -r requirements.txt

# Create .env with API keys
MISTRAL_API_KEY=sk-...
OPENROUTER_API_KEY=sk-...
```

---

## Configuration

Edit `llm_config.yml`:

```yaml
pdf2markdown:
  model: google/gemini-3-flash-preview
  temperature: 0.1

extraction:
  model: deepseek/deepseek-v3.2 # ⭐ Best for tool calling
  temperature: 0.1

mapping:
  model: google/gemini-3-flash-preview
  temperature: 0.1
```

---

## Stage 1: PDF → Markdown

### Examples

```bash
# Single PDF with vision refinement
python -m pdf2markdown.pdf_to_markdown --input documents/sample.pdf

# Without vision (faster)
python -m pdf2markdown.pdf_to_markdown --input documents/sample.pdf --vision-model ""

# Batch processing
python -m pdf2markdown.pdf_to_markdown --input documents/ --pattern "*.pdf"

# Advanced options
python -m pdf2markdown.pdf_to_markdown --input large.pdf \
  --max-upload-bytes 5242880 \
  --vision-max-rounds 5 \
  --no-images
```

### Output

```
output/pdf2markdown/TIMESTAMP_docname/
├── combined_markdown.md       # Final markdown for extraction
├── page-0001.md
├── images/
│   └── page-0001.jpeg
└── vision_diffs/
    └── page-0001-round-1.diff
```

---

## Stage 2: Extraction (Markdown → JSON)

### Examples

```bash
# Extract all classes
python -m extraction.scripts.extract \
  --markdown pdf2markdown/output/TIMESTAMP_doc/combined_markdown.md

# Specific classes only
python -m extraction.scripts.extract \
  --markdown path/to/combined_markdown.md \
  --class-names City CityAnnualStats Initiative

# Different model
python -m extraction.scripts.extract \
  --markdown path/to/combined_markdown.md \
  --model anthropic/claude-3.5-sonnet
```

### Available Classes

```
City                  CityAnnualStats        ClimateCityContract    Sector
EmissionRecord        CityBudget             BudgetFunding          FundingSource
Initiative            InitiativeStakeholder  Indicator              IndicatorValue
CityTarget            InitiativeIndicator    TefCategory            InitiativeTef
```

### Output Example

```json
// output/extraction/CityAnnualStats.json
[
  {
    "year": 2023,
    "population": 628718,
    "populationDensity": 2129,
    "notes": "As at 31.12.2023"
  },
  {
    "year": 2019,
    "notes": "Baseline year for GHG inventory"
  }
]
```

### Key Features

✅ **Year Extraction** - Properly extracts years from: "As at 31.12.2023" → 2023, "base year 2019" → 2019, "by 2030" → 2030

✅ **Tool Calling** - Uses function calls for structured output

✅ **Validation** - Pydantic models ensure data integrity

✅ **Duplicate Detection** - Skips duplicate records

✅ **Error Reporting** - Detailed logs show validation results

---

## Stage 3: Mapping (Optional)

```bash
# Link foreign keys
python -m mapping.mapping --input extraction/output --apply

# Review mappings
python -m mapping.mapping --input extraction/output --review
```

---

## Project Structure

```
project_root/
├── pdf2markdown/              # Stage 1: PDF → Markdown
├── extraction/                # Stage 2: Markdown → JSON
│   ├── prompts/              # LLM prompts by class
│   ├── tools/                # Tool definitions
│   ├── utils/                # Validation & parsing
│   ├── output/               # Extracted JSON files
│   └── extract.py            # Core logic
├── mapping/                   # Stage 3: Link records
├── database/
│   └── models.py             # Pydantic schemas (16 classes)
├── documents/                # Input PDFs
├── tests/
├── llm_config.yml            # Model configuration
├── run_pipeline.py           # Full pipeline
├── requirements.txt
└── README.md
```

---

## Typical Workflows

### Single Document

```bash
python -m pdf2markdown.pdf_to_markdown --input documents/my_city.pdf
python -m extraction.scripts.extract --markdown pdf2markdown/output/TIMESTAMP_my_city/combined_markdown.md
cat output/extraction/City.json
```

### Batch Processing

```bash
python run_pipeline.py
# Results in: output/pdf2markdown/, output/extraction/, output/mapping/
```

### Test Specific Class

```bash
python -m extraction.scripts.extract --markdown existing.md --class-names CityAnnualStats
```

---

## Python API

### PDF to Markdown

```python
from pathlib import Path
from mistralai import Mistral
from openai import OpenAI
from pdf2markdown.pdf_to_markdown import pdf_to_markdown_mistral

mistral = Mistral(api_key="sk-...")
vision = OpenAI(api_key="sk-...", base_url="https://openrouter.ai/api/v1")

output = pdf_to_markdown_mistral(
    pdf_path=Path("documents/sample.pdf"),
    output_root=Path("pdf2markdown/output"),
    client=mistral,
    vision_client=vision,
    vision_model="google/gemini-3-flash-preview",
)
```

### Extract Data

```python
from openai import OpenAI
from extraction.extract import run_class_extraction
from database.models import City

client = OpenAI(api_key="sk-...", base_url="https://openrouter.ai/api/v1")

run_class_extraction(
    client=client,
    model_name="deepseek/deepseek-v3.2",
    system_prompt="...",
    user_template="...",
    markdown_text=markdown_content,
    model_cls=City,
    output_dir=Path("extraction/output"),
)
```

---

## Troubleshooting

| Issue                        | Solution                                                    |
| ---------------------------- | ----------------------------------------------------------- |
| Missing Mistral API key      | Set `MISTRAL_API_KEY` in `.env`                             |
| Vision refinement fails      | Check `OPENROUTER_API_KEY` in `.env`                        |
| Missing required field: year | Markdown may lack year info, check `extraction/debug_logs/` |
| OpenRouter API error         | Verify API key has credits                                  |
| Large PDF timeout            | Use `--max-upload-bytes 5242880` to split into 5MB chunks   |

---

## Recent Fixes (January 2026)

✅ **Model Selection** - Switched extraction to `deepseek/deepseek-v3.2` for superior tool calling (was generating empty objects with google/gemini)

✅ **Year Extraction** - Enhanced `CityAnnualStats.md` prompt with explicit examples for extracting years from varied text patterns

✅ **Error Messages** - Improved validation feedback to show exactly which fields are missing and what data was received

---

## Architecture Details

### PDF → Markdown Flow

```
PDF → [Mistral OCR] → Markdown + Images
  ↓
[2-Page Windows] → {image_left, markdown_left, image_right, markdown_right}
  ↓
[Vision Agent] → Tool calls → Edits
  ↓
Final Markdown ✓
```

### How to Extend

1. **New extraction class?** Add model to `database/models.py` and prompt to `extraction/prompts/`
2. **Different PDF pipeline?** Modify `pdf2markdown/pdf_to_markdown.py`
3. **Custom mapping?** Edit `mapping/mappers/`

---

## References

- [Mistral OCR](https://docs.mistral.ai/)
- [OpenRouter](https://openrouter.ai/)
- [Docling](https://github.com/DS4SD/docling)

---

## License

See `LICENSE.md`

**Last Updated:** January 4, 2026
