# Changelog

## 0.2.0 - 2026-06-08

- Added SARIF 2.1.0 report output for GitHub Code Scanning.
- Added fixture-backed SARIF locations, stable partial fingerprints, rule metadata, and CLI path output.
- Added CI smoke validation for generated SARIF and tests for SARIF rendering.
- Updated package metadata to point to the public GitHub repository.

## 0.1.0 - 2026-06-08

- First public release of `mcp-schema-fuzzer`.
- Added offline CLI commands: `fuzz`, `validate-fixtures`, `init-suite`, `explain`, `check`.
- Added schema parsing, boundary-case generation, transcript validation, deduplication, severity handling, and Markdown/JSON/JUnit reports.
- Added example suites, CI workflow, and a unit test suite covering parser, generators, fixtures, reports, and CLI behavior.
