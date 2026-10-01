#!/usr/bin/bash

set -eu -o pipefail

uv run pytest \
  -vv \
  --disable-warnings \
  --tb=short \
  -s tests/ssh/
