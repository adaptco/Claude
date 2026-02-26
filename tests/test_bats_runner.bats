#!/usr/bin/env bats

setup_file() {
    # Path to the bats executable provided by the user.
    # IMPORTANT: This test assumes 'bats' is in the system's PATH.
    # If not, you may need to provide the full path to bats.sh
    BATS_EXECUTABLE="bats"
}

@test "bats runner: correctly reports test failures" {
    # Run the bats executable against the test suite that is designed to have failures.
    # The '|| true' prevents this script from exiting if bats returns a non-zero exit code,
    # which it should do when tests fail.
    run "$BATS_EXECUTABLE" "tests/internals/suite.bats" || true

    # 1. Assert that the exit code is 1, indicating a test failure.
    [ "$status" -eq 1 ]

    # 2. Assert that the output summary is correct.
    assert_output --partial "1 test, 1 failure"
}

@test "bats runner: correctly identifies skipped tests" {
    run "$BATS_EXECUTABLE" "tests/internals/suite.bats" || true

    # Assert that the output summary mentions the skipped test.
    # Note: bats output combines passed and skipped in its summary line.
    assert_output --partial "2 tests, 1 skipped"
}

@test "bats runner: correctly identifies passing tests" {
    # To test for success, we run only the passing test by name
    run "$BATS_EXECUTABLE" --filter "A passing test" "tests/internals/suite.bats"

    # 1. Assert that the exit code is 0, indicating success.
    [ "$status" -eq 0 ]

    # 2. Assert that the output summary is correct.
    assert_output --partial "1 test, 0 failures"
}
