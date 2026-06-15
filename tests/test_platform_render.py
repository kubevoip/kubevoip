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
    rendered = render_kamailio_config(spec, "home", "198.51.100.10", ["udp:rtpengine:2223"], {}, {})
    assert "src_ip == 203.0.113.0/24" in rendered
    assert 'starts_with($rU, "+61")' in rendered
    assert '$du = "sip:example.pstn.twilio.com"' in rendered
    assert "proxy_authorize" in rendered
    assert "loose_route()" in rendered
