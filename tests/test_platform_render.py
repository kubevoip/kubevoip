from kubevoip.models import SIPGatewaySpec
from kubevoip.platform_render import render_kamailio_config


def gateway_spec() -> SIPGatewaySpec:
    return SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
        }
    )


def homer_gateway_spec(capture_mode: str = "transaction") -> SIPGatewaySpec:
    return SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
            "observability": {
                "capture": {
                    "enabled": True,
                    "type": "Homer",
                    "hepAddress": "homer-heplify.telemetry.svc.cluster.local",
                    "hepPort": 9060,
                    "hepTransport": "udp",
                    "captureMode": capture_mode,
                    "includePayload": True,
                }
            },
        }
    )


def sip_headers_gateway_spec() -> SIPGatewaySpec:
    return SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
            "observability": {"sipHeaders": {"enabled": True}},
        }
    )


def sdp_gateway_spec() -> SIPGatewaySpec:
    return SIPGatewaySpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "networkProfileRef": {"name": "public"},
            "mediaRelayRef": {"name": "home"},
            "observability": {"sdp": {"enabled": True}},
        }
    )


def test_kamailio_uses_database_backed_runtime_routing():
    rendered = render_kamailio_config(gateway_spec(), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert 'loadmodule "sqlops.so"' in rendered
    assert 'modparam("sqlops", "sqlcon", "kubevoip=>__DBURL__")' in rendered
    assert "kubevoip_sip_trunk_cidr" in rendered
    assert "kubevoip_dial_policy_scope" in rendered
    assert "kubevoip_call_route" in rendered
    assert "kubevoip_sip_user" in rendered
    assert "kubevoip_sip_trunk" in rendered
    assert "proxy_authorize" in rendered
    assert "lookup(\"location\")" in rendered
    assert 'uac_auth_mode("1")' in rendered
    assert "rtpengine_offer" in rendered
    assert "provider.example.net" not in rendered
    assert "provider-password" not in rendered
    assert "provider-user" not in rendered
    assert "KUBEVOIP_TRUNK_" not in rendered
    assert '" + $aU + "' in rendered
    assert '" + $avp(caller_policy) + "' in rendered
    assert '" + $rU + "' in rendered
    assert "sql_query(\"kubevoip\", \"$var(caller_query)\", \"caller\")" in rendered
    assert "namespace='test'" in rendered
    assert "gateway_name='home'" in rendered
    assert "namespace='KUBEVOIP_NAMESPACE'" not in rendered
    assert "log_stderror=yes" in rendered
    assert 'loadmodule "xlog.so"' in rendered
    assert "kubevoip_sip_event" in rendered
    assert 'loadmodule "siptrace.so"' not in rendered
    assert "duplicate_uri" not in rendered
    assert "kubevoip_sip_headers" not in rendered
    assert "kubevoip_sdp_body" not in rendered


def test_kamailio_loads_policy_before_consuming_credentials():
    rendered = render_kamailio_config(gateway_spec(), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert rendered.index("route(LOAD_AUTHENTICATED_POLICY);") < rendered.index("consume_credentials();")


def test_kamailio_record_route_uses_internal_and_external_addresses():
    rendered = render_kamailio_config(gateway_spec(), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert 'record_route_preset("10.0.0.10:5060;r2=on", "198.51.100.10:5060;r2=on")' in rendered
    assert 'record_route_preset("198.51.100.10:5060;r2=on", "10.0.0.10:5060;r2=on")' in rendered


def test_kamailio_uses_single_record_route_when_addresses_match():
    rendered = render_kamailio_config(gateway_spec(), "home", "test", "198.51.100.10", "198.51.100.10", ["udp:rtpengine:2223"])
    assert "record_route();" in rendered
    assert "record_route_preset" not in rendered


def test_kamailio_homer_capture_is_opt_in():
    rendered = render_kamailio_config(homer_gateway_spec(), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert 'loadmodule "siptrace.so"' in rendered
    assert 'modparam("siptrace", "trace_to_database", 0)' in rendered
    assert 'modparam("siptrace", "trace_flag"' not in rendered
    assert 'modparam("siptrace", "hep_mode_on", 1)' in rendered
    assert 'modparam("siptrace", "hep_version", 3)' in rendered
    assert 'modparam("siptrace", "duplicate_uri", "sip:homer-heplify.telemetry.svc.cluster.local:9060")' in rendered
    assert "setflag(22);" not in rendered
    assert 'sip_trace_mode("t");' in rendered
    assert "sip_trace();" not in rendered


def test_kamailio_homer_capture_supports_dialog_mode():
    rendered = render_kamailio_config(homer_gateway_spec("dialog"), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert 'sip_trace_mode("d");' in rendered


def test_kamailio_can_log_sip_headers_to_stdout():
    rendered = render_kamailio_config(sip_headers_gateway_spec(), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert "kubevoip_sip_headers" in rendered
    assert "route(LOG_SIP_HEADERS);" in rendered
    assert "$msg(fline)" in rendered
    assert "$msg(hdrs)" in rendered


def test_kamailio_can_log_sdp_body_to_stdout():
    rendered = render_kamailio_config(sdp_gateway_spec(), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert "kubevoip_sdp_body" in rendered
    assert "route(LOG_SDP_BODY);" in rendered
    assert 'has_body("application/sdp")' in rendered
    assert "$rb" in rendered
