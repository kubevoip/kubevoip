import os
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def helm_template(*args, check=True):
    return subprocess.run(
        ["helm", "template", "kubevoip", "charts/kubevoip", *args],
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def render_docs(*args):
    result = helm_template(*args)
    return [item for item in yaml.safe_load_all(result.stdout) if item]


def rendered_kind(docs, kind):
    return [item for item in docs if item.get("kind") == kind]


def test_platform_crd_copies_are_semantically_identical():
    standalone = list(yaml.safe_load_all((ROOT / "config/crd/platform-crds.yaml").read_text()))
    chart = list(yaml.safe_load_all((ROOT / "charts/kubevoip/crds/platform-crds.yaml").read_text()))
    assert standalone == chart
    assert all(item["spec"]["group"] == "kubevoip.com" for item in standalone)
    assert all("x-kubernetes-preserve-unknown-fields" not in item["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"] for item in standalone)


def test_chart_includes_kopf_peering_crds():
    crds = list(yaml.safe_load_all((ROOT / "charts/kubevoip/crds/kopf-peering-crds.yaml").read_text()))
    names = {item["metadata"]["name"]: item for item in crds}

    assert names["clusterkopfpeerings.kopf.dev"]["spec"]["scope"] == "Cluster"
    assert names["kopfpeerings.kopf.dev"]["spec"]["scope"] == "Namespaced"
    assert all(item["spec"]["group"] == "kopf.dev" for item in crds)


def test_workflows_are_valid_yaml():
    for workflow in (ROOT / ".github/workflows").glob("*.yaml"):
        assert yaml.safe_load(workflow.read_text())


def test_chart_uses_namespace_scoped_rbac():
    rbac = (ROOT / "charts/kubevoip/templates/rbac.yaml").read_text()
    deployment = (ROOT / "charts/kubevoip/templates/deployment.yaml").read_text()
    dockerfile = (ROOT / "Dockerfile").read_text()

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


def test_default_render_keeps_single_operator_without_peering():
    docs = render_docs("--namespace", "telephony")

    deployment = rendered_kind(docs, "Deployment")[0]
    assert deployment["spec"]["replicas"] == 1
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container["args"] == ["--namespace=telephony"]
    assert "command" not in container
    assert rendered_kind(docs, "KopfPeering") == []
    assert all(
        "kopfpeerings" not in rule.get("resources", [])
        for role in rendered_kind(docs, "Role")
        for rule in role["rules"]
    )


def test_ha_render_adds_peering_wrapper_rbac_and_preferred_anti_affinity():
    docs = render_docs(
        "--namespace",
        "telephony",
        "--set",
        "operator.highAvailability.enabled=true",
        "--set",
        "operator.replicas=3",
    )

    deployment = rendered_kind(docs, "Deployment")[0]
    assert deployment["spec"]["replicas"] == 3
    pod_spec = deployment["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    script = container["args"][0]

    assert container["command"] == ["/bin/sh", "-ec"]
    assert "--namespace=telephony" in script
    assert "--peering=kubevoip-kubevoip" in script
    assert "--priority=\"$priority\"" in script
    assert "ipaddress.ip_address" in script
    assert "Pod-IP-derived priorities are probabilistically unique" in script
    assert "normally 2 or 3" in script
    assert ": \"${POD_IP:?POD_IP is required for Kopf HA priority}\"" in script
    assert "''|*[!0-9]*)" in script
    assert any(env["name"] == "POD_IP" for env in container["env"])

    peering = rendered_kind(docs, "KopfPeering")[0]
    assert peering["metadata"]["name"] == "kubevoip-kubevoip"
    assert peering["metadata"]["namespace"] == "telephony"

    peering_rule = next(
        rule
        for role in rendered_kind(docs, "Role")
        for rule in role["rules"]
        if rule["apiGroups"] == ["kopf.dev"]
    )
    assert peering_rule["resources"] == ["kopfpeerings"]
    assert peering_rule["verbs"] == ["get", "list", "watch", "create", "patch", "update"]

    anti_affinity = pod_spec["affinity"]["podAntiAffinity"]
    assert "preferredDuringSchedulingIgnoredDuringExecution" in anti_affinity
    assert "requiredDuringSchedulingIgnoredDuringExecution" not in anti_affinity


def test_ha_peering_name_can_be_overridden():
    docs = render_docs(
        "--namespace",
        "telephony",
        "--set",
        "operator.highAvailability.enabled=true",
        "--set",
        "operator.replicas=2",
        "--set",
        "operator.highAvailability.peeringName=custom-peer",
    )

    script = rendered_kind(docs, "Deployment")[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]
    peering = rendered_kind(docs, "KopfPeering")[0]
    assert "--peering=custom-peer" in script
    assert peering["metadata"]["name"] == "custom-peer"


def test_render_fails_for_multiple_operator_replicas_without_ha():
    result = helm_template("--set", "operator.replicas=2", check=False)

    assert result.returncode != 0
    assert "operator.replicas > 1 requires operator.highAvailability.enabled=true" in result.stderr


def test_ha_priority_python_accepts_valid_pod_ip_and_rejects_invalid_pod_ip():
    docs = render_docs(
        "--set",
        "operator.highAvailability.enabled=true",
        "--set",
        "operator.replicas=3",
    )
    script = rendered_kind(docs, "Deployment")[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]
    match = re.search(r"python - <<'PY'\n(?P<code>.*?)\nPY", script, re.DOTALL)
    assert match
    code = match.group("code")

    env = {**os.environ, "POD_IP": "10.244.0.12"}
    valid = subprocess.run(["python", "-c", code], check=True, text=True, capture_output=True, env=env)
    assert valid.stdout.strip().isdigit()
    assert 1 <= int(valid.stdout.strip()) <= 32767

    invalid_env = {**os.environ, "POD_IP": "not-an-ip"}
    invalid = subprocess.run(["python", "-c", code], check=False, text=True, capture_output=True, env=invalid_env)
    assert invalid.returncode != 0
    assert "invalid POD_IP for Kopf HA priority" in invalid.stderr


def test_operator_image_includes_alembic_migrations():
    dockerfile = (ROOT / "Dockerfile").read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert "COPY database /app/database" in dockerfile
    assert "uv pip install --system --no-cache ." in dockerfile
    assert "RUN pip install" not in dockerfile
    assert '"database" = "database"' in pyproject
    assert (ROOT / "database/alembic.ini").exists()
    assert (ROOT / "database/env.py").exists()
    assert (ROOT / "database/versions/0001_runtime_schema.py").exists()
    assert not (ROOT / "database/versions/0001_kamailio_subscriber.py").exists()
    assert not (ROOT / "database/versions/0002_runtime_routing.py").exists()


def test_operator_package_includes_render_templates():
    assert (ROOT / "kubevoip/templates/kamailio.cfg.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/pjsip.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/extensions.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/rtp.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/logger.conf.j2").exists()


def test_discovery_rbac_names_include_release_namespace():
    first = helm_template("--namespace", "asterisk-demo")
    second = helm_template("--namespace", "kubevoip-platform")

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
