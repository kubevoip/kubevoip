# Contributing

KubeVoIP welcomes bug reports, documentation fixes, tests, and focused feature
proposals.

## Development

Requirements:

- Python 3.12+
- `uv`
- Docker
- Access to a Kubernetes cluster for integration testing

Run the local checks before opening a pull request:

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
```

Helm chart source and chart rendering tests live in
[`kubevoip/charts`](https://github.com/kubevoip/charts).

Keep changes focused. Add tests for behavioral changes. Treat every `v1alpha1`
API change as a compatibility decision that needs documentation.

## Releases

Use `bump-my-version` from a clean working tree for platform release bumps:

```bash
uv run bump-my-version bump patch
git push origin main
```

The bump command updates the configured version files and creates the release
commit. It does not create a Git tag. After CI passes on `main`, create and push
the release tag:

```bash
git tag -a vX.Y.Z -m "KubeVoIP vX.Y.Z"
git push origin vX.Y.Z
```

## Pull requests

Describe user-visible behavior, testing, and any compatibility or networking
impact. All required GitHub Actions checks must pass before a pull request is
merged.
