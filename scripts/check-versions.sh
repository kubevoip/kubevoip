#!/usr/bin/env bash
set -euo pipefail
version="${1#v}"
python_version="$(awk -F'"' '/^version = / {print $2; exit}' pyproject.toml)"
test "$version" = "$python_version"
