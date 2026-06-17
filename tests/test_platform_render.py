from kubevoip.models import CallRouteSpec, SIPGatewaySpec, SIPTrunkSpec
from kubevoip.platform_render import render_kamailio_config


def test_kamailio_renders_trusted_sources_and_outbound_trunk_routes():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
        }
    )
    trunks = {
        "provider-primary": SIPTrunkSpec.model_validate(
            {
                "gatewayRef": {"name": "home"},
                "terminationUri": "provider.example.net",
                "inbound": {"allowedSourceCidrs": ["203.0.113.0/24"]},
                "outbound": {"callerIdSecretRef": {"name": "caller-id", "key": "value"}},
            }
        )
    }
    routes = [
        (
            "outbound-au",
            CallRouteSpec.model_validate(
                {
                    "gatewayRef": {"name": "home"},
                    "match": {"calledNumber": "+61..."},
                    "target": {"trunkRef": "provider-primary"},
                }
            ),
        )
    ]
    rendered = render_kamailio_config(spec, "home", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"], {}, {}, trunks, routes)
    assert "src_ip == 203.0.113.0/24" in rendered
    assert 'starts_with($rU, "+61")' in rendered
    assert 'remove_hf("Route")' in rendered
    assert '$rd = "provider.example.net"' in rendered
    assert 'loadmodule "uac.so"' in rendered
    assert 'uac_replace_from("__KUBEVOIP_TRUNK_PROVIDER_PRIMARY_CALLER_ID__", "sip:__KUBEVOIP_TRUNK_PROVIDER_PRIMARY_CALLER_ID__@198.51.100.10")' in rendered
    assert "P-Asserted-Identity: <sip:__KUBEVOIP_TRUNK_PROVIDER_PRIMARY_CALLER_ID__@198.51.100.10>" in rendered
    assert '$du = "sip:provider.example.net"' in rendered
    assert "proxy_authorize" in rendered
    assert "loose_route()" in rendered
    assert "alias=ADVERTISED_ADDR:5060" in rendered
    assert "alias=INTERNAL_ADDR:5060" in rendered
    assert 'record_route_preset("10.0.0.10:5060;r2=on", "198.51.100.10:5060;r2=on")' in rendered
    assert 'record_route_preset("198.51.100.10:5060;r2=on", "10.0.0.10:5060;r2=on")' in rendered


def test_kamailio_uses_single_record_route_when_addresses_match():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
        }
    )
    rendered = render_kamailio_config(spec, "home", "198.51.100.10", "198.51.100.10", ["udp:rtpengine:2223"], {}, {})
    assert "record_route();" in rendered
    assert "record_route_preset" not in rendered


def test_kamailio_omits_outbound_caller_id_when_trunk_has_no_secret():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
        }
    )
    trunks = {"provider-primary": SIPTrunkSpec.model_validate({"gatewayRef": {"name": "home"}, "terminationUri": "provider.example.net"})}
    routes = [("outbound", CallRouteSpec.model_validate({"gatewayRef": {"name": "home"}, "match": {"calledNumber": "+..."}, "target": {"trunkRef": "provider-primary"}}))]
    rendered = render_kamailio_config(spec, "home", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"], {}, {}, trunks, routes)
    assert "uac_replace_from" not in rendered
    assert "P-Asserted-Identity" not in rendered


def test_kamailio_renders_digest_auth_without_secret_values():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
        }
    )
    trunks = {
        "provider-primary": SIPTrunkSpec.model_validate(
            {
                "gatewayRef": {"name": "home"},
                "terminationUri": "provider.example.net",
                "outbound": {
                    "authentication": {
                        "mode": "Digest",
                        "digest": {
                            "usernameSecretRef": {"name": "trunk-auth", "key": "username"},
                            "passwordSecretRef": {"name": "trunk-auth", "key": "password"},
                            "realm": "provider.example.net",
                        },
                    }
                },
            }
        )
    }
    routes = [("outbound", CallRouteSpec.model_validate({"gatewayRef": {"name": "home"}, "match": {"calledNumber": "+..."}, "target": {"trunkRef": "provider-primary"}}))]
    rendered = render_kamailio_config(spec, "home", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"], {}, {}, trunks, routes)
    assert 'route(RELAY_TRUNK_outbound_provider_primary)' in rendered
    assert 'failure_route[TRUNK_AUTH_outbound_provider_primary]' in rendered
    assert '$avp(auser) = "__KUBEVOIP_TRUNK_PROVIDER_PRIMARY_AUTH_USERNAME__";' in rendered
    assert '$avp(apass) = "__KUBEVOIP_TRUNK_PROVIDER_PRIMARY_AUTH_PASSWORD__";' in rendered
    assert '$avp(arealm) = "provider.example.net";' in rendered
    assert "uac_auth()" in rendered
    assert "secret-user" not in rendered
    assert "secret-password" not in rendered
