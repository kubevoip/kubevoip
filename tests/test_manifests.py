from pathlib import Path

import yaml


def test_crd_copies_are_semantically_identical():
    root = Path(__file__).parents[1]
    standalone = yaml.safe_load((root / "config/crd/asterisk-crd.yaml").read_text())
    chart = yaml.safe_load((root / "charts/kubevoip/crds/asterisk-crd.yaml").read_text())
    assert standalone == chart


def test_workflows_are_valid_yaml():
    root = Path(__file__).parents[1]
    for workflow in (root / ".github/workflows").glob("*.yaml"):
        assert yaml.safe_load(workflow.read_text())
