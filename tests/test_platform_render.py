from kubevoip.models import AsteriskPoolSpec, SIPGatewaySpec
from kubevoip.platform_render import render_kamailio_config, render_worker_configs


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
    assert "kubevoip_voicemail_mailbox" in rendered
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
    assert "kubevoip_sip_message" not in rendered


def test_kamailio_renders_voicemail_fallback_routes():
    rendered = render_kamailio_config(gateway_spec(), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert "route[RELAY_USER]" in rendered
    assert "failure_route[VOICEMAIL_FALLBACK]" in rendered
    assert "route[SEND_TO_VOICEMAIL]" in rendered
    assert "X-KubeVoIP-Mailbox" in rendered
    assert "$avp(vm_mailbox) = $dbr(route=>[0,10]);" in rendered
    assert "$var(vm_fr) = $avp(vm_timeout) * 1000;" in rendered
    assert "t_set_fr($var(vm_fr), $var(vm_fr));" in rendered
    assert 'rtpengine_offer("replace-origin replace-session-connection direction=external direction=external");' in rendered
    assert 'rtpengine_offer("replace-origin replace-session-connection direction=external direction=internal");' in rendered
    assert 'rtpengine_answer("replace-origin replace-session-connection direction=internal direction=external");' in rendered
    assert 'rtpengine_answer("replace-origin replace-session-connection direction=external direction=external");' in rendered
    assert "media_target=asterisk" in rendered


def test_kamailio_renders_mwi_routes():
    rendered = render_kamailio_config(gateway_spec(), "home", "test", "198.51.100.10", "10.0.0.10", ["udp:rtpengine:2223"])

    assert 'loadmodule "presence.so"' in rendered
    assert 'loadmodule "presence_mwi.so"' in rendered
    assert 'modparam("presence", "db_url", "__DBURL__")' in rendered
    assert 'modparam("presence_mwi", "default_expires", 3600)' in rendered
    assert 'is_method("SUBSCRIBE") && $hdr(Event) =~ "message-summary"' in rendered
    assert 'is_method("PUBLISH") && $hdr(Event) =~ "message-summary"' in rendered
    assert "route[HANDLE_MWI_SUBSCRIBE]" in rendered
    assert "route[HANDLE_MWI_PUBLISH]" in rendered
    assert "handle_subscribe();" in rendered
    assert "handle_publish();" in rendered
    assert "route(SEND_MWI_NOTIFY_TO_CONTACTS);" in rendered
    assert "uac_req_send()" in rendered
    assert "Messages-Waiting" in rendered
    assert "Voice-Message" in rendered


def test_worker_configs_include_odbc_voicemail_when_enabled():
    spec = AsteriskPoolSpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "applications": {"voicemail": {"enabled": True}},
        }
    )
    configs = render_worker_configs(
        spec,
        {"host": "postgres.test.svc", "port": "5432", "dbname": "kubevoip", "user": "app", "password": "secret"},
    )

    assert "VoiceMailMain()" in configs["extensions.conf"]
    assert "VoiceMail(${KUBEVOIP_MAILBOX}@default,u)" in configs["extensions.conf"]
    assert "allow=ulaw" in configs["pjsip.conf"]
    assert "allow=alaw" in configs["pjsip.conf"]
    assert "voicemail => odbc,kubevoip,voicemail" in configs["extconfig.conf"]
    assert "odbcstorage=kubevoip" in configs["voicemail.conf"]
    assert "forcename=yes" in configs["voicemail.conf"]
    assert "forcegreetings=yes" in configs["voicemail.conf"]
    assert "externnotify=/usr/local/bin/kubevoip-mwi-publish" in configs["voicemail.conf"]
    assert "Driver=PostgreSQL Unicode" in configs["odbc.ini"]
    assert "password => secret" in configs["res_odbc.conf"]


def test_worker_configs_can_preselect_voicemail_main_mailbox():
    spec = AsteriskPoolSpec.model_validate(
        {
            "databaseSecretRef": {"name": "db"},
            "applications": {"voicemail": {"enabled": True, "mainMailbox": "100"}},
        }
    )
    configs = render_worker_configs(
        spec,
        {"host": "postgres.test.svc", "port": "5432", "dbname": "kubevoip", "user": "app", "password": "secret"},
    )

    assert "VoiceMailMain(100@default)" in configs["extensions.conf"]
    assert "VoiceMailMain()" not in configs["extensions.conf"]


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

    assert "kubevoip_sip_message" in rendered
    assert "route(LOG_SIP_MESSAGE);" in rendered
    assert "$msg(fline)" in rendered
    assert '$var(cr) = "0d";' in rendered
    assert "$var(cr) = $(var(cr){s.decode.hexa});" in rendered
    assert '$var(lf) = "0a";' in rendered
    assert "$var(lf) = $(var(lf){s.decode.hexa});" in rendered
    assert "$(msg(hdrs){s.replace,$var(cr),\\\\r}{s.replace,$var(lf),\\\\n})" in rendered


def test_kamailio_can_include_sdp_body_in_sip_message_log():
    rendered = render_kamailio_config(
        SIPGatewaySpec.model_validate(
            {
                "databaseSecretRef": {"name": "db"},
                "networkProfileRef": {"name": "public"},
                "mediaRelayRef": {"name": "home"},
                "observability": {"sipHeaders": {"enabled": True}, "sdp": {"enabled": True}},
            }
        ),
        "home",
        "test",
        "198.51.100.10",
        "10.0.0.10",
        ["udp:rtpengine:2223"],
    )

    assert "kubevoip_sip_message" in rendered
    assert "route(LOG_SIP_MESSAGE);" in rendered
    assert 'has_body("application/sdp")' in rendered
    assert "$(rb{s.replace,$var(cr),\\\\r}{s.replace,$var(lf),\\\\n})" in rendered
