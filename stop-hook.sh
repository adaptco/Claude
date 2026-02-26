#!/bin/bash

STATE_FILE=".gemini/ralph-loop.local.md"

if [ ! -f "$STATE_FILE" ]; then
  echo "State file not found."
  exit 1
fi

# Use sed to replace active: true with active: false
# The sed command for both GNU and BSD/macOS sed
if sed --version 2>/dev/null | grep -q GNU; then
  sed -i 's/active: true/active: false/' "$STATE_FILE"
else
  sed -i '' 's/active: true/active: false/' "$STATE_FILE"
fi


echo "Ralph loop stopped."
