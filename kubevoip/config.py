"""Operator-wide defaults."""

import os

GROUP = "kubevoip.io"
VERSION = "v1alpha1"
PLURAL = "asterisks"
FIELD_MANAGER = "kubevoip"
DEFAULT_ASTERISK_IMAGE = os.getenv(
    "KUBEVOIP_ASTERISK_IMAGE", "ghcr.io/danohn/kubevoip-asterisk:v0.1.0"
)
MAX_RTP_PORTS = 200
