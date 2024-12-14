#!/usr/bin/bash

# Note:
# Only run this script if you have Act (https://nektosact.com/) installed in your machine.

set -eu -o pipefail

if [ ! -d "$HOME/artifact-server-dir" ]; then
  mkdir -p "$HOME/artifact-server-dir/marsh"
fi

act \
  --artifact-server-path="$HOME/artifact-server-dir" \
  --use-gitignore \
  --env-file=".env.act" \
  --secret-file=".secrets" \
  --var-file=".vars"
