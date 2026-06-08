# Contributing

## Development workflow

1. Use Python 3.9 or newer.
2. Create a virtual environment if you want isolated installs.
3. Install the project in editable mode:

```bash
python -m pip install -e .
```

4. Run the test suite:

```bash
python -m unittest discover -s tests -t . -v
```

5. Smoke-test the CLI against the included examples:

```bash
python -m mcp_schema_fuzzer validate-fixtures examples/filesystem-tool/suite.json
python -m mcp_schema_fuzzer fuzz examples/filesystem-tool/suite.json --output outputs/smoke/filesystem --check error
```

## Reporting issues

- Include the suite files or a reduced reproduction when possible.
- Mention your Python version and operating system.
- Share the generated JSON report if the problem is in matching, deduplication, or CI gating.

## Scope

- Runtime dependencies are intentionally avoided.
- The project never executes dangerous strings or calls remote services.
- Changes that expand supported schema keywords should include tests and README updates.
