#!/usr/bin/env bats

@test "A passing test" {
  [ 1 -eq 1 ]
}

@test "A failing test" {
  [ 1 -eq 0 ]
}

@test "A skipped test" {
  skip "This test is skipped"
  # This code is never reached
  [ 0 -eq 0 ]
}
