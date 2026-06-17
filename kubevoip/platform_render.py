"""Render configuration for platform components."""

import hashlib
import json

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


def kamailio_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_kamailio_config(
    spec: SIPGatewaySpec,
    gateway_name: str,
    namespace: str,
    external_address: str,
    internal_address: str,
    relay_endpoints: list[str],
) -> str:
    relay_sockets = " ".join(relay_endpoints)
    external_record_route = kamailio_string(external_address)
    internal_record_route = kamailio_string(internal_address)
    if internal_address == external_address:
        record_route_line = "record_route();"
    else:
        record_route_line = (
            f'if (isflagset(1)) {{ record_route_preset("{internal_record_route}:5060;r2=on", "{external_record_route}:5060;r2=on"); }} '
            f'else {{ record_route_preset("{external_record_route}:5060;r2=on", "{internal_record_route}:5060;r2=on"); }}'
        )
    sql_namespace = namespace.replace("'", "''")
    sql_gateway = gateway_name.replace("'", "''")
    trusted_query_prefix = (
        "select t.name, t.inbound_dial_policy_name "
        "from kubevoip_sip_trunk t "
        "join kubevoip_sip_trunk_cidr c on c.namespace=t.namespace and c.trunk_name=t.name "
        f"where t.namespace='{sql_namespace}' and t.gateway_name='{sql_gateway}' "
        "and c.cidr >>= '"
    )
    trusted_query_suffix = (
        "'::inet "
        "order by t.name limit 1"
    )
    caller_query_prefix = (
        "select dial_policy_name from kubevoip_sip_user "
        f"where namespace='{sql_namespace}' and gateway_name='{sql_gateway}' "
        "and auth_username='"
    )
    caller_query_suffix = "' limit 1"
    route_query_prefix = (
        "select r.target_kind, r.target_ref, coalesce(r.target_extension,''), coalesce(r.target_host,''), "
        "coalesce(u.auth_username,''), coalesce(t.termination_uri,''), coalesce(t.outbound_caller_id,''), "
        "coalesce(t.digest_username,''), coalesce(t.digest_realm,''), coalesce(t.digest_ha1,'') "
        "from kubevoip_dial_policy_scope d "
        "join kubevoip_call_route r on r.namespace=d.namespace and r.scope_name=d.scope_name "
        "left join kubevoip_sip_user u on r.target_kind='SIPUser' and u.namespace=r.namespace and u.name=r.target_ref "
        "left join kubevoip_sip_trunk t on r.target_kind='SIPTrunk' and t.namespace=r.namespace and t.name=r.target_ref "
        f"where d.namespace='{sql_namespace}' and d.policy_name='"
    )
    route_query_middle = (
        "' "
        f"and r.gateway_name='{sql_gateway}' "
        "and (r.called_number='"
    )
    route_query_suffix = (
        "' or (right(r.called_number, 3)='...' "
        "and '"
    )
    route_query_end = (
        "' like left(r.called_number, length(r.called_number)-3) || '%')) "
        "order by d.position, r.priority, r.name limit 1"
    )
    return f"""#!KAMAILIO
#!define ADVERTISED_ADDR "{external_address}"
#!define INTERNAL_ADDR "{internal_address}"
#!define AUTH_REALM "{gateway_name}"
#!define RTPENGINE_SOCKETS "{relay_sockets}"
#!define KUBEVOIP_NAMESPACE "{kamailio_string(namespace)}"
#!define KUBEVOIP_GATEWAY "{kamailio_string(gateway_name)}"
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
loadmodule "sqlops.so"
loadmodule "uac.so"
loadmodule "dialog.so"
loadmodule "rtpengine.so"
modparam("usrloc", "db_mode", 3)
modparam("usrloc", "db_url", "__DBURL__")
modparam("auth_db", "db_url", "__DBURL__")
modparam("auth_db", "password_column", "ha1")
modparam("auth_db", "calculate_ha1", 0)
modparam("uac", "auth_username_avp", "$avp(auser)")
modparam("uac", "auth_password_avp", "$avp(apass)")
modparam("uac", "auth_realm_avp", "$avp(arealm)")
modparam("rtpengine", "rtpengine_sock", RTPENGINE_SOCKETS)
modparam("sqlops", "sqlcon", "kubevoip=>__DBURL__")

request_route {{
  if (!mf_process_maxfwd_header("10")) {{ send_reply("483", "Too Many Hops"); exit; }}
  route(DETECT_TRUSTED_TRUNK);
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
    route(LOAD_AUTHENTICATED_POLICY);
    consume_credentials();
  }}
  if (is_method("INVITE") && $avp(caller_policy) == $null) {{ send_reply("403", "No dial policy"); exit; }}
  if (!($rU =~ "^[+0-9.*]+$")) {{ send_reply("404", "No route"); exit; }}
  if (has_body("application/sdp")) {{ rtpengine_offer("replace-origin replace-session-connection"); }}
  if (is_method("INVITE")) {{ dlg_manage(); {record_route_line} }}
  route(ROUTE_INVITE);
  exit;
}}

route[DETECT_TRUSTED_TRUNK] {{
  $var(trusted_query) = "{trusted_query_prefix}" + $si + "{trusted_query_suffix}";
  sql_query("kubevoip", "$var(trusted_query)", "trusted");
  if ($dbr(trusted=>rows) > 0) {{
    setflag(1);
    $avp(caller_policy) = $dbr(trusted=>[0,1]);
  }}
  sql_result_free("trusted");
}}

route[LOAD_AUTHENTICATED_POLICY] {{
  $var(caller_query) = "{caller_query_prefix}" + $aU + "{caller_query_suffix}";
  sql_query("kubevoip", "$var(caller_query)", "caller");
  if ($dbr(caller=>rows) > 0) {{
    $avp(caller_policy) = $dbr(caller=>[0,0]);
  }}
  sql_result_free("caller");
}}

route[ROUTE_INVITE] {{
  $var(route_query) = "{route_query_prefix}" + $avp(caller_policy) + "{route_query_middle}" + $rU + "{route_query_suffix}" + $rU + "{route_query_end}";
  sql_query("kubevoip", "$var(route_query)", "route");
  if ($dbr(route=>rows) == 0) {{
    sql_result_free("route");
    send_reply("403", "No permitted route");
    exit;
  }}
  $avp(target_kind) = $dbr(route=>[0,0]);
  if ($avp(target_kind) == "SIPUser") {{
    $rU = $dbr(route=>[0,4]);
    sql_result_free("route");
    if (!lookup("location")) {{ send_reply("404", "Not registered"); exit; }}
    route(RELAY);
    exit;
  }}
  if ($avp(target_kind) == "AsteriskPool") {{
    $rU = $dbr(route=>[0,2]);
    $du = "sip:" + $dbr(route=>[0,3]) + ":5060";
    sql_result_free("route");
    route(RELAY);
    exit;
  }}
  if ($avp(target_kind) == "SIPTrunk") {{
    remove_hf("Route");
    if ($dbr(route=>[0,6]) != "") {{
      uac_replace_from($dbr(route=>[0,6]), "sip:" + $dbr(route=>[0,6]) + "@ADVERTISED_ADDR");
    }}
    $rd = $dbr(route=>[0,5]);
    $du = "sip:" + $dbr(route=>[0,5]);
    $avp(auser) = $dbr(route=>[0,7]);
    $avp(arealm) = $dbr(route=>[0,8]);
    $avp(apass) = $dbr(route=>[0,9]);
    sql_result_free("route");
    route(RELAY_TRUNK);
    exit;
  }}
  sql_result_free("route");
  send_reply("500", "Unsupported route target");
  exit;
}}

route[RELAY] {{
  t_on_reply("MANAGE_REPLY");
  if (!t_relay()) {{ sl_reply_error(); }}
  exit;
}}

route[RELAY_TRUNK] {{
  t_on_reply("MANAGE_REPLY");
  t_on_failure("TRUNK_AUTH");
  if (!t_relay()) {{ sl_reply_error(); }}
  exit;
}}

failure_route[TRUNK_AUTH] {{
  if (t_is_canceled()) {{ exit; }}
  if (t_check_status("401|407") && $avp(auser) != "" && $avp(apass) != "") {{
    if (uac_auth_mode("1")) {{ t_relay(); exit; }}
  }}
}}

onreply_route[MANAGE_REPLY] {{
  if (has_body("application/sdp")) {{ rtpengine_answer("replace-origin replace-session-connection"); }}
}}
"""
