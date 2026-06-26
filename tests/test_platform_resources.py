from kubevoip.models import AsteriskPoolSpec, MediaRelaySpec, SIPGatewaySpec
from kubevoip.platform_controller import resolve_external_address
from kubevoip.platform_resources import (
    build_asterisk_pool_resources,
    build_gateway_resources,
    build_gateway_service,
    build_media_relay_resources,
    build_media_relay_services,
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
    assert "--log-stderr" in deployments[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]
    assert "--log-level=6" in deployments[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]
    assert "--split-logs" in deployments[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]
    assert "kubevoip_rtp_event" in deployments[0]["spec"]["template"]["spec"]["containers"][0]["args"][0]


def test_media_relay_prefers_spreading_replicas_across_nodes():
    spec = MediaRelaySpec.model_validate(
        {
            "replicas": 2,
            "networkProfileRef": {"name": "public"},
            "media": {"start": 20000, "end": 20003},
        }
    )
    resources = build_media_relay_resources("home", "test", OWNER, spec, ["one.example", "two.example"])
    deployments = [item for item in resources if item["kind"] == "Deployment"]
    terms = [
        item["spec"]["template"]["spec"]["affinity"]["podAntiAffinity"]["preferredDuringSchedulingIgnoredDuringExecution"][0]
        for item in deployments
    ]
    assert [term["weight"] for term in terms] == [100, 100]
    assert all(term["podAffinityTerm"]["topologyKey"] == "kubernetes.io/hostname" for term in terms)
    assert all(
        term["podAffinityTerm"]["labelSelector"]["matchLabels"]
        == {
            "app.kubernetes.io/name": "rtpengine",
            "app.kubernetes.io/managed-by": "kubevoip",
            "app.kubernetes.io/part-of": "kubevoip",
        }
        for term in terms
    )


def test_media_relay_services_can_be_built_before_addresses_resolve():
    spec = MediaRelaySpec.model_validate(
        {
            "replicas": 2,
            "networkProfileRef": {"name": "public"},
            "media": {"start": 20000, "end": 20003},
            "network": {"service": {"type": "LoadBalancer"}},
        }
    )
    services = build_media_relay_services("home", "test", OWNER, spec)
    assert [item["metadata"]["name"] for item in services] == [
        "home-rtpengine-0",
        "home-rtpengine-1",
    ]
    assert all(item["spec"]["type"] == "LoadBalancer" for item in services)


def test_gateway_service_can_be_built_before_address_resolves():
    owner = {**OWNER, "kind": "SIPGateway"}
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
            "service": {"type": "LoadBalancer"},
        }
    )
    service = build_gateway_service("home", "test", owner, spec)
    assert service["metadata"]["name"] == "home-sip-gateway"
    assert service["spec"]["type"] == "LoadBalancer"


def test_gateway_resources_do_not_mount_trunk_secrets():
    owner = {**OWNER, "kind": "SIPGateway"}
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
        }
    )
    resources = build_gateway_resources("home", "test", owner, spec, "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    config = next(item for item in resources if item["kind"] == "ConfigMap")["data"]["kamailio.cfg"]
    deployment = next(item for item in resources if item["kind"] == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert "provider-auth" not in config
    assert "caller-id" not in config
    assert "env" not in container
    assert container["envFrom"] == [{"secretRef": {"name": "db"}}]


def test_asterisk_pool_uses_private_service_and_headless_identity():
    owner = {**OWNER, "kind": "AsteriskPool"}
    resources = build_asterisk_pool_resources("apps", "test", owner, AsteriskPoolSpec(replicas=2))
    services = {item["metadata"]["name"]: item for item in resources if item["kind"] == "Service"}
    statefulset = next(item for item in resources if item["kind"] == "StatefulSet")
    assert services["apps-asterisk-pool"]["spec"]["type"] == "ClusterIP"
    assert services["apps-asterisk-pool-headless"]["spec"]["clusterIP"] == "None"
    assert statefulset["spec"]["serviceName"] == "apps-asterisk-pool-headless"
    assert statefulset["spec"]["replicas"] == 2
    assert "kubevoip.com/config-hash" in statefulset["spec"]["template"]["metadata"]["annotations"]
    secret = next(item for item in resources if item["kind"] == "Secret")
    assert "logger.conf" in secret["data"]
    mounted = {
        mount["subPath"]
        for mount in statefulset["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]
    }
    assert "logger.conf" in mounted
