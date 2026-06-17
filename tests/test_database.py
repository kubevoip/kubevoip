import pytest

from kubevoip.database import connection_string, redact_database, trunk_digest_ha1


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


def test_trunk_digest_ha1_does_not_equal_raw_password():
    ha1 = trunk_digest_ha1("provider-user", "provider.example.net", "provider-password")
    assert ha1 == "5ee8b3326e5f509f59cf9ae44d4b4949"
    assert ha1 != "provider-password"
