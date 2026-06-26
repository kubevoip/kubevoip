from pathlib import Path

import yaml


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


def test_chart_uses_namespace_scoped_rbac():
    root = Path(__file__).parents[1]
    rbac = (root / "charts/kubevoip/templates/rbac.yaml").read_text()
    deployment = (root / "charts/kubevoip/templates/deployment.yaml").read_text()
    dockerfile = (root / "Dockerfile").read_text()

    assert "kind: Role\n" in rbac
    assert "kind: RoleBinding\n" in rbac
    assert "kind: ClusterRole\n" in rbac
    assert "kind: ClusterRoleBinding\n" in rbac
    assert 'resources: ["secrets"]' not in rbac
    assert 'resources: ["configmaps", "secrets", "services", "pods"]' in rbac
    assert 'resources: ["namespaces"]' in rbac
    assert 'resources: ["customresourcedefinitions"]' in rbac
    assert "--namespace={{ .Release.Namespace }}" in deployment
    assert "--all-namespaces" not in dockerfile


def test_operator_image_includes_alembic_migrations():
    root = Path(__file__).parents[1]
    dockerfile = (root / "Dockerfile").read_text()
    pyproject = (root / "pyproject.toml").read_text()

    assert "COPY database /app/database" in dockerfile
    assert "uv pip install --system --no-cache ." in dockerfile
    assert "RUN pip install" not in dockerfile
    assert '"database" = "database"' in pyproject
    assert (root / "database/alembic.ini").exists()
    assert (root / "database/env.py").exists()
    assert (root / "database/versions/0001_runtime_schema.py").exists()
    assert not (root / "database/versions/0001_kamailio_subscriber.py").exists()
    assert not (root / "database/versions/0002_runtime_routing.py").exists()


def test_operator_package_includes_render_templates():
    root = Path(__file__).parents[1]

    assert (root / "kubevoip/templates/kamailio.cfg.j2").exists()
    assert (root / "kubevoip/templates/asterisk/pjsip.conf.j2").exists()
    assert (root / "kubevoip/templates/asterisk/extensions.conf.j2").exists()
    assert (root / "kubevoip/templates/asterisk/rtp.conf.j2").exists()
    assert (root / "kubevoip/templates/asterisk/logger.conf.j2").exists()


def test_discovery_rbac_names_include_release_namespace():
    import subprocess

    root = Path(__file__).parents[1]

    first = subprocess.run(
        ["helm", "template", "kubevoip", "charts/kubevoip", "--namespace", "asterisk-demo"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    second = subprocess.run(
        ["helm", "template", "kubevoip", "charts/kubevoip", "--namespace", "kubevoip-platform"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )

    first_docs = list(yaml.safe_load_all(first.stdout))
    second_docs = list(yaml.safe_load_all(second.stdout))

    first_cluster_roles = {
        item["metadata"]["name"]
        for item in first_docs
        if item and item.get("kind") in {"ClusterRole", "ClusterRoleBinding"}
    }
    second_cluster_roles = {
        item["metadata"]["name"]
        for item in second_docs
        if item and item.get("kind") in {"ClusterRole", "ClusterRoleBinding"}
    }

    assert first_cluster_roles == {"kubevoip-kubevoip-asterisk-demo-discovery"}
    assert second_cluster_roles == {"kubevoip-kubevoip-kubevoip-platform-discovery"}
    assert first_cluster_roles.isdisjoint(second_cluster_roles)
