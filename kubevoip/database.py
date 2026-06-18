"""PostgreSQL persistence for Kamailio runtime data."""

from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from psycopg.conninfo import make_conninfo
from sqlalchemy import Integer, String, create_engine, delete, inspect, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).parents[1]
ALEMBIC_INI = ROOT / "database" / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = ROOT / "database"
_MIGRATION_LOCK = threading.Lock()


class Base(DeclarativeBase):
    pass


class KamailioVersion(Base):
    __tablename__ = "version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    table_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Subscriber(Base):
    __tablename__ = "subscriber"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    domain: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    password: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    ha1: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    ha1b: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    caller_id: Mapped[str | None] = mapped_column(String(128))
    owner_namespace: Mapped[str] = mapped_column(String(63), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(63), nullable=False)


class Location(Base):
    __tablename__ = "location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ruid: Mapped[str] = mapped_column(String(64), default="", nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    domain: Mapped[str | None] = mapped_column(String(64))
    contact: Mapped[str] = mapped_column(String(512), default="", nullable=False)


class CallScope(Base):
    __tablename__ = "kubevoip_call_scope"

    namespace: Mapped[str] = mapped_column(String(63), primary_key=True)
    name: Mapped[str] = mapped_column(String(63), primary_key=True)
    gateway_name: Mapped[str] = mapped_column(String(63), nullable=False)
    owner_uid: Mapped[str] = mapped_column(String(128), nullable=False)


class DialPolicy(Base):
    __tablename__ = "kubevoip_dial_policy"

    namespace: Mapped[str] = mapped_column(String(63), primary_key=True)
    name: Mapped[str] = mapped_column(String(63), primary_key=True)
    gateway_name: Mapped[str] = mapped_column(String(63), nullable=False)
    owner_uid: Mapped[str] = mapped_column(String(128), nullable=False)


