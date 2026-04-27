# mineru-converter

Convert documents to Markdown using MinerU. Designed as an opencode Skill but works as a standalone CLI tool.

## Features

- Convert PDF, DOCX, PPTX, XLSX, and image files to Markdown
- Incremental conversion — skips already-converted files
- Extract and organize images for Obsidian compatibility
- OCR support for scanned documents
- Automatic MinerU installation detection and guidance

## Supported Formats

PDF, DOCX, PPTX, XLSX, PNG, JPG, JPEG, BMP, TIFF

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install MinerU

MinerU must be installed before use. The converter will automatically detect if MinerU is available and prompt you to install it if not found.

Check if MinerU is installed:

```bash
mineru --version
```

If MinerU is not installed, the converter offers:
- **Auto-install**: Creates a virtual environment in `.mineru_venv/` under the skill directory
- **Manual install**: Provides installation instructions to run manually

### 3. Configure

```bash
cp config.template.yaml config.yaml
# Edit config.yaml if needed
```

## How to Use

Place your documents in the `inbox/` directory, then use the converter through natural language. Here are typical scenarios:

### Scenario 1: Convert all documents in a folder

When you have multiple files and want to convert everything:

> "Convert all documents in the inbox folder to Markdown."
> "Batch convert the inbox directory."
> "Convert everything in inbox/."

The converter processes all supported files in the directory, skipping those already converted.

### Scenario 2: Convert a specific page range of a PDF

When you only need certain pages from a PDF:

> "Convert pages 3 to 5 of this PDF to Markdown."
> "Convert this document from page 18 to page 28."
> "Extract only page 10 of this PDF."

Works with PDF files only. Other formats are converted in full.

### Scenario 3: Use OCR for scanned documents

When dealing with scanned image-based PDFs that need text recognition:

> "Use OCR to convert this scanned PDF."
> "Convert this document with OCR — it's image-based."
> "This is a scanned document, please recognize the text."

OCR enables text extraction from images and scanned pages.

### Scenario 4: Convert documents in different languages

When the document is not in Chinese and you want better recognition accuracy:

> "Convert this English document to Markdown."
> "Convert this Japanese PDF."
> "Process this English PDF with language detection."

The converter supports Chinese (default), English, Japanese, Korean, and many other languages.

### Scenario 5: Re-convert a file

When the previous conversion result is unsatisfactory or the file has changed:

> "Re-convert this file."
> "This conversion was wrong, convert it again."
> "Force re-conversion."

### Scenario 6: Check what will be converted

When you want to see which files are pending and which are already done:

> "What files are ready to be converted?"
> "Show me the conversion plan."
> "Which files have already been converted?"

### Scenario 7: Convert with parallel processing

When you have many files and want to speed up:

> "Batch convert the inbox folder with 2 workers."
> "Process files in parallel."

### Scenario 8: Convert with OCR for all files

When converting a batch of documents and all need OCR:

> "Batch convert the inbox folder using OCR."
> "Convert all files in inbox with OCR method."

## Output Location

Converted Markdown files and extracted images are saved in the `raw/` directory:

```
<project>/
├── inbox/                     # Place documents here
│   ├── paper.pdf
│   └── notes.docx
├── raw/                       # Converted output
│   ├── paper.md
│   ├── notes.md
│   ├── attachments/
│   │   └── <hash8>/          # Images grouped by file hash
│   └── manifest.json         # Conversion records
```

## Configuration

Edit `config.yaml` to change defaults:

```yaml
mineru:
  command: "mineru"          # Or absolute path to venv/bin/mineru
  args:
    backend: "pipeline"
    model: "auto"
    language: "ch"           # Default language
    method: "auto"           # Default parsing method (auto/txt/ocr)
```

## Architecture Overview

- **MinerU auto-detection** — checks availability before conversion, guides installation
- **Atomic manifest writes** — single-lock read-modify-save for concurrent safety
- **Unique temp directories** — each worker gets its own `.tmp_mineru_{uuid}` to avoid conflicts
- **File locking** — safe `manifest.json` access with `fcntl.flock`

## Testing

```bash
python3 -m pytest tests/ -v
```

72 tests covering MinerU invocation, page range parsing, CLI argument handling, installation guidance, file organization, and manifest management.
