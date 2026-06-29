import pytest
from sqlalchemy.engine import URL

import kubevoip.database as database_module
from kubevoip.database import (
    ActiveWatcher,
    AsteriskVoicemailMessage,
    AsteriskVoicemailUser,
    CallRoute,
    CallScope,
    DialPolicy,
    DialPolicyScope,
    Presentity,
    SIPTrunk,
    SIPTrunkCIDR,
    SIPUser,
    Subscriber,
    VoicemailMailbox,
    Watcher,
    connection_string,
    reconcile_call_route,
    reconcile_call_scope,
    reconcile_dial_policy,
    reconcile_sip_trunk,
    reconcile_sip_user,
    reconcile_voicemail_mailbox,
    redact_database,
    run_migrations,
    sqlalchemy_url,
    trunk_digest_ha1,
    voicemail_message_counts,
)


def test_database_secret_validation_and_redaction():
    values = {"host": "postgres", "port": "5432", "dbname": "kubevoip", "user": "app", "password": "secret"}
    assert "password=secret" in connection_string(values)
    assert redact_database(values)["password"] == "<redacted>"
    with pytest.raises(KeyError):
        connection_string({"host": "postgres"})


def test_database_connection_string_quotes_secret_values():
    values = {
        "host": "postgres",
        "port": "5432",
        "dbname": "kubevoip",
        "user": "app user",
        "password": r"secret value\with'quotes",
    }
    conninfo = connection_string(values)
    assert "user='app user'" in conninfo
    assert r"password='secret value\\with\'quotes'" in conninfo
    url = sqlalchemy_url(values)
    assert isinstance(url, URL)
    assert url.render_as_string(hide_password=False) == "postgresql+psycopg://app user:secret value%5Cwith%27quotes@postgres:5432/kubevoip"


def test_trunk_digest_ha1_does_not_equal_raw_password():
    ha1 = trunk_digest_ha1("provider-user", "provider.example.net", "provider-password")
    assert ha1 == "5ee8b3326e5f509f59cf9ae44d4b4949"
    assert ha1 != "provider-password"


def test_reconcile_helpers_run_migrations(monkeypatch):
    calls = []

    monkeypatch.setattr("kubevoip.database.run_migrations", lambda database: calls.append(database))
    monkeypatch.setattr("kubevoip.database._session", lambda _database: (_ for _ in ()).throw(RuntimeError("stop after migration")))

    with pytest.raises(RuntimeError, match="stop after migration"):
        reconcile_call_scope({"host": "postgres", "port": "5432", "dbname": "kubevoip", "user": "app", "password": "secret"}, "ns", "internal", "uid", "main")
    assert calls == [{"host": "postgres", "port": "5432", "dbname": "kubevoip", "user": "app", "password": "secret"}]


def test_orm_models_cover_runtime_tables():
    tables = {
        Subscriber.__tablename__,
        CallScope.__tablename__,
        DialPolicy.__tablename__,
        DialPolicyScope.__tablename__,
        SIPUser.__tablename__,
        SIPTrunk.__tablename__,
        SIPTrunkCIDR.__tablename__,
        CallRoute.__tablename__,
        AsteriskVoicemailUser.__tablename__,
        AsteriskVoicemailMessage.__tablename__,
        VoicemailMailbox.__tablename__,
        Presentity.__tablename__,
        ActiveWatcher.__tablename__,
        Watcher.__tablename__,
    }
    assert tables == {
        "subscriber",
        "kubevoip_call_scope",
        "kubevoip_dial_policy",
        "kubevoip_dial_policy_scope",
        "kubevoip_sip_user",
        "kubevoip_sip_trunk",
        "kubevoip_sip_trunk_cidr",
        "kubevoip_call_route",
        "voicemail",
        "voicemessages",
        "kubevoip_voicemail_mailbox",
        "presentity",
        "active_watchers",
        "watchers",
    }


def test_public_database_reconcile_api_remains_importable():
    assert callable(run_migrations)
    assert callable(reconcile_call_scope)
    assert callable(reconcile_dial_policy)
    assert callable(reconcile_sip_user)
    assert callable(reconcile_sip_trunk)
    assert callable(reconcile_call_route)
    assert callable(reconcile_voicemail_mailbox)
    assert callable(voicemail_message_counts)


def test_voicemail_mailbox_initial_pin_is_mailbox_and_not_reconciled(monkeypatch):
    calls = []

    class SessionFactory:
        def begin(self):
            return self

        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(database_module, "run_migrations", lambda _database: None)
    monkeypatch.setattr(database_module, "_session", lambda _database: SessionFactory())
    monkeypatch.setattr(
        database_module,
        "_upsert",
        lambda _session, model, values, conflict_columns, update_columns: calls.append((model, values, conflict_columns, update_columns)),
    )

    reconcile_voicemail_mailbox(
        {"host": "postgres", "port": "5432", "dbname": "kubevoip", "user": "app", "password": "secret"},
        "ns",
        "daniel",
        "uid",
        "home",
        "daniel",
        "daniel",
        "100",
        "applications",
        "applications-asterisk-pool.ns.svc.cluster.local",
        "701",
        "100",
        "Daniel <100>",
        True,
        15,
        True,
        True,
        True,
        False,
        None,
        None,
        None,
    )

    voicemail_user = calls[0]
    assert voicemail_user[0] is AsteriskVoicemailUser
    assert voicemail_user[1]["password"] == "100"
    assert "password" not in voicemail_user[3]
