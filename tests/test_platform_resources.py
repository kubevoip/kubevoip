from kubevoip.models import AsteriskPoolSpec, MediaRelaySpec
from kubevoip.platform_controller import resolve_external_address
from kubevoip.platform_resources import (
    build_asterisk_pool_resources,
    build_media_relay_resources,
    partition_range,
)

OWNER = {
    "apiVersion": "kubevoip.com/v1alpha1",
    "kind": "MediaRelay",
    "metadata": {"name": "home", "namespace": "test", "uid": "uid"},
}


def test_partition_range_is_complete_and_non_overlapping():
    assert partition_range(20000, 20004, 2) == [(20000, 20002), (20003, 20004)]


def test_external_address_precedence():
    assert resolve_external_address("replica", "component", "profile", "service") == (
        "replica",
        "ReplicaOverride",
    )
    assert resolve_external_address(None, "component", "profile", "service") == (
        "component",
        "ComponentOverride",
    )
    assert resolve_external_address(None, None, "profile", "service") == ("profile", "NetworkProfile")
    assert resolve_external_address(None, None, None, "service") == ("service", "Service")


def test_media_relay_builds_stable_service_per_replica():
    spec = MediaRelaySpec.model_validate(
        {
            "replicas": 2,
            "networkProfileRef": {"name": "public"},
            "media": {"start": 20000, "end": 20003},
        }
    )
    resources = build_media_relay_resources("home", "test", OWNER, spec, ["one.example", "two.example"])
    services = [item for item in resources if item["kind"] == "Service"]
    deployments = [item for item in resources if item["kind"] == "Deployment"]
    assert [item["metadata"]["name"] for item in services] == ["home-rtpengine-0", "home-rtpengine-1"]
    assert [port["port"] for port in services[0]["spec"]["ports"]] == [2223, 20000, 20001]
    assert "--table=-1" in deployments[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]


def test_asterisk_pool_uses_private_headless_service():
    owner = {**OWNER, "kind": "AsteriskPool"}
    resources = build_asterisk_pool_resources("apps", "test", owner, AsteriskPoolSpec(replicas=2))
    service = next(item for item in resources if item["kind"] == "Service")
    statefulset = next(item for item in resources if item["kind"] == "StatefulSet")
    assert service["spec"]["clusterIP"] == "None"
    assert statefulset["spec"]["replicas"] == 2
    assert "kubevoip.com/config-hash" in statefulset["spec"]["template"]["metadata"]["annotations"]
