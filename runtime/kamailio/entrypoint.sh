#!/usr/bin/env sh
set -eu
: "${host:?database Secret must contain host}"
: "${port:?database Secret must contain port}"
: "${dbname:?database Secret must contain dbname}"
: "${user:?database Secret must contain user}"
: "${password:?database Secret must contain password}"
dburl="$(python3 -c 'import os, urllib.parse
quote = lambda key: urllib.parse.quote(os.environ[key], safe="")
print("postgres://{}:{}@{}:{}/{}".format(*(quote(key) for key in ("user", "password", "host", "port", "dbname"))))')"
DBURL="$dburl" python3 -c 'import os, pathlib, re
source = pathlib.Path("/etc/kamailio/kamailio.cfg").read_text()
source = source.replace("__DBURL__", os.environ["DBURL"])
for key, value in os.environ.items():
    if key.startswith("KUBEVOIP_TRUNK_"):
        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
        source = source.replace(f"__{key}__", escaped)
missing = sorted(set(re.findall(r"__KUBEVOIP_TRUNK_[A-Z0-9_]+__", source)))
if missing:
    raise SystemExit("missing trunk environment variables: " + ", ".join(missing))
pathlib.Path("/work/kamailio.cfg").write_text(source)'
exec kamailio -DD -E -f /work/kamailio.cfg
