# TWT

## Test Type
Basic Functionality

## Overall Description
Tests 802.11 Target Wake Time (TWT) -- a power-save feature where the **STA**, not the AP, negotiates
specific wake/sleep scheduling so it can sleep between agreed-upon service periods instead of staying
awake continuously. The test works against either a real AP or a Pal6 configured as the AP.

Because TWT negotiation is something the STA itself initiates, it can't be configured through the
normal Pal STA setup API the way other radio settings are -- it has to be issued as a direct Linux
command (`wpa_cli twt_setup`/`twt_teardown`) on the STA's own underlying OS. The test does this through
a chained REST call: the main Octobox server's own exec endpoint runs a `curl` command that itself
reaches the STA Pal's **own** basic-server instance (its management IP, port 8383) to execute the
`sudo wpa_cli ...` command locally there. This is exactly why basic-server specifically needs to be
running **on the STA Pal** (not just the main Octobox server) for this test to work -- the command
ultimately executes on the STA itself.

During the traffic run, the script sends a sequence of different TWT setup/teardown command pairs,
varying:
* the wake interval (`mantissa x 2^exponent` microseconds -- the standard 802.11 TWT interval
  encoding),
* the TWT Setup Command type (`setup_cmd`, varied across the sequence to exercise different
  negotiation styles -- e.g. request- vs. suggest- vs. demand-style setup), and
* the flow ID (each setup/teardown pair uses its own flow ID, so each establishes and later tears
  down a distinct TWT agreement).

Every command sent (and the sniffer-start and traffic-start moments) is timestamped into a
`timingEvents` list, logged to the result log -- this timeline is what lets `createReport.py` later
mark exactly when each command was issued directly on the resulting plots. A sniffer runs throughout
the whole test (started early enough to catch the handshake, so the capture can be decrypted
afterward), which matters because the capture is the test's real ground truth: the AP can accept,
modify, or reject whatever was requested, and the only way to know what was *actually* agreed to is to
look at the real over-the-air TWT signaling frames.

## How TWT's effect is made visible
`createReport.py` makes TWT's effect visible three different ways:

1. **Throughput vs. Time, with every TWT command marked directly on the plot.** A vertical red
   reference line is drawn at each TWT command's timestamp (time-aligned to traffic start), so you can
   see throughput behavior change right at the moment each setup or teardown was issued -- TWT
   scheduling should visibly shape the delivery pattern while an agreement is active, and traffic
   should return to its normal pattern right after a teardown.
2. **The actual over-the-air TWT signaling frames, decoded directly from the capture.** Rather than
   just trusting that the requested `wpa_cli` commands took effect, the capture is scanned for genuine
   802.11 TWT Action frames, and each one found is decoded for its real negotiated parameters --
   mantissa, exponent, the resulting interval in microseconds, the minimum TWT duration, and the setup
   type -- alongside the radio conditions at the time (MCS, streams, bandwidth, data rate, RSSI,
   channel). This is the ground truth of what TWT agreement was actually established, shown in a table
   of every TWT-related frame found.
3. **"Packet Arrival per Unit Time."** The main data stream's packets (identified automatically) across
   the window spanning the TWT activity are binned into a fine-grained (1000-bin) histogram of arrival
   times. This is the most direct visual signature of TWT actually constraining delivery: instead of a
   steady stream of packets, you should see them arrive in bursts separated by roughly the negotiated
   sleep interval, whenever a TWT agreement is actively shaping delivery.

## Executable Code
### TWT.py
This is the main code, and sends the TWT command sequence described above (via the chained
exec-through-the-STA's-own-basic-server mechanism) while traffic runs and a sniffer captures. As
always, it also does the initial configuration: reading in the configuration files, reading in the
testbed configuration, setting up the directory for output files, etc.

### createReport.py
Builds the three TWT-specific views described above, plus the usual report scaffolding (System
Diagram, Test Information Summary, Test Description). Since the capture is of encrypted 802.11
traffic, it needs the Wi-Fi security credentials (`ssidForDecode`/`pwdForDecode`, passed to every
pcap-decoding call) in order to decrypt it before any of the TWT frame or packet-arrival analysis is
possible -- same requirement as the other scripts in this project that analyze a capture directly.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `palToUseSTA`/`palToUseSniffer`, `APtoUse` (a real AP, or `Pal-6A`/
`Pal-6B` configured as the AP, with `Pal6APssid`/`Pal6APsecurity`/`Pal6APpassword`), `primaryChannel`/
`iface`/`bw`/`nss`, `ulDl`/`iperfMode`, `attensToUse`/`quadAttenStart`/`quadAttenStop`,
`runPcapAnalysis`/`snifferBW`/`headersOnly`/`managementOnly`, `eaLocation`, and
`ssidForDecode`/`pwdForDecode` (the packet-decryption credentials described above).

Note that the TWT command sequence itself -- which intervals, setup types, flow IDs, and wait times are
used -- is currently hardcoded directly in the script, not exposed through params_test.json. If you
want to exercise different TWT parameters, that means editing the script directly rather than changing
a configuration value.

## Output
This test produces the standard CSV/JSON/pcap output, plus the HTML report with: Throughput vs. Time
annotated with every TWT command's timing, the table of actual TWT signaling frames decoded from the
capture (with their real negotiated parameters and radio conditions), and the Packet Arrival per Unit
Time histogram described above.
