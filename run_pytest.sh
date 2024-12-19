#!/usr/bin/bash

set -eu -o pipefail

poetry run pytest -vv --disable-warnings --tb=short --ignore=tests/ssh/
