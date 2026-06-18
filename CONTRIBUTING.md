# Contributing

KubeVoIP welcomes bug reports, documentation fixes, tests, and focused feature
proposals.

## Development

Requirements:

- Python 3.12+
- `uv`
- Helm 3
- Docker
- Access to a Kubernetes cluster for integration testing

Run the local checks before opening a pull request:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
helm lint charts/kubevoip
helm template kubevoip charts/kubevoip >/dev/null
```

Keep changes focused. Add tests for behavioral changes. Treat every `v1alpha1`
API change as a compatibility decision that needs documentation.

## Pull requests

Describe user-visible behavior, testing, and any compatibility or networking
impact. All required GitHub Actions checks must pass before a pull request is
merged.
