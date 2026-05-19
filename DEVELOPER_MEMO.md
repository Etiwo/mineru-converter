# mineru-converter Developer Memo

Technical reference for developers. Contains CLI commands, architecture details, and API reference.

## CLI Commands

### convert — Convert files

```bash
# Convert a single file
python3 run.py convert --file inbox/document.pdf

# Batch convert
python3 run.py convert --dir inbox/ --workers 2

# Convert specific pages (PDF only)
python3 run.py convert --file doc.pdf --pages 3-5

# Use OCR for scanned documents
python3 run.py convert --file scanned.pdf --method ocr

# Convert with language setting
python3 run.py convert --file doc.pdf --lang en

# Force re-conversion
python3 run.py convert --file doc.pdf --force
```

### CLI Options

| Option | Description | Example |
|--------|-------------|---------|
| `--file <path>` | Convert a single file | `--file doc.pdf` |
| `--dir <path>` | Convert all files in directory | `--dir inbox/` |
| `--output-dir <dir>` | Custom output directory | `--output-dir ./output` |
| `--force` | Re-convert even if already done | `--force` |
| `--workers <N>` | Parallel workers (default: 1) | `--workers 2` |
| `--verbose` | Print MinerU output | `--verbose` |
| `--json` | Output as JSON | `--json` |
| `--pages <range>` | Page range for PDF (1-indexed) | `--pages 18-28` |
| `--method <auto|txt|ocr>` | PDF parsing method | `--method ocr` |
| `--lang <code>` | Document language | `--lang en` |

**Note**: `--pages` is only allowed with `--file`, not with `--dir`.

### plan — View conversion plan

```bash
python3 run.py plan --dir inbox/ --json
```

### status — Check conversion status

```bash
python3 run.py status
python3 run.py status --json
```

## Configuration

Edit `config.yaml`:

```yaml
mineru:
  command: "mineru"          # Or absolute path to venv/bin/mineru
  args:
    backend: "pipeline"
    model: "auto"
    language: "ch"           # Default language
    method: "auto"           # Default parsing method (auto/txt/ocr)
```

## Architecture

- **PDF/DOCX/PPTX/XLSX/images** — converted via MinerU (see `mineru_caller.py` → `file_organizer.py`)
- **EPUB** — converted via a built-in converter (`epub_converter.py`) that uses `ebooklib` + `html2text`, completely independent of MinerU
- **MinerU auto-detection** — checks availability before conversion, guides installation
- **Atomic manifest writes** — single-lock read-modify-save for concurrent safety
- **Unique temp directories** — each worker gets its own `.tmp_mineru_{uuid}` to avoid conflicts
- **File locking** — safe `manifest.json` access with `fcntl.flock`
- **Image handling** — all formats store images in `attachments/<hash8>/` with Obsidian-compatible relative paths; EPUB uses its own path-rewriting logic (`epub_converter._rewrite_image_paths`)

## Testing

```bash
python3 -m pytest tests/ -v
```

72+ tests covering MinerU invocation, page range parsing, CLI argument handling, installation guidance, file organization, manifest management, and EPUB conversion.
