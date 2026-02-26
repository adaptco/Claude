#!/usr/bin/env bats

# Mock version of the diag2.sh script since the original is outside the workspace.
# This mock is based on the ORCHESTRATOR PLAN provided.
setup_file() {
    # Make the mock script executable
    chmod +x diag2.sh
}

setup() {
    # Create a temporary directory for each test to mock the project structure
    BATS_TMPDIR=$(mktemp -d "$BATS_TEST_TMPDIR/bats.XXXXXX")
    cd "$BATS_TMPDIR"
}

teardown() {
    # Clean up the temporary directory
    cd ..
    rm -rf "$BATS_TMPDIR"
}

@test "diag2: success scenario - all checks pass" {
    # --- Setup Mock Environment ---
    # CODEX-1
    mkdir -p packages/core
    echo "class Capability { /* ... */ }" > packages/core/index.ts
    echo "function policy_eval() { return 'allow'; }" >> packages/core/index.ts

    # CODEX-2
    mkdir -p packages/mcp-router
    echo "if (!capability) { fossil.log('message_refused'); }" > packages/mcp-router/index.ts

    # CODEX-3
    mkdir -p packages/gateway
    echo "command.on('/deploy', create_capability);" > packages/gateway/index.ts

    # CODEX-4
    mkdir -p packages/artifact-store
    echo "type audit_event = { hash: string }; store.verifyChain();" > packages/artifact-store/index.ts

    # CODEX-5
    mkdir -p packages/adapters/ci
    echo "function generate_workflow_stub() {}" > packages/adapters/ci/index.ts

    # --- Run Script ---
    # Assuming diag2.sh is in the parent directory of the test runner
    run ../diag2.sh

    # --- Assertions ---
    [ "$status" -eq 0 ]
    assert_output --partial "✅ CODEX-1 PASS"
    assert_output --partial "✅ CODEX-2 PASS"
    assert_output --partial "✅ CODEX-3 PASS"
    assert_output --partial "✅ CODEX-4 PASS"
    assert_output --partial "✅ CODEX-5 PASS"
    assert_output --partial "All checks passed!"
}

@test "diag2: failure - CODEX-1 (Capability model) is missing" {
    # --- Setup Mock Environment (with CODEX-1 content missing) ---
    mkdir -p packages/core
    touch packages/core/index.ts # File exists but is empty

    # --- Run Script ---
    run ../diag2.sh

    # --- Assertions ---
    [ "$status" -ne 0 ]
    assert_output --partial "FAIL: Capability model not found in packages/core"
}

@test "diag2: failure - CODEX-2 (mcp-router refusal fossil) is missing" {
    # --- Setup Mock Environment ---
    # CODEX-1
    mkdir -p packages/core
    echo "class Capability { /* ... */ }" > packages/core/index.ts
    echo "function policy_eval() { return 'allow'; }" >> packages/core/index.ts

    # CODEX-2 (missing the required content)
    mkdir -p packages/mcp-router
    touch packages/mcp-router/index.ts

    # --- Run Script ---
    run ../diag2.sh

    # --- Assertions ---
    [ "$status" -ne 0 ]
    assert_output --partial "FAIL: message_refused fossil not handled in packages/mcp-router"
}


@test "diag2: failure - CODEX-4 (verifyChain) is missing" {
    # --- Setup Mock Environment ---
    # CODEX-1
    mkdir -p packages/core
    echo "class Capability { /* ... */ }" > packages/core/index.ts
    echo "function policy_eval() { return 'allow'; }" >> packages/core/index.ts

    # CODEX-2
    mkdir -p packages/mcp-router
    echo "if (!capability) { fossil.log('message_refused'); }" > packages/mcp-router/index.ts

    # CODEX-3
    mkdir -p packages/gateway
    echo "command.on('/deploy', create_capability);" > packages/gateway/index.ts

    # CODEX-4 (missing verifyChain)
    mkdir -p packages/artifact-store
    echo "type audit_event = { hash: string };" > packages/artifact-store/index.ts

    # --- Run Script ---
    run ../diag2.sh

    # --- Assertions ---
    [ "$status" -ne 0 ]
    assert_output --partial "FAIL: Chain verification not found in packages/artifact-store"
}

@test "diag2: failure - directory for a check is missing" {
    # --- Setup Mock Environment (missing packages/core directory) ---
    # No directories created

    # --- Run Script ---
    run ../diag2.sh

    # --- Assertions ---
    [ "$status" -ne 0 ]
    assert_output --partial "FAIL: packages/core not found"
}
