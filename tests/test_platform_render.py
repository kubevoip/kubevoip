from kubevoip.models import SIPGatewaySpec
from kubevoip.platform_render import render_kamailio_config


def test_kamailio_renders_trusted_sources_and_outbound_trunk_routes():
    spec = SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
            "trunks": [
                {
                    "name": "twilio",
                    "terminationUri": "example.pstn.twilio.com",
                    "allowedSourceCidrs": ["203.0.113.0/24"],
                }
            ],
            "routes": [
                {
                    "match": {"calledNumber": "+61..."},
                    "target": {"trunkRef": "twilio"},
                }
            ],
        }
    )
    rendered = render_kamailio_config(spec, "home", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"], {}, {})
    assert "src_ip == 203.0.113.0/24" in rendered
    assert 'starts_with($rU, "+61")' in rendered
    assert '$du = "sip:example.pstn.twilio.com"' in rendered
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
