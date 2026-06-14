import base64

from kubevoip.models import AsteriskSpec
from kubevoip.resources import build_resources

OWNER = {
    "apiVersion": "kubevoip.io/v1alpha1",
    "kind": "Asterisk",
    "metadata": {"name": "demo", "namespace": "test", "uid": "uid"},
}


def test_resources_share_access_service_and_mount_secret():
    spec = AsteriskSpec.model_validate({"rtp": {"start": 10000, "end": 10002}})
    configs = {"pjsip.conf": "secret", "extensions.conf": "dialplan", "rtp.conf": "rtp"}
    resources = build_resources("demo", "test", OWNER, spec, configs, "hash")
    kinds = [item["kind"] for item in resources]
    assert kinds == ["Secret", "ConfigMap", "Service", "Service", "StatefulSet"]
    assert base64.b64decode(resources[0]["data"]["pjsip.conf"]) == b"secret"
    assert "stringData" not in resources[0]
    access = resources[3]
    assert [port["port"] for port in access["spec"]["ports"]] == [5060, 10000, 10001, 10002]
    statefulset = resources[4]
    assert statefulset["spec"]["template"]["metadata"]["annotations"]["kubevoip.io/config-hash"] == "hash"


def test_all_resources_have_controller_owner_reference():
    spec = AsteriskSpec.model_validate({"rtp": {"start": 10000, "end": 10000}})
    configs = {"pjsip.conf": "secret", "extensions.conf": "dialplan", "rtp.conf": "rtp"}
    for resource in build_resources("demo", "test", OWNER, spec, configs, "hash"):
        owner = resource["metadata"]["ownerReferences"][0]
        assert owner["uid"] == "uid"
        assert owner["controller"] is True
