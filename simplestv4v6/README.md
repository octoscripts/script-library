# simplestv4v6

## Test Type
Testbed Use

## Overall Description
Very similar to `simplest.py` -- a single traffic pair on a single STA, no sniffer, no attenuation
ramp -- but this version adds one more thing worth learning from: it lets the traffic pair be
configured for either IPv4 or IPv6 addressing, and shows how `sd2Utils` makes that switch for you
automatically.

The reason this needs any special handling at all is that an IPv4 address in this testbed is usually
known and configured statically up front, but an IPv6 address is typically negotiated/assigned
dynamically once the STA associates -- it isn't known at the time the traffic pair is first built.
So the traffic pair has to be constructed first (as if it were IPv4), and then patched afterward, once
the STA's real IPv6 address is actually known:

1. The traffic pair is set up as usual (`sd2Utils.setupTrafficPairs(..., ipMode=ipMode)`), with the
   configured `ipMode` passed through so the lower-level setup already knows an IPv6 address will
   eventually be needed.
2. After the STA associates, `sd2Utils.getPalStatus(palToUse, 1, targetRadio, ...)` is called
   specifically to query the Pal's real-time status and populate `globalsfile.ipAddressInfo` with
   whatever address(es) it actually negotiated -- this is the step that discovers the real IPv6
   address, since it can't be known in advance.
3. If `ipMode` indicates IPv6 (`"6" in ipMode`), `sd2Utils.updateTrafficAddressToIPv6(tpDictList,
   ipMode)` rewrites the traffic pair's endpoint address in place, from the original IPv4 placeholder
   to the address that was just discovered. If `ipMode` is IPv4, this step is simply skipped and the
   traffic pair is used as originally built.

This is also a good illustration of a second, smaller nuance worth knowing: `usePalAsAP` (use a Pal as
the AP) and `usePalAPasEndpoint` (make that same Pal-as-AP the traffic pair's actual remote endpoint)
are two separate settings here. You can set up a Pal as the AP without necessarily routing the traffic
pair to it -- `palAsAP` is only passed into `setupTrafficPairs()` when `usePalAPasEndpoint` is also
true; otherwise the traffic pair's remote endpoint is left alone even though a Pal is acting as the AP.

Note: like `simplest.py`, this script did not previously log any test info to the result log, log its
final run time, or call a report generator at all -- there was no `createReport.py` for it. All of
that was added as part of this update, following the same convention used elsewhere.

## Executable Code
### simplestv4v6.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. The
traffic pair / STA setup, and the IPv6 address discovery and traffic-pair patching described above,
are done here.

### createReport.py
Newly added -- identical in structure and plots to `simplest.py`'s `createReport.py` (reads the result
log, finds every result archive the run produced, and runs each through Expert Analysis to produce the
standard plots: Throughput vs. Time, and Data Rate/MCS/Streams/Bandwidth vs. Time, UL/DL, combined
across every radio endpoint). Nothing about IPv4-vs-IPv6 addressing changes what Expert Analysis
reports on here, so no IP-version-specific logic was needed in this file.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes everything `simplest.py` has (`palToUse`/`attensToUse` as plain text device
names, `usePalAsAP` plus its SSID/security/password/channel, `band`/`primaryChannel`/`bw`/`iface`/
`nss`, `ulDl`/`iperfMode`/`trafficType`/`trafficBW`/`parallel`/`window`/`length`,
`quadAttenStart`/`quadAttenStop`, `totalTests`), plus two more specific to this script: `ipMode` (which
IP version/addressing mode to use for the traffic pair) and `usePalAPasEndpoint` (whether a configured
Pal-as-AP is also the traffic pair's remote endpoint, as described above).

## Output
This test produces the standard CSV/JSON/zip output (one archive per iteration), plus the HTML report
described above.
