# CLI Test Pack

This directory contains command-line tests for the backend CLI.

Run from the repository root:

```bash
python3 tests/clitest/run_cli_tests.py
```

The first batch covers:

- core assessment command
- behavior training command
- trade review command
- questionnaire assessment / QA command
- basic rejection cases:
  - missing questionnaire answers
  - unknown questionnaire question id
  - invalid JSON input

The tests use temporary memory files and `--no-llm` for questionnaire submission,
so they do not call real Kimi or write persistent runtime state.

