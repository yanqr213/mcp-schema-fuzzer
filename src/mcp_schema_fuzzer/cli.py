from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .engine import run_fuzz
from .generator import find_case, generate_cases
from .init_suite import init_suite
from .reports import gate_report, summarize_for_console, top_findings, write_report_bundle
from .suite import load_examples, load_suite, load_suite_and_validate
from .utils import load_json, resolve_output_base


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-schema-fuzzer", description="Offline schema fuzzing for MCP servers and agent tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fuzz_parser = subparsers.add_parser("fuzz", help="Generate fuzz cases, validate transcripts, and write reports.")
    fuzz_parser.add_argument("suite", help="Path to suite.json")
    fuzz_parser.add_argument("--output", required=True, help="Output file stem. Example: outputs/run/report")
    fuzz_parser.add_argument("--check", choices=["warning", "error"], help="Fail if findings at or above the threshold exist.")

    validate_parser = subparsers.add_parser("validate-fixtures", help="Validate suite, schema, example, and transcript fixtures.")
    validate_parser.add_argument("suite", help="Path to suite.json")

    init_parser = subparsers.add_parser("init-suite", help="Create a starter suite directory.")
    init_parser.add_argument("path", help="Directory to create")
    init_parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty destination")

    explain_parser = subparsers.add_parser("explain", help="Explain why a generated case exists.")
    explain_parser.add_argument("suite", help="Path to suite.json")
    explain_parser.add_argument("case_id", help="Generated case id")

    check_parser = subparsers.add_parser("check", help="Apply a severity gate to an existing JSON report.")
    check_parser.add_argument("report", help="Path to a JSON report")
    check_parser.add_argument("--check", required=True, choices=["warning", "error"], help="Severity threshold")
    return parser


def cmd_validate(args) -> int:
    suite, result = load_suite_and_validate(args.suite)
    if result.errors:
        print(f"{suite.name}: fixture validation failed")
        for item in result.errors:
            print(f"ERROR: {item}")
        for item in result.warnings:
            print(f"WARNING: {item}")
        return 1
    print(f"{suite.name}: fixtures are valid")
    for item in result.warnings:
        print(f"WARNING: {item}")
    return 0


def cmd_fuzz(args) -> int:
    suite, validation = load_suite_and_validate(args.suite)
    if validation.errors:
        print(f"{suite.name}: fixture validation failed before fuzzing", file=sys.stderr)
        for item in validation.errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1

    report = run_fuzz(suite)
    output_base = resolve_output_base(args.output)
    paths = write_report_bundle(report, output_base)
    print(summarize_for_console(report))
    print(f"Markdown: {paths['markdown']}")
    print(f"JSON: {paths['json']}")
    print(f"JUnit: {paths['junit']}")
    print(f"SARIF: {paths['sarif']}")
    for finding in top_findings(report):
        print(f"[{finding['severity']}] {finding['code']}: {finding['message']}")
    if args.check and not gate_report(report, args.check):
        print(f"Gate failed at severity threshold: {args.check}", file=sys.stderr)
        return 2
    return 0


def cmd_init_suite(args) -> int:
    path = init_suite(args.path, force=args.force)
    print(f"Created starter suite at {path}")
    return 0


def cmd_explain(args) -> int:
    suite, validation = load_suite_and_validate(args.suite)
    if validation.errors:
        print(f"{suite.name}: fixture validation failed before explain", file=sys.stderr)
        for item in validation.errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1

    for target in suite.targets:
        schema = load_json(target.schema_path)
        examples = load_examples(target.examples_path) if target.examples_path else []
        cases = generate_cases(target.id, schema, examples)
        try:
            case = find_case(cases, args.case_id)
        except KeyError:
            continue
        print(f"Case: {case.id}")
        print(f"Target: {case.target}")
        print(f"Category: {case.category}")
        print(f"Severity: {case.severity}")
        print(f"Path: {case.path}")
        print(f"Source Example: {case.source_example}")
        print(f"Rationale: {case.rationale}")
        print("Payload:")
        print(case.payload)
        return 0

    print(f"Case not found: {args.case_id}", file=sys.stderr)
    return 1


def cmd_check(args) -> int:
    report = load_json(Path(args.report))
    passed = gate_report(report, args.check)
    print(summarize_for_console(report))
    print(f"Gate threshold: {args.check}")
    if not passed:
        print("Gate failed", file=sys.stderr)
        return 2
    print("Gate passed")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate-fixtures":
        return cmd_validate(args)
    if args.command == "fuzz":
        return cmd_fuzz(args)
    if args.command == "init-suite":
        return cmd_init_suite(args)
    if args.command == "explain":
        return cmd_explain(args)
    if args.command == "check":
        return cmd_check(args)
    parser.error("unknown command")
    return 1