class DialPolicyScope(Base):
    __tablename__ = "kubevoip_dial_policy_scope"

    namespace: Mapped[str] = mapped_column(String(63), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(63), primary_key=True)
    scope_name: Mapped[str] = mapped_column(String(63), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class SIPUser(Base):
    __tablename__ = "kubevoip_sip_user"

    namespace: Mapped[str] = mapped_column(String(63), primary_key=True)
    name: Mapped[str] = mapped_column(String(63), primary_key=True)
    gateway_name: Mapped[str] = mapped_column(String(63), nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)
    auth_username: Mapped[str] = mapped_column(String(64), nullable=False)
    caller_id: Mapped[str | None] = mapped_column(String(128))
    dial_policy_name: Mapped[str] = mapped_column(String(63), nullable=False)
    owner_uid: Mapped[str] = mapped_column(String(128), nullable=False)


class SIPTrunk(Base):
    __tablename__ = "kubevoip_sip_trunk"

    namespace: Mapped[str] = mapped_column(String(63), primary_key=True)
    name: Mapped[str] = mapped_column(String(63), primary_key=True)
    gateway_name: Mapped[str] = mapped_column(String(63), nullable=False)
    termination_uri: Mapped[str] = mapped_column(String(253), nullable=False)
    inbound_dial_policy_name: Mapped[str | None] = mapped_column(String(63))
    outbound_caller_id: Mapped[str | None] = mapped_column(String(128))
    digest_username: Mapped[str | None] = mapped_column(String(128))
    digest_realm: Mapped[str | None] = mapped_column(String(253))
    digest_ha1: Mapped[str | None] = mapped_column(String(128))
    owner_uid: Mapped[str] = mapped_column(String(128), nullable=False)


class SIPTrunkCIDR(Base):
    __tablename__ = "kubevoip_sip_trunk_cidr"

    namespace: Mapped[str] = mapped_column(String(63), primary_key=True)
    trunk_name: Mapped[str] = mapped_column(String(63), primary_key=True)
    cidr: Mapped[str] = mapped_column(postgresql.CIDR, primary_key=True)


class CallRoute(Base):
    __tablename__ = "kubevoip_call_route"

    namespace: Mapped[str] = mapped_column(String(63), primary_key=True)
    name: Mapped[str] = mapped_column(String(63), primary_key=True)
    gateway_name: Mapped[str] = mapped_column(String(63), nullable=False)
    scope_name: Mapped[str] = mapped_column(String(63), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    called_number: Mapped[str] = mapped_column(String(64), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(63), nullable=False)
    target_extension: Mapped[str | None] = mapped_column(String(20))
    target_host: Mapped[str | None] = mapped_column(String(253))
    owner_uid: Mapped[str] = mapped_column(String(128), nullable=False)


def connection_string(values: dict[str, str]) -> str:
    required = ("host", "port", "dbname", "user", "password")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise KeyError(f"database Secret missing keys: {', '.join(missing)}")
    return make_conninfo(**{key: values[key] for key in required})


def sqlalchemy_url(values: dict[str, str]) -> URL:
    required = ("host", "port", "dbname", "user", "password")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise KeyError(f"database Secret missing keys: {', '.join(missing)}")
    return URL.create(
        "postgresql+psycopg",
        username=values["user"],
        password=values["password"],
        host=values["host"],
        port=int(values["port"]),
        database=values["dbname"],
    )


def subscriber_ha1(username: str, domain: str, password: str) -> tuple[str, str]:
    ha1 = hashlib.md5(f"{username}:{domain}:{password}".encode(), usedforsecurity=False).hexdigest()
    ha1b = hashlib.md5(f"{username}@{domain}:{domain}:{password}".encode(), usedforsecurity=False).hexdigest()
    return ha1, ha1b


def trunk_digest_ha1(username: str, realm: str, password: str) -> str:
    return hashlib.md5(f"{username}:{realm}:{password}".encode(), usedforsecurity=False).hexdigest()


def _engine(database: dict[str, str]):
    return create_engine(sqlalchemy_url(database), pool_pre_ping=True)


def _session(database: dict[str, str]):
    return sessionmaker(_engine(database), expire_on_commit=False)


def run_migrations(database: dict[str, str]) -> None:
    with _MIGRATION_LOCK:
        logging.getLogger("alembic").setLevel(logging.WARNING)
        config = Config(str(ALEMBIC_INI))
        config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
        config.set_main_option("sqlalchemy.url", sqlalchemy_url(database).render_as_string(hide_password=False))
        if _schema_matches_runtime_head(database):
            command.stamp(config, "0001", purge=True)
        command.upgrade(config, "head")


def _schema_matches_runtime_head(database: dict[str, str]) -> bool:
    engine = _engine(database)
    required_tables = {
        "version",
        "kubevoip_schema_migrations",
        "subscriber",
        "location",
        "kubevoip_call_scope",
        "kubevoip_dial_policy",
        "kubevoip_dial_policy_scope",
        "kubevoip_sip_user",
        "kubevoip_sip_trunk",
        "kubevoip_sip_trunk_cidr",
        "kubevoip_call_route",
    }
    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        if not required_tables.issubset(tables):
            return False
        if "alembic_version" in tables:
            current_alembic = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            return current_alembic in {"0001", "0002"}
        current = connection.execute(text("SELECT max(version) FROM kubevoip_schema_migrations")).scalar()
        return current == 2


def _upsert(session, model, values: dict[str, Any], conflict_columns: list[str], update_columns: list[str]) -> None:
    statement = insert(model).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=[getattr(model, column) for column in conflict_columns],
        set_={column: getattr(statement.excluded, column) for column in update_columns},
    )
    session.execute(statement)


def reconcile_call_scope(database: dict[str, str], namespace: str, name: str, uid: str, gateway_name: str) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        _upsert(
            session,
            CallScope,
            {"namespace": namespace, "name": name, "gateway_name": gateway_name, "owner_uid": uid},
            ["namespace", "name"],
            ["gateway_name", "owner_uid"],
        )


def delete_call_scope(database: dict[str, str], namespace: str, name: str) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        session.execute(delete(CallScope).where(CallScope.namespace == namespace, CallScope.name == name))


def reconcile_dial_policy(database: dict[str, str], namespace: str, name: str, uid: str, gateway_name: str, scopes: list[str]) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        _upsert(
            session,
            DialPolicy,
            {"namespace": namespace, "name": name, "gateway_name": gateway_name, "owner_uid": uid},
            ["namespace", "name"],
            ["gateway_name", "owner_uid"],
        )
        session.execute(delete(DialPolicyScope).where(DialPolicyScope.namespace == namespace, DialPolicyScope.policy_name == name))
        session.add_all(
            DialPolicyScope(namespace=namespace, policy_name=name, scope_name=scope, position=position)
            for position, scope in enumerate(scopes)
        )


def delete_dial_policy(database: dict[str, str], namespace: str, name: str) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        session.execute(delete(DialPolicyScope).where(DialPolicyScope.namespace == namespace, DialPolicyScope.policy_name == name))
        session.execute(delete(DialPolicy).where(DialPolicy.namespace == namespace, DialPolicy.name == name))


def reconcile_sip_user(
    database: dict[str, str],
    namespace: str,
    name: str,
    uid: str,
    username: str,
    domain: str,
    extension: str,
    dial_policy_name: str,
    password: str,
    caller_id: str | None,
) -> None:
    run_migrations(database)
    ha1, ha1b = subscriber_ha1(username, domain, password)
    Session = _session(database)
    with Session.begin() as session:
        _upsert(
            session,
            Subscriber,
            {
                "username": username,
                "domain": domain,
                "password": "",
                "ha1": ha1,
                "ha1b": ha1b,
                "caller_id": caller_id,
                "owner_namespace": namespace,
                "owner_name": name,
            },
            ["username", "domain"],
            ["password", "ha1", "ha1b", "caller_id", "owner_namespace", "owner_name"],
        )
        _upsert(
            session,
            SIPUser,
            {
                "namespace": namespace,
                "name": name,
                "gateway_name": domain,
                "extension": extension,
                "auth_username": username,
                "caller_id": caller_id,
                "dial_policy_name": dial_policy_name,
                "owner_uid": uid,
            },
            ["namespace", "name"],
            ["gateway_name", "extension", "auth_username", "caller_id", "dial_policy_name", "owner_uid"],
        )


def delete_sip_user(database: dict[str, str], namespace: str, name: str) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        session.execute(delete(SIPUser).where(SIPUser.namespace == namespace, SIPUser.name == name))
        session.execute(delete(Subscriber).where(Subscriber.owner_namespace == namespace, Subscriber.owner_name == name))


def reconcile_sip_trunk(
    database: dict[str, str],
    namespace: str,
    name: str,
    uid: str,
    gateway_name: str,
    termination_uri: str,
    allowed_source_cidrs: list[str],
    inbound_dial_policy_name: str | None,
    outbound_caller_id: str | None,
    digest_username: str | None,
    digest_realm: str | None,
    digest_ha1: str | None,
) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        _upsert(
            session,
            SIPTrunk,
            {
                "namespace": namespace,
                "name": name,
                "gateway_name": gateway_name,
                "termination_uri": termination_uri,
                "inbound_dial_policy_name": inbound_dial_policy_name,
                "outbound_caller_id": outbound_caller_id,
                "digest_username": digest_username,
                "digest_realm": digest_realm,
                "digest_ha1": digest_ha1,
                "owner_uid": uid,
            },
            ["namespace", "name"],
            [
                "gateway_name",
                "termination_uri",
                "inbound_dial_policy_name",
                "outbound_caller_id",
                "digest_username",
                "digest_realm",
                "digest_ha1",
                "owner_uid",
            ],
        )
        session.execute(delete(SIPTrunkCIDR).where(SIPTrunkCIDR.namespace == namespace, SIPTrunkCIDR.trunk_name == name))
        session.add_all(SIPTrunkCIDR(namespace=namespace, trunk_name=name, cidr=cidr) for cidr in allowed_source_cidrs)


def delete_sip_trunk(database: dict[str, str], namespace: str, name: str) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        session.execute(delete(SIPTrunkCIDR).where(SIPTrunkCIDR.namespace == namespace, SIPTrunkCIDR.trunk_name == name))
        session.execute(delete(SIPTrunk).where(SIPTrunk.namespace == namespace, SIPTrunk.name == name))


def reconcile_call_route(
    database: dict[str, str],
    namespace: str,
    name: str,
    uid: str,
    gateway_name: str,
    scope_name: str,
    priority: int,
    called_number: str,
    target_kind: str,
    target_ref: str,
    target_extension: str | None,
    target_host: str | None,
) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        _upsert(
            session,
            CallRoute,
            {
                "namespace": namespace,
                "name": name,
                "gateway_name": gateway_name,
                "scope_name": scope_name,
                "priority": priority,
                "called_number": called_number,
                "target_kind": target_kind,
                "target_ref": target_ref,
                "target_extension": target_extension,
                "target_host": target_host,
                "owner_uid": uid,
            },
            ["namespace", "name"],
            [
                "gateway_name",
                "scope_name",
                "priority",
                "called_number",
                "target_kind",
                "target_ref",
                "target_extension",
                "target_host",
                "owner_uid",
            ],
        )


def delete_call_route(database: dict[str, str], namespace: str, name: str) -> None:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        session.execute(delete(CallRoute).where(CallRoute.namespace == namespace, CallRoute.name == name))


def database_ready(database: dict[str, str]) -> bool:
    run_migrations(database)
    Session = _session(database)
    with Session.begin() as session:
        return session.execute(select(1)).scalar_one() == 1


def redact_database(values: dict[str, Any]) -> dict[str, Any]:
    return {key: "<redacted>" if key == "password" else value for key, value in values.items()}
