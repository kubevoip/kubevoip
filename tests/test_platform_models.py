import pytest
from pydantic import ValidationError

from kubevoip.models import (
    AsteriskPoolSpec,
    CallRouteSpec,
    CallScopeSpec,
    DialPolicySpec,
    MediaRelaySpec,
    NetworkProfileSpec,
    RouteMatch,
    RouteTarget,
    SIPGatewaySpec,
    SIPTrunkSpec,
    SIPUserSpec,
    VoicemailMailboxSpec,
)


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


def test_gateway_rejects_nested_trunks_and_routes():
    with pytest.raises(ValidationError):
        SIPGatewaySpec.model_validate(
            {
                "databaseSecretRef": {"name": "db"},
                "networkProfileRef": {"name": "public"},
                "mediaRelayRef": {"name": "home"},
                "trunks": [{"name": "provider-primary", "terminationUri": "provider.example.net"}],
            }
        )
    with pytest.raises(ValidationError):
        SIPGatewaySpec.model_validate(
            {
                "databaseSecretRef": {"name": "db"},
                "networkProfileRef": {"name": "public"},
                "mediaRelayRef": {"name": "home"},
                "routes": [{"match": {"calledNumber": "+61..."}, "target": {"trunkRef": "provider-primary"}}],
            }
        )


def test_sip_trunk_validates_provider_neutral_digest_auth():
    spec = SIPTrunkSpec.model_validate(
        {
            "gatewayRef": {"name": "home"},
            "terminationUri": "provider.example.net",
            "inbound": {"allowedSourceCidrs": ["203.0.113.0/24"], "dialPolicyRef": {"name": "external"}},
            "outbound": {
                "callerIdSecretRef": {"name": "caller-id", "key": "value"},
                "authentication": {
                    "mode": "Digest",
                    "digest": {
                        "usernameSecretRef": {"name": "trunk-auth", "key": "username"},
                        "passwordSecretRef": {"name": "trunk-auth", "key": "password"},
                        "realm": "provider.example.net",
                    },
                },
            },
        }
    )
    assert spec.gateway_ref.name == "home"
    assert spec.outbound.authentication.digest.username_secret_ref.key == "username"
    with pytest.raises(ValidationError):
        SIPTrunkSpec.model_validate(
            {
                "gatewayRef": {"name": "home"},
                "terminationUri": "provider.example.net",
                "inbound": {"allowedSourceCidrs": ["invalid"]},
            }
        )
    with pytest.raises(ValidationError):
        SIPTrunkSpec.model_validate(
            {
                "gatewayRef": {"name": "home"},
                "terminationUri": "provider.example.net",
                "inbound": {"allowedSourceCidrs": ["203.0.113.0/24"]},
            }
        )
    with pytest.raises(ValidationError):
        SIPTrunkSpec.model_validate(
            {
                "gatewayRef": {"name": "home"},
                "terminationUri": "provider.example.net",
                "outbound": {"authentication": {"mode": "Digest"}},
            }
        )


def test_call_route_preserves_current_matching_and_targets():
    route = CallRouteSpec.model_validate(
        {
            "gatewayRef": {"name": "home"},
            "scopeRef": {"name": "external"},
            "priority": 10,
            "match": {"calledNumber": "+61..."},
            "target": {"trunkRef": "provider-primary"},
        }
    )
    assert route.match.called_number == "+61..."
    assert route.target.trunk_ref == "provider-primary"
    with pytest.raises(ValidationError):
        CallRouteSpec.model_validate(
            {
                "gatewayRef": {"name": "home"},
                "scopeRef": {"name": "internal"},
                "match": {"calledNumber": "600"},
                "target": {"asteriskPoolRef": "applications"},
            }
        )


def test_call_scope_dial_policy_and_user_policy_refs_validate():
    scope = CallScopeSpec.model_validate({"gatewayRef": {"name": "home"}})
    policy = DialPolicySpec.model_validate(
        {"gatewayRef": {"name": "home"}, "scopes": [{"name": "internal"}, {"name": "external"}]}
    )
    user = SIPUserSpec.model_validate(
        {
            "gatewayRef": {"name": "home"},
            "dialPolicyRef": {"name": "internal-external"},
            "extension": "100",
            "authUsername": "daniel",
            "passwordSecretRef": {"name": "daniel-sip", "key": "password"},
        }
    )
    assert scope.gateway_ref.name == "home"
    assert [item.name for item in policy.scopes] == ["internal", "external"]
    assert user.dial_policy_ref.name == "internal-external"
    with pytest.raises(ValidationError):
        DialPolicySpec.model_validate({"gatewayRef": {"name": "home"}, "scopes": [{"name": "internal"}, {"name": "internal"}]})


