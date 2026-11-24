# McsSweep

## Test Type
Basic Functionality

## Overall Description
For each MCS value in a configured list (plus an automatically-added "-1" run using dynamic/adaptive
rate control), forces the STA -- and, if configured, a Pal acting as the AP -- to that fixed MCS, then
runs a full attenuation sweep (`quadAttenStart` to `quadAttenStop`) to get a throughput-vs-attenuation
RvR curve at that rate. The result is a family of RvR curves, one per fixed MCS plus the adaptive-rate
curve, with an "Outer Envelope" curve overlaid on top showing the best throughput achieved by *any*
fixed MCS at each attenuation point -- i.e. the theoretical best case if the ideal rate were always
selected. Plotting the adaptive-rate curve against that envelope shows how well the DUT's own rate
control is doing relative to the ideal.

A few things this test supports beyond the basic sweep:
* The STA can be a real Pal STA, **or** an iperf2/iperf3 client endpoint (selected via `palToUseSTA`),
  in which case `customAlias`/`customIP`/`customPort` configure the non-Pal side of the traffic pair
  directly. RSSI-based plots are only produced when a real Pal STA is used, since a plain iperf client
  has no RSSI stats to report.
* `usePalAsAP` configures a Pal as the AP (with its own band/channel/SSID/security), instead of
  testing against the real DUT.
* `useMiniServers` can redirect the traffic pair to use configured mini-server endpoints instead of
  the normal traffic address.
* If a Kafka broker is reachable, the evolving multi-MCS envelope report is published to the
  `plotStream` topic after every MCS iteration (not just at the end), the same live-reporting pattern
  used in `KafkaExample.py` -- so a dashboard subscribed to `plotStream` sees the envelope build up,
  one more MCS curve at a time, as the sweep progresses.

## Executable Code
### McsSweep.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. All of
the per-MCS reconfiguration, the attenuation sweep, and the Kafka producer/consumer setup is done
here. Note that `createReport.py` is optional here: the script checks whether it exists before
importing it, and skips all analysis/reporting gracefully if it's missing.

### createReport.py
`analyze(directory_name, json_dir, ea_root)` -- called after *every* MCS iteration (not just once at
the end), and each time, re-reads **every** MCS archive completed so far from the result log. For each
one, it runs the full Expert Analysis pipeline (zip2csv -> objectify -> getStats -> crunch) to get that
MCS's per-attenuation-step throughput and (when available) the combined control/data RSSI across all
chains. It builds one throughput-vs-attenuation curve per MCS (plus the adaptive-rate curve), computes
the "Outer Envelope" curve from the fixed-MCS curves, and produces up to three plots: Throughput vs.
Attenuation (always), and Throughput vs. Control RSSI / Data RSSI (only when RSSI data looks usable,
i.e. a real Pal STA was used). The report JSON is always written locally in the script's own
directory; if a local Script Manager instance can be reached, it's also converted to HTML and a link
is published (as `TestReportLocal.json`).

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `palToUseSTA` (a Pal STA, or `"iperf2"`/`"iperf3"` for a client endpoint,
with `customAlias`/`customIP`/`customPort` for the latter), `usePalAsAP` and its associated
`palToUseAsAP`/`palToUseAsAPBand`/`palToUseAsAPChannel`/`palToUseAsAPSSID`/`palToUseAsAPPassword`/
`palToUseAsAPSecurity`, `primaryChannel`/`bw`/`iface`/`nss`, `ulDl`/`iperfMode`/`trafficType`/
`trafficBW`/`length`/`parallel`/`window`, `quadAttenStart`/`quadAttenStop` (the sweep range repeated
for every MCS), `fixedMcsValues` (the comma-separated list of MCS indices to test -- the adaptive "-1"
run is added automatically, not part of this list), and `useMiniServers`/`miniServersToUse`.

## Output
This test produces the standard CSV/JSON/zip output, one archive per MCS value tested (named
`MCS_<NN>.json.zip`, or `MCS_Adapt.json.zip` for the adaptive-rate run). In addition,
`createReport.py` produces: a local report JSON in the script's own directory every time; an HTML
report plus a script-manager link when Script Manager is reachable locally; and, if a Kafka broker is
available, the same evolving report published to the `plotStream` topic after each MCS iteration.
