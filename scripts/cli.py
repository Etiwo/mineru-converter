"""CLI entry point for mineru-converter-skill."""

import sys
import json
import argparse
from pathlib import Path

# Support both module and direct execution
try:
    from .config_loader import get_output_dir
    from .converter import convert_single, convert_batch, build_plan, get_status
    from .mineru_caller import check_mineru_available, MineruNotFoundError
    from .mineru_setup import check_mineru_available as check_mineru_setup, install_mineru_auto, show_manual_instructions
    from .manifest_manager import ManifestLoadError
except ImportError:
    _project_root = Path(__file__).resolve().parent.parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from config_loader import get_output_dir
    from converter import convert_single, convert_batch, build_plan, get_status
    from mineru_caller import check_mineru_available, MineruNotFoundError
    from mineru_setup import check_mineru_available as check_mineru_setup, install_mineru_auto, show_manual_instructions
    from manifest_manager import ManifestLoadError


def _format_report(report, as_json=False):
    """Format conversion report for display."""
    if as_json:
        return json.dumps(report, indent=2, ensure_ascii=False)

    lines = []
    if "items" in report:
        lines.append(f"Scanned: {report['scanned']}")
        lines.append(f"Processed: {report['processed']}")
        lines.append(f"Skipped: {report['skipped']}")
        lines.append(f"Failed: {report['failed']}")
        lines.append("")

        for item in report.get("items", []):
            icon = {"success": "[OK]", "skipped": "[SKIP]", "failed": "[ERR]"}.get(item["status"], "[???]")
            lines.append(f"{icon} {item['path']}")
            if item.get("error"):
                lines.append(f"       {item['error']}")
            if item.get("details"):
                d = item["details"]
                if d.get("md_path"):
                    lines.append(f"       -> {d['md_path']}")
                if d.get("images"):
                    lines.append(f"       images: {d['images']}")
    elif "process" in report:
        lines.append(f"Source:    {report['source_dir']}")
        lines.append(f"Output:    {report['output_dir']}")
        lines.append(f"Scanned:   {report['scanned']}")
        lines.append(f"To convert: {len(report['process'])}")
        lines.append(f"Already done: {len(report['skip'])}")
        lines.append("")

        if report["process"]:
            lines.append("To convert:")
            for item in report["process"]:
                lines.append(f"  [NEW] {item['path']}")
        if report["skip"]:
            lines.append("")
            lines.append("Already converted:")
            for item in report["skip"]:
                lines.append(f"  [SKIP] {item['path']}")
                if item.get("reason"):
                    lines.append(f"         {item['reason']}")
        if report.get("unsupported"):
            lines.append("")
            lines.append("Unsupported:")
            for item in report["unsupported"]:
                lines.append(f"  [SKIP] {item['path']} ({item['reason']})")
    elif "total" in report:
        lines.append(f"Output dir: {report['output_dir']}")
        lines.append(f"Total: {report['total']} (success: {report['success']}, failed: {report['failed']})")

    return "\n".join(lines)


def _ensure_mineru_installed():
    """Check if MinerU is installed, prompt user to install if not."""
    available, version = check_mineru_available()
    if available:
        return True

    print("MinerU is not installed or not in PATH.")
    print("The converter needs MinerU to function.")
    print()

    try:
        choice = input("Would you like to install MinerU? (A)uto / (M)anual / (C)ancel [A]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = "c"

    if choice in ("b", "m", "manual"):
        print()
        print(show_manual_instructions())
        return False
    elif choice in ("c", "cancel", "n", "no"):
        print("Aborted. Please install MinerU and try again.")
        return False
    else:
        # Default: auto install
        try:
            use_all_choice = input("Install full version (all backends) or core only? (F)ull / (C)ore [F]: ").strip().lower()
            use_all = use_all_choice not in ("c", "core", "core only")
        except (EOFError, KeyboardInterrupt):
            use_all = True

        print()
        if install_mineru_auto(use_all=use_all):
            # Re-check
            available, version = check_mineru_available()
            if available:
                print(f"MinerU installed successfully (version {version}).")
                return True
            else:
                print("Installation completed but MinerU still not detected. Check the output above for errors.")
                return False
        else:
            print("Installation failed. Please install manually.")
            return False


def main():
    parser = argparse.ArgumentParser(
        prog="mineru-converter",
        description="Convert documents (PDF, DOCX, PPTX, XLSX, images) to Markdown using MinerU.",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # convert command
    conv_parser = sub.add_parser("convert", help="Convert one or more files")
    conv_parser.add_argument("--file", type=str, help="Single file to convert")
    conv_parser.add_argument("--dir", type=str, help="Directory of files to convert")
    conv_parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: from config)")
    conv_parser.add_argument("--force", action="store_true", help="Force re-conversion even if already done")
    conv_parser.add_argument("--workers", type=int, default=1, help="Parallel workers for batch (default: 1)")
    conv_parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    conv_parser.add_argument("--verbose", action="store_true", help="Verbose output")
    conv_parser.add_argument("--pages", type=str, default=None, help="Page range to convert (e.g. '3-5'), only for single file")
    conv_parser.add_argument("--method", type=str, default=None, choices=["auto", "txt", "ocr"],
                             help="PDF parsing method (default: from config)")
    conv_parser.add_argument("--lang", type=str, default=None, help="Document language (default: from config)")

    # plan command
    plan_parser = sub.add_parser("plan", help="Show conversion plan without executing")
    plan_parser.add_argument("--dir", type=str, required=True, help="Directory to scan")
    plan_parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: from config)")
    plan_parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")

    # status command
    status_parser = sub.add_parser("status", help="Show conversion statistics")
    status_parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: from config)")
    status_parser.add_argument("--list-converted", action="store_true", help="List converted files")
    status_parser.add_argument("--list-failed", action="store_true", help="List failed files")
    status_parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    try:
        if args.command == "convert":
            # Validate: --pages only works with --file
            if args.dir and args.pages:
                parser.error("--pages can only be used with --file, not with --dir")

            # Ensure MinerU is installed before any conversion
            if not _ensure_mineru_installed():
                return 1

            if args.file:
                result = convert_single(
                    args.file, output_dir=output_dir, force=args.force,
                    verbose=args.verbose, pages=args.pages,
                    method=args.method, lang=args.lang,
                )
                # For single file, wrap in report format
                report = {"items": [result], "scanned": 1, "processed": 1 if result["status"] == "success" else 0,
                          "skipped": 1 if result["status"] == "skipped" else 0, "failed": 1 if result["status"] == "failed" else 0}
            elif args.dir:
                result = convert_batch(
                    args.dir, output_dir=output_dir, force=args.force,
                    workers=args.workers, verbose=args.verbose,
                    method=args.method, lang=args.lang,
                )
                report = result
            else:
                parser.error("--file or --dir required for convert")
                return 1

        elif args.command == "plan":
            report = build_plan(args.dir, output_dir=output_dir)

        elif args.command == "status":
            report = get_status(output_dir=output_dir,
                                list_converted=args.list_converted,
                                list_failed=args.list_failed)

        else:
            parser.print_help()
            return 1

        print(_format_report(report, as_json=args.as_json))

    except ManifestLoadError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
