#!/bin/bash
#
# diag2.sh: Diagnostic script to verify implementation of the Operator Command Vocabulary.
# This script checks for key artifacts and code structures required by the ORCHESTRATOR PLAN.
#

set -e # Exit immediately if any check fails

echo "Running diagnostics for Operator Command Vocabulary..."
echo "----------------------------------------------------"

# --- CODEX-1 Check ---
if [ ! -d "packages/core" ]; then
    echo "FAIL: packages/core not found" >&2
    exit 1
fi
if ! grep -q "class Capability" packages/core/index.ts || ! grep -q "policy_eval" packages/core/index.ts; then
    echo "FAIL: Capability model not found in packages/core" >&2
    exit 1
fi
echo "✅ CODEX-1 PASS: Capability tokens + policy primitives found."

# --- CODEX-2 Check ---
if [ ! -d "packages/mcp-router" ]; then
    echo "FAIL: packages/mcp-router not found" >&2
    exit 1
fi
if ! grep -q "message_refused" packages/mcp-router/index.ts; then
    echo "FAIL: message_refused fossil not handled in packages/mcp-router" >&2
    exit 1
fi
echo "✅ CODEX-2 PASS: Unbypassable trigger gate found."

# --- CODEX-3 Check ---
if [ ! -d "packages/gateway" ]; then
    echo "FAIL: packages/gateway not found" >&2
    exit 1
fi
if ! grep -q "command.on('/deploy'" packages/gateway/index.ts; then
    echo "FAIL: Operator command vocabulary not found in packages/gateway" >&2
    exit 1
fi
echo "✅ CODEX-3 PASS: Operator command vocabulary + consent hooks found."

# --- CODEX-4 Check ---
if [ ! -d "packages/artifact-store" ]; then
    echo "FAIL: packages/artifact-store not found" >&2
    exit 1
fi
if ! grep -q "store.verifyChain()" packages/artifact-store/index.ts; then
    echo "FAIL: Chain verification not found in packages/artifact-store" >&2
    exit 1
fi
echo "✅ CODEX-4 PASS: Audit ledger artifacts + chain-verification found."

# --- CODEX-5 Check ---
if [ ! -d "packages/adapters/ci" ]; then
    echo "FAIL: packages/adapters/ci not found" >&2
    exit 1
fi
if ! grep -q "generate_workflow_stub" packages/adapters/ci/index.ts; then
    echo "FAIL: Safe stubs for workflows not found" >&2
    exit 1
fi
echo "✅ CODEX-5 PASS: Safe stubs for adapters found."

echo "----------------------------------------------------"
echo "All checks passed!"

exit 0
