"""Command line boundary for Table Sentry.

The scanner is intentionally read-only: JSON is emitted either to stdout or to
a newly-created output file, and all user-facing errors are concise stderr text.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from . import core


class UserError(Exception):
    """An invalid command, path, or input file."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="table-sentry", description="Scan tabular files for quality and leakage signals.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="scan one CSV or JSONL file")
    scan.add_argument("input", metavar="INPUT")
    scan.add_argument("--target")
    scan.add_argument("--id", dest="id_columns", action="append", default=[])
    scan.add_argument("--group", dest="group_columns", action="append", default=[])
    scan.add_argument("--time", dest="time_column")
    _output_options(scan)
    compare = sub.add_parser("compare", help="compare train and test for key overlap")
    compare.add_argument("train", metavar="TRAIN")
    compare.add_argument("test", metavar="TEST")
    compare.add_argument("--key", dest="overlap_keys", action="append", default=[])
    compare.add_argument("--target")
    _output_options(compare)
    return parser


def _output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", dest="output", default="-", metavar="OUT", help="JSON output path, or - for stdout")
    parser.add_argument("--pretty", action="store_true", help="indent JSON output")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")


def _same_path(a: Path, b: Path) -> bool:
    try:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _is_alias(path: Path, inputs: Sequence[Path]) -> bool:
    if any(_same_path(path, item) for item in inputs):
        return True
    try:
        st = path.stat()
        return any(st.st_dev == item.stat().st_dev and st.st_ino == item.stat().st_ino for item in inputs)
    except OSError:
        return False


def _emit(result: object, output: str, *, pretty: bool, force: bool, inputs: Sequence[str]) -> None:
    try:
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2 if pretty else None, sort_keys=True) + "\n"
    except (TypeError, ValueError) as exc:
        raise UserError(f"result is not valid JSON: {exc}") from exc
    if output == "-":
        sys.stdout.write(payload)
        return
    target = Path(output)
    source_paths = [Path(p) for p in inputs]
    if _is_alias(target, source_paths):
        raise UserError("output must be a different file from every input (aliases and hard links are not allowed)")
    if target.exists() and not force:
        raise UserError(f"output already exists: {output} (use --force to replace)")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not force:
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
        else:
            fd, temporary = tempfile.mkstemp(prefix=".table-sentry-", dir=target.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                    stream.write(payload)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    except (OSError, UnicodeError) as exc:
        raise UserError(f"cannot write output: {exc}") from exc


def _options(args: argparse.Namespace) -> core.ScanOptions:
    return core.ScanOptions(target=args.target, id_columns=tuple(getattr(args, "id_columns", ())),
                            time_column=getattr(args, "time_column", None), group_columns=tuple(getattr(args, "group_columns", ())),
                            overlap_keys=tuple(getattr(args, "overlap_keys", ())))


def _run(args: argparse.Namespace) -> object:
    if args.command == "scan":
        path = Path(args.input)
        if not path.is_file():
            raise UserError(f"input path is not a file: {args.input}")
        result = core.scan_file(path, _options(args))
        _emit(result, args.output, pretty=args.pretty, force=args.force, inputs=[args.input])
        if args.output == "-":
            print(f"table-sentry: scanned {path.name}", file=sys.stderr)
        return result
    train, test = Path(args.train), Path(args.test)
    for label, path in (("train", train), ("test", test)):
        if not path.is_file():
            raise UserError(f"{label} path is not a file: {path}")
    result = core.compare_splits(train, test, _options(args))
    _emit(result, args.output, pretty=args.pretty, force=args.force, inputs=[args.train, args.test])
    if args.output == "-":
        print(f"table-sentry: compared {train.name} and {test.name}", file=sys.stderr)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        args = _parser().parse_args(argv)
        _run(args)
        return 0
    except (UserError, ValueError, KeyError, FileNotFoundError, UnicodeError) as exc:
        print(f"table-sentry: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"table-sentry: error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # process boundary: never dump a traceback to CLI users
        print(f"table-sentry: internal error: {exc}", file=sys.stderr)
        return 3
