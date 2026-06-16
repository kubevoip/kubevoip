"""Render configuration for platform components."""

import hashlib
import json
import os

from kubevoip.models import AsteriskPoolSpec, SIPGatewaySpec


def stable_hash(values: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def render_worker_configs(spec: AsteriskPoolSpec) -> dict[str, str]:
    return {
        "pjsip.conf": """[global]
type=global
user_agent=KubeVoIP-Asterisk-Worker

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

[kamailio]
type=endpoint
context=applications
disallow=all
allow=ulaw
aors=kamailio

[kamailio]
type=aor
max_contacts=10

[kamailio-identify]
type=identify
endpoint=kamailio
match=0.0.0.0/0
""",
        "extensions.conf": f"""[applications]
exten => {spec.applications.echo_extension},1,Answer()
 same => n,Echo()
 same => n,Hangup()
""",
        "rtp.conf": "[general]\nrtpstart=10000\nrtpend=10199\n",
    }


def render_kamailio_config(
    spec: SIPGatewaySpec,
    gateway_name: str,
    external_address: str,
    internal_address: str,
    relay_endpoints: list[str],
    asterisk_targets: dict[str, str],
    sip_user_targets: dict[str, str],
) -> str:
    routes = []
    trunks = {trunk.name: trunk for trunk in spec.trunks}
    external_record_route = external_address.replace('"', '\\"')
    outbound_caller_id = os.getenv("KUBEVOIP_OUTBOUND_CALLER_ID", "").replace('"', '\\"')
    for route in spec.routes:
        number = route.match.called_number.replace('"', '\\"')
        condition = f'starts_with($rU, "{number[:-3]}")' if number.endswith("...") else f'$rU == "{number}"'
        if route.target.sip_user_ref:
            username = sip_user_targets.get(route.target.sip_user_ref, "")
            action = f'$rU = "{username}"; if (!lookup("location")) {{ send_reply("404", "Not registered"); exit; }}'
        elif route.target.asterisk_pool_ref:
            target = asterisk_targets.get(route.target.asterisk_pool_ref or "", "")
            action = f'$du = "sip:{target}:5060"; route(RELAY); exit;'
        else:
            target = trunks[route.target.trunk_ref or ""].termination_uri.replace('"', '\\"')
            caller_id_action = (
                f'uac_replace_from("{outbound_caller_id}", "sip:{outbound_caller_id}@{external_record_route}"); '
                f'append_hf("P-Asserted-Identity: <sip:{outbound_caller_id}@{external_record_route}>\\r\\n"); '
                if outbound_caller_id
                else ""
            )
            action = f'remove_hf("Route"); {caller_id_action}$rd = "{target}"; $du = "sip:{target}"; route(RELAY); exit;'
        routes.append(f"if ({condition}) {{ {action} }}")
    trusted_sources = [f"src_ip == {network}" for trunk in spec.trunks for network in trunk.allowed_source_cidrs]
    trust_line = f"if ({' || '.join(trusted_sources)}) {{ setflag(1); }}" if trusted_sources else ""
    relay_sockets = " ".join(relay_endpoints)
    internal_record_route = internal_address.replace('"', '\\"')
    if internal_record_route == external_record_route:
        record_route_line = "record_route();"
    else:
        record_route_line = (
            f'if (isflagset(1)) {{ record_route_preset("{internal_record_route}:5060;r2=on", "{external_record_route}:5060;r2=on"); }} '
            f'else {{ record_route_preset("{external_record_route}:5060;r2=on", "{internal_record_route}:5060;r2=on"); }}'
        )
    return f"""#!KAMAILIO
#!define ADVERTISED_ADDR "{external_address}"
#!define INTERNAL_ADDR "{internal_address}"
#!define AUTH_REALM "{gateway_name}"
#!define RTPENGINE_SOCKETS "{relay_sockets}"
auto_aliases=no
alias=ADVERTISED_ADDR:5060
alias=INTERNAL_ADDR:5060
listen=udp:0.0.0.0:5060 advertise ADVERTISED_ADDR:5060
loadmodule "db_postgres.so"
loadmodule "tm.so"
loadmodule "sl.so"
loadmodule "rr.so"
loadmodule "pv.so"
loadmodule "maxfwd.so"
loadmodule "textops.so"
loadmodule "siputils.so"
loadmodule "auth.so"
loadmodule "auth_db.so"
loadmodule "usrloc.so"
loadmodule "registrar.so"
loadmodule "uac.so"
loadmodule "rtpengine.so"
modparam("usrloc", "db_mode", 3)
modparam("usrloc", "db_url", "__DBURL__")
modparam("auth_db", "db_url", "__DBURL__")
modparam("auth_db", "password_column", "ha1")
modparam("auth_db", "calculate_ha1", 0)
modparam("rtpengine", "rtpengine_sock", RTPENGINE_SOCKETS)

request_route {{
  if (!mf_process_maxfwd_header("10")) {{ send_reply("483", "Too Many Hops"); exit; }}
  {trust_line}
  if (is_method("BYE|CANCEL")) {{ rtpengine_delete(); }}
  if (has_totag()) {{
    if (loose_route()) {{ route(RELAY); exit; }}
    if (is_method("ACK")) {{ exit; }}
    send_reply("404", "Dialog not found");
    exit;
  }}
  if (is_method("REGISTER")) {{
    if (!www_authorize(AUTH_REALM, "subscriber")) {{ www_challenge(AUTH_REALM, "0"); exit; }}
    save("location");
    exit;
  }}
  if (is_method("INVITE") && !isflagset(1)) {{
    if (!proxy_authorize(AUTH_REALM, "subscriber")) {{ proxy_challenge(AUTH_REALM, "0"); exit; }}
    consume_credentials();
  }}
  if (has_body("application/sdp")) {{ rtpengine_offer("replace-origin replace-session-connection"); }}
  if (is_method("INVITE")) {{ {record_route_line} }}
  {" ".join(routes)}
  if (!lookup("location")) {{ send_reply("404", "No route"); exit; }}
  route(RELAY);
}}

route[RELAY] {{
  t_on_reply("MANAGE_REPLY");
  if (!t_relay()) {{ sl_reply_error(); }}
  exit;
}}

onreply_route[MANAGE_REPLY] {{
  if (has_body("application/sdp")) {{ rtpengine_answer("replace-origin replace-session-connection"); }}
}}
"""
