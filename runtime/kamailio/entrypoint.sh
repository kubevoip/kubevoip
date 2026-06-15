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
DBURL="$dburl" python3 -c 'import os, pathlib
source = pathlib.Path("/etc/kamailio/kamailio.cfg").read_text()
pathlib.Path("/work/kamailio.cfg").write_text(source.replace("__DBURL__", os.environ["DBURL"]))'
exec kamailio -DD -E -f /work/kamailio.cfg
