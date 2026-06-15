from pathlib import Path

import yaml


def test_crd_copies_are_semantically_identical():
    root = Path(__file__).parents[1]
    standalone = yaml.safe_load((root / "config/crd/asterisk-crd.yaml").read_text())
    chart = yaml.safe_load((root / "charts/kubevoip/crds/asterisk-crd.yaml").read_text())
    assert standalone == chart


def test_platform_crd_copies_are_semantically_identical():
    root = Path(__file__).parents[1]
    standalone = list(yaml.safe_load_all((root / "config/crd/platform-crds.yaml").read_text()))
    chart = list(yaml.safe_load_all((root / "charts/kubevoip/crds/platform-crds.yaml").read_text()))
    assert standalone == chart
    assert all(item["spec"]["group"] == "kubevoip.com" for item in standalone)
    assert all("x-kubernetes-preserve-unknown-fields" not in item["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"] for item in standalone)


def test_workflows_are_valid_yaml():
    root = Path(__file__).parents[1]
    for workflow in (root / ".github/workflows").glob("*.yaml"):
        assert yaml.safe_load(workflow.read_text())
