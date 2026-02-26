#!/usr/bin/env bats

setup() {
  # Create a dummy state file for the test
  mkdir -p .gemini
  cat > .gemini/ralph-loop.local.md <<EOF
---
active: true
iteration: 5
max_iterations: 10
completion_promise: "DONE"
started_at: "2025-01-06T12:00:00Z"
---

The task prompt goes here...
EOF
}

teardown() {
  # Clean up the dummy state file and directory
  rm -rf .gemini
}

@test "should set active to false in state file" {
  # Run the script
  run bash ./stop-hook.sh

  # Assert that the script executed successfully
  [ "$status" -eq 0 ]

  # Check that the output is correct
  [ "$output" = "Ralph loop stopped." ]

  # Verify that the state file was updated correctly
  grep "active: false" .gemini/ralph-loop.local.md
}

@test "should exit with an error if state file does not exist" {
  # Ensure no state file exists
  rm .gemini/ralph-loop.local.md

  # Run the script
  run bash ./stop-hook.sh

  # Assert that the script failed as expected
  [ "$status" -eq 1 ]

  # Check the error message
  [ "$output" = "State file not found." ]
}
