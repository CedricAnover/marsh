#!/usr/bin/env bash

set -eu -o pipefail

poetry run pytest -vv --disable-warnings --tb=short
