---
name: mineru-converter
description: Convert documents (PDF, DOCX, PPTX, XLSX, images) to Markdown using MinerU, with incremental detection, page range selection, OCR method, and language options.
license: MIT
---

# MinerU Document Converter

Convert documents (PDF, DOCX, PPTX, XLSX, PNG, JPG, JPEG, BMP, TIFF) to Markdown using MinerU.

## What I do

- Convert single files or batch directories to Markdown
- Incremental conversion — skips already-converted files (SHA256 based)
- Extract and organize images into `raw/attachments/<hash>/`
- Rewrite image paths in Markdown to be Obsidian-compatible
- Clean up MinerU temporary files
- Support page range, OCR method, and language selection

## When to use me

Use when the user wants to:
- Convert a PDF or other document to Markdown
- Convert a specific page range of a PDF
- Batch convert a folder of documents
- Check which files are already converted and which need conversion
- Integrate document conversion into a knowledge pipeline

## Source and Output

- **Source**: Documents in the project's `inbox/` directory
- **Output**: Converted files in the project's `raw/` directory
- **Manifest**: `raw/manifest.json` tracks conversion state

## Prerequisites

- **MinerU** must be installed and available as `mineru` in PATH (`mineru --version`)
- The converter automatically detects if MinerU is installed before converting
- If MinerU is not found, the converter will prompt the user to install it

## Commands

Always run commands from the project directory, or use the full path.
The converter lives at: `~/.config/opencode/skills/mineru-converter/`

### Convert a single file

```bash
cd <project_dir> && python3 ~/.config/opencode/skills/mineru-converter/run.py convert --file <path> [--force] [--pages 3-5] [--method ocr] [--lang en]
```

| Option | Description | Example |
|--------|-------------|---------|
| `--file` | Path to file to convert (required) | `--file report.pdf` |
| `--force` | Force re-conversion even if already done | `--force` |
| `--pages` | Page range to convert (1-indexed, only for PDF) | `--pages 3-5` |
| `--method` | PDF parsing method: auto, txt, or ocr | `--method ocr` |
| `--lang` | Document language code | `--lang en` |

### Convert all files in a directory

```bash
cd <project_dir> && python3 ~/.config/opencode/skills/mineru-converter/run.py convert --dir <path> [--force] [--workers 2] [--method ocr] [--lang en]
```

| Option | Description | Example |
|--------|-------------|---------|
| `--dir` | Directory of files to convert (required) | `--dir inbox/` |
| `--force` | Force re-conversion even if already done | `--force` |
| `--workers` | Parallel workers for batch (default: 1) | `--workers 2` |
| `--method` | PDF parsing method applied to all files | `--method ocr` |
| `--lang` | Document language applied to all files | `--lang en` |

> **Note**: `--pages` is only allowed with `--file`, not with `--dir`.

### View conversion plan (no execution)

```bash
python3 ~/.config/opencode/skills/mineru-converter/run.py plan --dir <path> [--json]
```

### Check conversion status

```bash
python3 ~/.config/opencode/skills/mineru-converter/run.py status
```

## Output Structure

```
<output_dir>/
├── document.md                  # Converted markdown
├── attachments/
│   └── <hash8>/                 # Images grouped by file hash
│       ├── image1.jpg
│       └── image2.png
└── manifest.json                # Conversion records
```

## JSON Output

Add `--json` flag to get structured output for parsing:

```json
{
  "scanned": 3,
  "processed": 1,
  "skipped": 2,
  "failed": 0,
  "items": [
    {
      "path": "/abs/path/to/file.pdf",
      "status": "success",
      "details": {
        "md_path": "document.md",
        "images": 5
      }
    }
  ]
}
```

## Supported Formats

PDF, DOCX, PPTX, XLSX, PNG, JPG, JPEG, BMP, TIFF

## Page Range Syntax

Use `--pages` to specify a range of pages to convert (PDF only):

```bash
# Convert pages 3 to 5
convert --file doc.pdf --pages 3-5

# Convert single page 10
convert --file doc.pdf --pages 10
```

Pages are 1-indexed (human-friendly) and are automatically converted to 0-indexed for MinerU.

## OCR Method

Use `--method` to control PDF parsing strategy:

| Method | Description | Use case |
|--------|-------------|----------|
| `auto` | Auto-detect (default) | Most documents |
| `txt` | Text extraction only | Documents with extractable text |
| `ocr` | OCR recognition | Scanned/image PDFs |

```bash
# Use OCR for scanned PDFs
convert --file scanned.pdf --method ocr

# Use text extraction for digital PDFs
convert --file digital.pdf --method txt
```

## Language

Use `--lang` to specify the document language for better OCR accuracy:

```bash
# English document
convert --file doc.pdf --lang en

# Japanese document
convert --file doc.pdf --lang ja

# Chinese (default)
convert --file doc.pdf --lang ch
```

## Configuration

Edit `config.yaml` to change defaults:

```yaml
mineru:
  command: "mineru"          # or absolute path to venv/bin/mineru
  args:
    backend: "pipeline"
    model: "auto"
    language: "ch"           # default language
    method: "auto"           # default parsing method
```

## Error Handling

- Unsupported file formats are skipped (not failed)
- Individual file failures do not stop the batch
- Failed files are logged in manifest.json with error details
- MinerU installation is checked before every conversion
