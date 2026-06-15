import pytest

from kubevoip.controller import WaitingForLoadBalancerError
from kubevoip.platform_controller import reconcile_gateway, reconcile_media_relay

PROFILE = {
    "apiVersion": "kubevoip.com/v1alpha1",
    "kind": "NetworkProfile",
    "metadata": {"name": "public", "namespace": "test"},
    "spec": {"externalAddress": {"source": "Service"}},
}


class FakeKubernetes:
    def __init__(self, ingresses=None):
        self.applied = []
        self.ingresses = ingresses or {}

    def apply(self, resource):
        self.applied.append(resource)

    def read_custom(self, namespace, plural, name):
        assert (namespace, plural, name) == ("test", "networkprofiles", "public")
        return PROFILE

    def service_ingress(self, namespace, name):
        return self.ingresses.get(name)

    def ready_deployment_replicas(self, namespace, name):
        return 1


def test_media_relay_creates_load_balancer_services_before_waiting_for_ingress():
    api = FakeKubernetes()
    body = {
        "apiVersion": "kubevoip.com/v1alpha1",
        "kind": "MediaRelay",
        "metadata": {"name": "home", "namespace": "test", "uid": "uid"},
    }
    spec = {
        "replicas": 2,
        "networkProfileRef": {"name": "public"},
        "media": {"start": 20000, "end": 20003},
        "network": {"service": {"type": "LoadBalancer"}},
    }

    with pytest.raises(
        WaitingForLoadBalancerError,
        match="waiting for LoadBalancer address for RTPengine replica 0",
    ):
        reconcile_media_relay(body, spec, api)

    assert [resource["metadata"]["name"] for resource in api.applied] == [
        "home-rtpengine-0",
        "home-rtpengine-1",
    ]
    assert all(resource["kind"] == "Service" for resource in api.applied)


def test_media_relay_finishes_reconciliation_after_load_balancer_addresses_resolve():
    api = FakeKubernetes(
        {
            "home-rtpengine-0": "203.0.113.10",
            "home-rtpengine-1": "203.0.113.11",
        }
    )
    body = {
        "apiVersion": "kubevoip.com/v1alpha1",
        "kind": "MediaRelay",
        "metadata": {"name": "home", "namespace": "test", "uid": "uid"},
    }
    spec = {
        "replicas": 2,
        "networkProfileRef": {"name": "public"},
        "media": {"start": 20000, "end": 20003},
        "network": {"service": {"type": "LoadBalancer"}},
    }

    status = reconcile_media_relay(body, spec, api)

    assert status["phase"] == "Ready"
    assert [relay["externalAddress"] for relay in status["relays"]] == [
        "203.0.113.10",
        "203.0.113.11",
    ]
    assert [resource["kind"] for resource in api.applied].count("Deployment") == 2


def test_gateway_creates_load_balancer_service_before_waiting_for_ingress():
    api = FakeKubernetes()
    body = {
        "apiVersion": "kubevoip.com/v1alpha1",
        "kind": "SIPGateway",
        "metadata": {"name": "home", "namespace": "test", "uid": "uid"},
    }
    spec = {
        "databaseSecretRef": {"name": "db"},
        "networkProfileRef": {"name": "public"},
        "mediaRelayRef": {"name": "home"},
        "service": {"type": "LoadBalancer"},
    }

    with pytest.raises(
        WaitingForLoadBalancerError,
        match="waiting for LoadBalancer address for SIP gateway",
    ):
        reconcile_gateway(body, spec, api)

    assert [resource["metadata"]["name"] for resource in api.applied] == [
        "home-sip-gateway",
    ]
    assert api.applied[0]["kind"] == "Service"
