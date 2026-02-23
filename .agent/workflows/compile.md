---
description: Compile and validate the avatar.controlbus application
---

# Compile the Application

Since this is a Python project, "compiling" means syntax-checking all source files, validating schemas, and running the test suite.

// turbo-all

## Steps

1. **Syntax-check all Python source files**

```bash
python -m py_compile bytesampler_adapter.py
python -m py_compile test_harness.py
```

1. **Validate the JSON schema**

```bash
python -c "import json; json.load(open('control-plane-state.schema.json')); print('JSON schema valid')"
```

1. **Run the full test suite**

```bash
python -m pytest test_harness.py -v --tb=short
```

1. **Report results** — Summarize how many tests passed/failed and list any failures.