def test_gateway_service_validation_remains_provider_neutral():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
        }
    )
    assert spec.media_relay_ref.name == "home"
    with pytest.raises(ValidationError):
        SIPGatewaySpec.model_validate(
            {
                "databaseSecretRef": {"name": "db"},
                "networkProfileRef": {"name": "public"},
                "mediaRelayRef": {"name": "home"},
                "service": {"type": "NodePort"},
            }
        )


def test_gateway_homer_capture_validation():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
            "observability": {"capture": {"enabled": True, "hepAddress": "homer.telemetry.svc", "captureMode": "dialog"}},
        }
    )
    assert spec.observability.capture.enabled is True
    assert spec.observability.capture.type == "Homer"
    assert spec.observability.capture.hep_port == 9060
    assert spec.observability.capture.capture_mode == "dialog"
    with pytest.raises(ValidationError):
        SIPGatewaySpec.model_validate(
            {
                "databaseSecretRef": {"name": "db"},
                "networkProfileRef": {"name": "public"},
                "mediaRelayRef": {"name": "home"},
                "observability": {"capture": {"enabled": True, "hepPort": 0}},
            }
        )
    with pytest.raises(ValidationError):
        SIPGatewaySpec.model_validate(
            {
                "databaseSecretRef": {"name": "db"},
                "networkProfileRef": {"name": "public"},
                "mediaRelayRef": {"name": "home"},
                "observability": {"capture": {"enabled": True, "includePayload": False}},
            }
        )


def test_gateway_sip_header_logging_validation():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
            "observability": {"sipHeaders": {"enabled": True}},
        }
    )
    assert spec.observability.sip_headers.enabled is True


def test_gateway_sdp_logging_validation():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
            "observability": {"sdp": {"enabled": True}},
        }
    )
    assert spec.observability.sdp.enabled is True


def test_asterisk_pool_voicemail_requires_database_ref():
    spec = AsteriskPoolSpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "applications": {"voicemail": {"enabled": True, "mainExtension": "700", "mainMailbox": "100", "depositExtension": "701"}},
        }
    )
    assert spec.applications.voicemail.enabled is True
    assert spec.applications.voicemail.main_mailbox == "100"
    assert spec.database_secret_ref.name == "db"
    with pytest.raises(ValidationError):
        AsteriskPoolSpec.model_validate({"applications": {"voicemail": {"enabled": True}}})
    with pytest.raises(ValidationError):
        AsteriskPoolSpec.model_validate(
            {
                "databaseSecretRef": {"name": "db"},
                "applications": {"voicemail": {"enabled": True, "mainExtension": "700", "depositExtension": "700"}},
            }
        )


def test_voicemail_mailbox_validates_email_and_fallback():
    spec = VoicemailMailboxSpec.model_validate(
        {
            "sipUserRef": {"name": "daniel"},
            "asteriskPoolRef": {"name": "applications"},
            "email": {
                "enabled": True,
                "to": "daniel@example.com",
                "from": "voicemail@example.com",
                "apiKeySecretRef": {"name": "sendgrid", "key": "api-key"},
            },
            "fallback": {"enabled": True, "timeoutSeconds": 15},
        }
    )
    assert spec.mailbox is None
    assert spec.email.provider == "SendGrid"
    assert spec.fallback.on_no_answer is True
    with pytest.raises(ValidationError):
        VoicemailMailboxSpec.model_validate(
            {
                "sipUserRef": {"name": "daniel"},
                "asteriskPoolRef": {"name": "applications"},
                "email": {"enabled": True, "to": "daniel@example.com"},
            }
        )
    with pytest.raises(ValidationError):
        VoicemailMailboxSpec.model_validate(
            {
                "sipUserRef": {"name": "daniel"},
                "asteriskPoolRef": {"name": "applications"},
                "fallback": {"enabled": True, "onBusy": False, "onUnavailable": False, "onNoAnswer": False},
            }
        )


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
