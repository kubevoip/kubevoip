import pytest

from kubevoip import platform_controller
from kubevoip.controller import WaitingForLoadBalancerError
from kubevoip.platform_controller import reconcile_call_route_controller, reconcile_gateway, reconcile_media_relay, reconcile_sip_trunk_controller

PROFILE = {
    "apiVersion": "kubevoip.com/v1alpha1",
    "kind": "NetworkProfile",
    "metadata": {"name": "public", "namespace": "test"},
    "spec": {"externalAddress": {"source": "Service"}},
}


class FakeKubernetes:
    def __init__(self, ingresses=None, custom=None, secrets=None):
        self.applied = []
        self.ingresses = ingresses or {}
        self.custom = custom or {}
        self.secrets = secrets or {}

    def apply(self, resource):
        self.applied.append(resource)

    def read_custom(self, namespace, plural, name):
        if (namespace, plural, name) == ("test", "networkprofiles", "public"):
            return PROFILE
        return self.custom[(namespace, plural, name)]

    def list_custom(self, namespace, plural):
        return [
            item
            for (item_namespace, item_plural, _name), item in self.custom.items()
            if item_namespace == namespace and item_plural == plural
        ]

    def read_secret(self, namespace, name, key):
        return self.secrets[(namespace, name, key)]

    def read_secret_values(self, namespace, name):
        return self.secrets[(namespace, name)]

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


def test_gateway_uses_static_config_and_database_runtime_data(monkeypatch):
    monkeypatch.setattr(platform_controller, "database_ready", lambda _database: None)
    custom = {
        (
            "test",
            "mediarelays",
            "home",
        ): {"status": {"relays": [{"service": "home-rtpengine-0"}]}},
    }
    api = FakeKubernetes(custom=custom, secrets={("test", "db"): {"host": "postgres", "port": "5432", "dbname": "kubevoip", "user": "app", "password": "secret"}})
    body = {
        "apiVersion": "kubevoip.com/v1alpha1",
        "kind": "SIPGateway",
        "metadata": {"name": "home", "namespace": "test", "uid": "uid"},
    }
    spec = {
        "databaseSecretRef": {"name": "db"},
        "networkProfileRef": {"name": "public"},
        "mediaRelayRef": {"name": "home"},
    }

    status = reconcile_gateway(body, spec, api)

    config = next(resource for resource in api.applied if resource["kind"] == "ConfigMap")["data"]["kamailio.cfg"]
    runtime_condition = next(condition for condition in status["conditions"] if condition["type"] == "RuntimeDataReady")
    assert status["phase"] == "Ready"
    assert runtime_condition["reason"] == "DatabaseBacked"
    assert "kubevoip_call_route" in config
    assert "provider.example.net" not in config


def test_sip_trunk_and_call_route_statuses_validate_references(monkeypatch):
    calls = {}
    monkeypatch.setattr(platform_controller, "reconcile_sip_trunk", lambda *args: calls.setdefault("trunk", args))
    monkeypatch.setattr(platform_controller, "reconcile_call_route", lambda *args: calls.setdefault("route", args))
    custom = {
        (
            "test",
            "sipgateways",
            "home",
        ): {"spec": {"databaseSecretRef": {"name": "db"}, "networkProfileRef": {"name": "public"}, "mediaRelayRef": {"name": "home"}}},
        ("test", "sipusers", "daniel"): {"spec": {}},
        ("test", "siptrunks", "provider-primary"): {"spec": {}},
        ("test", "callscopes", "internal"): {"spec": {"gatewayRef": {"name": "home"}}},
        ("test", "callscopes", "external"): {"spec": {"gatewayRef": {"name": "home"}}},
        ("test", "dialpolicies", "external"): {"spec": {"gatewayRef": {"name": "home"}, "scopes": [{"name": "external"}]}},
    }
    secrets = {
        ("test", "db"): {"host": "postgres", "port": "5432", "dbname": "kubevoip", "user": "app", "password": "secret"},
        ("test", "caller-id", "value"): "+15551234567",
        ("test", "provider-auth", "username"): "user",
        ("test", "provider-auth", "password"): "password",
    }
    api = FakeKubernetes(custom=custom, secrets=secrets)
    trunk_status = reconcile_sip_trunk_controller(
        {"metadata": {"name": "provider-primary", "namespace": "test", "generation": 1}},
            {
                "gatewayRef": {"name": "home"},
                "terminationUri": "provider.example.net",
                "inbound": {"allowedSourceCidrs": ["203.0.113.0/24"], "dialPolicyRef": {"name": "external"}},
                "outbound": {
                    "callerIdSecretRef": {"name": "caller-id", "key": "value"},
                    "authentication": {
                    "mode": "Digest",
                        "digest": {
                            "usernameSecretRef": {"name": "provider-auth", "key": "username"},
                            "passwordSecretRef": {"name": "provider-auth", "key": "password"},
                            "realm": "provider.example.net",
                        },
                    },
                },
        },
        api,
    )
    route_status = reconcile_call_route_controller(
        {"metadata": {"name": "inbound", "namespace": "test", "generation": 1}},
        {"gatewayRef": {"name": "home"}, "scopeRef": {"name": "internal"}, "match": {"calledNumber": "100"}, "target": {"sipUserRef": "daniel"}},
        api,
    )
    assert trunk_status["phase"] == "Ready"
    assert route_status["phase"] == "Ready"
    assert calls["trunk"][11] == platform_controller.trunk_digest_ha1("user", "provider.example.net", "password")
    assert calls["route"][4:8] == ("home", "internal", 1000, "100")
