# Observability

KubeVoIP keeps observability vendor-neutral. Managed components write useful
operational logs to their container stdout or stderr streams so cluster
operators can choose Fluent Bit, Vector, Promtail, OpenTelemetry Collector,
cloud-native agents, or any other Kubernetes log pipeline.

KubeVoIP does not deploy a logging backend. It provides predictable log output
and optional HEP export so each installation can use its own retention,
indexing, alerting, and access-control model.

## Container logs

Kamailio logs safe SIP summary events with the `kubevoip_sip_event` marker.
These lines include fields such as namespace, gateway, stage, SIP method,
Call-ID, source address, route target, and selected target kind. They do not log
raw SIP passwords, HA1 values, or Secret-backed trunk credentials.

Example:

```text
kubevoip_sip_event namespace=telephony gateway=main stage=route_selected method=INVITE call_id=... source=203.0.113.20 target=100 target_kind=SIPUser
```

RTPengine runs in the foreground with stderr logging enabled. KubeVoIP also logs
a `kubevoip_rtp_event` startup line with the selected advertised address, pod
address, and media port range for each relay replica.

Asterisk workers mount an explicit `logger.conf` so notice, warning, error, and
verbose messages are sent to the console.

Useful commands:

```bash
kubectl -n telephony logs deploy/main-sip-gateway -c kamailio
kubectl -n telephony logs deploy/main-rtpengine-0 -c rtpengine
kubectl -n telephony logs statefulset/apps-asterisk-pool -c asterisk
```

To filter SIP summary logs with plain Kubernetes tooling:

```bash
kubectl -n telephony logs deploy/main-sip-gateway -c kamailio \
  | grep kubevoip_sip_event
```

## SIP header logs

For provider troubleshooting, Kamailio can also log SIP request and reply
headers to stdout with the `kubevoip_sip_headers` marker. This is useful when
you need provider-specific headers such as call identifiers, trunk diagnostics,
or routing metadata in your existing log backend.

Example `SIPGateway` configuration:

```yaml
apiVersion: kubevoip.com/v1alpha1
kind: SIPGateway
metadata:
  name: home
spec:
  databaseSecretRef:
    name: kubevoip-db
  networkProfileRef:
    name: public
  mediaRelayRef:
    name: home
  observability:
    sipHeaders:
      enabled: true
```

Header logs are disabled by default. When enabled, Kamailio emits the SIP first
line and headers for requests and replies, without the SIP body or SDP:

```text
kubevoip_sip_headers namespace=telephony gateway=main direction=... method=INVITE status=... call_id=... source=203.0.113.20 first_line=[...] headers=[...]
```

To search for a provider Call SID in Kubernetes logs:

```bash
kubectl -n telephony logs deploy/main-sip-gateway -c kamailio \
  | grep -E 'kubevoip_sip_headers|X-Twilio|CallSid|Call-Sid|CA[0-9a-fA-F]{32}'
```

## SDP body logs

SDP is carried in the SIP message body rather than in SIP headers. For media
troubleshooting, Kamailio can log SDP bodies from SIP requests and replies with
the `kubevoip_sdp_body` marker whenever the message has
`Content-Type: application/sdp`.

Example `SIPGateway` configuration:

```yaml
apiVersion: kubevoip.com/v1alpha1
kind: SIPGateway
metadata:
  name: home
spec:
  databaseSecretRef:
    name: kubevoip-db
  networkProfileRef:
    name: public
  mediaRelayRef:
    name: home
  observability:
    sdp:
      enabled: true
```

Example log marker:

```text
kubevoip_sdp_body namespace=telephony gateway=main direction=... method=INVITE status=... call_id=... source=203.0.113.20 first_line=[...] body=[v=0...]
```

To search for SDP bodies in Kubernetes logs:

```bash
kubectl -n telephony logs deploy/main-sip-gateway -c kamailio \
  | grep kubevoip_sdp_body
```

## HOMER and HEP capture

KubeVoIP can send SIP capture traffic from Kamailio to a HOMER or
HEP-compatible collector. KubeVoIP does not deploy or operate HOMER; the
collector is user-owned infrastructure.

Example `SIPGateway` capture configuration:

```yaml
apiVersion: kubevoip.com/v1alpha1
kind: SIPGateway
metadata:
  name: home
spec:
  databaseSecretRef:
    name: kubevoip-db
  networkProfileRef:
    name: public
  mediaRelayRef:
    name: home
  observability:
    capture:
      enabled: true
      type: Homer
      hepAddress: homer-heplify.telemetry.svc.cluster.local
      hepPort: 9060
      hepTransport: udp
      captureMode: transaction
      includePayload: true
```

`captureMode` can be `transaction` or `dialog`. HOMER capture is disabled by
default because SIP and SDP payloads can contain caller identity, endpoint
addresses, Contact headers, routing metadata, and other customer-sensitive
information.

Supported destinations include in-cluster heplify-server, external HOMER
installations reachable from Kamailio pods, and other HEP-compatible collectors.

After enabling capture, reconcile the gateway and check that the generated
Kamailio configuration includes `siptrace`:

```bash
kubectl -n telephony get configmap home-sip-gateway-config \
  -o jsonpath='{.data.kamailio\.cfg}' | grep siptrace
```

Then place a test call or registration and search for the SIP Call-ID in HOMER.
The same Call-ID should also appear in the safe `kubevoip_sip_event` summary
logs from the Kamailio container.

## Capture modes

Use `transaction` for the default troubleshooting path. It captures SIP messages
around Kamailio transaction handling and is the best first choice for
registrations, challenges, INVITEs, failures, and routing investigations.

Use `dialog` when you need dialog-oriented call tracing. This is more useful for
full call-flow analysis, but should be enabled deliberately because it can
capture more customer-sensitive signaling context.

## Security notes

Container summary logs are designed to avoid raw credentials. HOMER capture is
different: it intentionally forwards SIP/SDP payloads to the configured capture
collector. Treat the collector, its storage, and its UI as sensitive production
systems.

SIP header and SDP logging also send raw signaling data into the cluster log
pipeline. Headers can include phone numbers, endpoint addresses, Contact
values, Authorization or Proxy-Authorization metadata, provider IDs, and routing
details. SDP can include media IP addresses, ports, codecs, ICE candidates, and
other endpoint details. Enable these logs deliberately, restrict log access, and
set retention appropriately.

Before enabling capture, confirm:

- Kamailio pods can reach the HEP collector address and UDP port.
- The collector has retention limits appropriate for SIP payloads.
- Access to HOMER is restricted to operators who are allowed to inspect call
  signaling.
- Your logging pipeline does not copy full capture payloads into a broader,
  less restricted log store.
