# Contributing

KubeVoIP welcomes bug reports, documentation improvements,
tests, and focused feature proposals are welcome.

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

Keep changes focused, add tests for behavioral changes, and treat every
`v1alpha1` API change as a compatibility decision that requires documentation.

## Pull Requests

Describe the user-visible behavior, testing performed, and any compatibility or
networking implications. All required GitHub Actions checks must pass before a
pull request is merged.
