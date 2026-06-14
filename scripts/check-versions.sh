#!/usr/bin/env bash
set -euo pipefail
version="${1#v}"
python_version="$(awk -F'"' '/^version = / {print $2; exit}' pyproject.toml)"
chart_version="$(sed -n 's/^version: //p' charts/kubevoip/Chart.yaml | head -1)"
app_version="$(awk -F'"' '/^appVersion: / {print $2; exit}' charts/kubevoip/Chart.yaml)"
test "$version" = "$python_version"
test "$version" = "$chart_version"
test "$version" = "$app_version"
