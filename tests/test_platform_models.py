import pytest
from pydantic import ValidationError

from kubevoip.models import MediaRelaySpec, NetworkProfileSpec, RouteMatch, RouteTarget, SIPGatewaySpec


def test_network_profile_validates_cidrs():
    profile = NetworkProfileSpec.model_validate({"externalAddress": {"value": "sip.example.com"}, "localNetworks": ["10.0.0.0/8"]})
    assert profile.external_address.value == "sip.example.com"
    with pytest.raises(ValidationError):
        NetworkProfileSpec.model_validate({"externalAddress": {"value": "sip.example.com"}, "localNetworks": ["invalid"]})


def test_media_relay_validates_replica_overrides():
    spec = MediaRelaySpec.model_validate(
        {
            "replicas": 2,
            "networkProfileRef": {"name": "public"},
            "media": {"start": 20000, "end": 20039},
            "network": {"replicaOverrides": [{"replica": 1, "externalAddress": "203.0.113.2"}]},
        }
    )
    assert spec.replicas == 2
    with pytest.raises(ValidationError):
        MediaRelaySpec.model_validate(
            {
                "replicas": 2,
                "networkProfileRef": {"name": "public"},
                "media": {"start": 20000, "end": 20039},
                "network": {"replicaOverrides": [{"replica": 2, "externalAddress": "203.0.113.2"}]},
            }
        )


def test_route_target_requires_exactly_one_target():
    assert RouteTarget.model_validate({"sipUserRef": "daniel"}).sip_user_ref == "daniel"
    with pytest.raises(ValidationError):
        RouteTarget.model_validate({"sipUserRef": "daniel", "asteriskPoolRef": "apps", "extension": "600"})


def test_gateway_routes_only_reference_declared_trunks():
    base = {
        "databaseSecretRef": {"name": "db"},
        "networkProfileRef": {"name": "public"},
        "mediaRelayRef": {"name": "home"},
        "trunks": [{"name": "twilio", "terminationUri": "example.pstn.twilio.com"}],
        "routes": [{"match": {"calledNumber": "+61..."}, "target": {"trunkRef": "twilio"}}],
    }
    assert SIPGatewaySpec.model_validate(base).routes[0].target.trunk_ref == "twilio"
    base["routes"][0]["target"]["trunkRef"] = "missing"
    with pytest.raises(ValidationError):
        SIPGatewaySpec.model_validate(base)


def test_addresses_and_routes_reject_configuration_injection():
    with pytest.raises(ValidationError):
        NetworkProfileSpec.model_validate({"externalAddress": {"value": 'example.com"\nloadmodule "evil.so'}})
    with pytest.raises(ValidationError):
        RouteMatch.model_validate({"calledNumber": '600") { exit; }'})


def test_media_relay_rejects_nodeport_and_oversized_ranges():
    base = {
        "networkProfileRef": {"name": "public"},
        "media": {"start": 20000, "end": 20099},
    }
    with pytest.raises(ValidationError):
        MediaRelaySpec.model_validate({**base, "network": {"service": {"type": "NodePort"}}})
    with pytest.raises(ValidationError):
        MediaRelaySpec.model_validate(
            {
                "networkProfileRef": {"name": "public"},
                "media": {"start": 20000, "end": 22000},
            }
        )
