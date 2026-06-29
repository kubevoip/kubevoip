from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_platform_crds_are_structural():
    crds = list(yaml.safe_load_all((ROOT / "config/crd/platform-crds.yaml").read_text()))

    assert crds
    assert all(item["spec"]["group"] == "kubevoip.com" for item in crds)
    assert all(
        "x-kubernetes-preserve-unknown-fields" not in item["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]
        for item in crds
    )


def test_workflows_are_valid_yaml():
    for workflow in (ROOT / ".github/workflows").glob("*.yaml"):
        assert yaml.safe_load(workflow.read_text())


def test_operator_image_includes_alembic_migrations():
    dockerfile = (ROOT / "Dockerfile").read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert "COPY database /app/database" in dockerfile
    assert "uv pip install --system --no-cache ." in dockerfile
    assert "RUN pip install" not in dockerfile
    assert '"database" = "database"' in pyproject
    assert (ROOT / "database/alembic.ini").exists()
    assert (ROOT / "database/env.py").exists()
    assert (ROOT / "database/versions/0001_runtime_schema.py").exists()
    assert (ROOT / "database/versions/0002_voicemail_odbc.py").exists()
    assert (ROOT / "database/versions/0003_voicemail_realtime_uniqueid.py").exists()
    assert (ROOT / "database/versions/0004_voicemail_message_id.py").exists()
    assert (ROOT / "database/versions/0005_kamailio_mwi_presence.py").exists()
    assert not (ROOT / "database/versions/0001_kamailio_subscriber.py").exists()
    assert not (ROOT / "database/versions/0002_runtime_routing.py").exists()


def test_operator_package_includes_render_templates():
    assert (ROOT / "kubevoip/templates/kamailio.cfg.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/pjsip.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/extensions.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/rtp.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/logger.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/res_odbc.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/extconfig.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/voicemail.conf.j2").exists()
    assert (ROOT / "kubevoip/templates/asterisk/odbc.ini.j2").exists()
