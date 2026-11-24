# TCP-RTT

## Test Type
Basic Functionality

## Overall Description
Measures TCP round-trip time two genuinely independent ways during the same iperf2 TCP stream, and
compares them directly: once from iperf2's own reported statistics, and once entirely from passive
analysis of the raw packet capture. The point of the test is as much about that comparison as it is
about the RTT number itself -- it's a way to sanity-check an application's self-reported latency
against what the packets on the wire actually show.

At a high level, the script:
* Sets up one traffic pair and one STA on the configured band (optionally against a Pal configured as
  the AP instead of the real DUT), and an AP-side scan to pick up the real primary channel in use.
* Starts a sniffer *before* the STA associates, specifically so the capture includes the WPA/WPA2/WPA3
  handshake -- without it, the packets can't be decrypted later (see below).
* Runs the traffic (an iperf2 TCP stream) and stops the sniffer once it's done.
* Hands the result archive and the capture to `createReport.py`, which produces both RTT measurements
  and the comparison between them.

## How RTT is derived, two different ways

**1. From iperf2's own statistics.** The result archive is run through the standard Expert Analysis
pipeline (zip2csv -> objectify -> crunch) the same way most other scripts in this project use it, and
the objectified per-second data includes a column iperf2 itself reports: `iPerf2 RTT [us]` (one per
traffic pair). This is plotted directly as "iPerf2 RTT (usec) vs. Time" -- this is the traffic
application's own account of its round-trip time, taken at face value. (This step also produces the
usual Aggregate Throughput plot and an Expert Analysis Alerts section, both standard across this
project's reports.)

**2. From the raw packet capture, independent of anything iperf2 reports.** Every TCP packet is pulled
from the capture (via Expert Analysis' `pcapAPI`), and for each acknowledged segment, RTT is computed
three different ways:
* **Wireshark's own ACK-RTT calculation** (`ackRtt`, computed during packet decode) -- plotted on its
  own RTT line plot, with a histogram and CDF (average RTT in the title).
* **An independently-computed "native" RTT** ("TCP/ACK time gap"): the original packet each ACK
  acknowledges is looked up by packet number, and the real time difference between the two packets'
  own capture timestamps is calculated from scratch -- a from-scratch cross-check against Wireshark's
  own number, not a re-reading of it.
* **Wireshark's built-in initial-RTT estimate** ("Initial RTT time"): derived once per TCP stream from
  the handshake itself (`tcp.analysis.initial_rtt`), so this appears as a handful of early reference
  points rather than a continuous series -- a third, independent baseline to compare against.

The report also includes, from this same packet-level analysis: a histogram of the "frame-to-ACK"
packet-count gap (how many packets apart, by sequence, a segment and its ACK are); a histogram of the
raw TCP sequence-number-to-acknowledgment-number delta (data outstanding/unacknowledged at ACK time);
a histogram of MSDU sizes for the TCP data packets; and a scatter showing where in the capture TCP vs.
ACK packets fall.

## The comparison
The final plot, "Compare RTT calculations, from iPerf and from PCAP," overlays all of the above on one
chart: the native TCP/ACK time gap, Wireshark's initial-RTT estimate, and iperf2's own per-second
reported RTT (time-aligned onto the same axes as the packet-capture series). This is the direct
answer to "does the application's self-reported RTT match what's actually happening on the wire" --
and since the three pcap-based numbers are themselves computed three independent ways, a mismatch
between any of them is informative on its own, separate from how iperf2's own number compares.

## A note on packet decryption
Because the sniffer captures encrypted 802.11 traffic, the packet parser needs the Wi-Fi security
credentials (SSID and password) in order to decrypt the capture before it can see down into the TCP
headers at all -- without them, the capture is opaque encrypted data frames, and none of the
packet-capture-based RTT analysis above is possible (the iperf2-statistics-based RTT is unaffected,
since it comes from the PAL stats archive, not the capture). These are configured separately from the
credentials actually used to connect (`ssidForDecode`/`pwdForDecode` in params_test.json, passed to
every `createReport.py` -> `pcapAPI` call), since you may want to decode a capture using different
credentials than whatever the STA itself connected with. If you adapt this test for a different
network, make sure `ssidForDecode`/`pwdForDecode` match the actual credentials in use, or the pcap
analysis will come back empty.

## Executable Code
### TCP-RTT.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. The
early-sniffer-start (to catch the handshake), channel scan, and traffic pair/STA setup specific to
this test are done here. `createReport.py` is optional -- the script checks whether it exists before
importing it, and skips reporting gracefully if it's missing.

### createReport.py
Produces both halves of the RTT comparison described above: the standard Expert Analysis pipeline
(for Aggregate Throughput, Alerts, and iperf2's own reported RTT), and the from-scratch packet-capture
analysis (for Wireshark's ACK-RTT, the native TCP/ACK time gap, the initial-RTT estimate, and the
supporting histograms), followed by the final comparison plot.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `palToUseSTA`/`palToUseSniffer`, `band`/`primaryChannel`/`iface`/`bw`/
`nss`, `ssid`/`security`/`password` (falling back to the DUT's per-band credentials in
params_system.json if `usePalAsAP` is not set), `usePalAsAP`, `ulDl`/`iperfMode`, `attensToUse`/
`quadAttenStart`/`quadAttenStop`, `snifferBW`/`headersOnly`/`managementOnly`, and
`ssidForDecode`/`pwdForDecode` (the packet-decryption credentials described above).

## Output
This test produces the standard CSV/JSON/pcap output, plus the HTML report with: Aggregate Throughput;
iPerf2 RTT vs. Time; the Wireshark ACK-RTT line plot, histogram, and CDF; the frame-to-ACK and
sequence-to-ACK delta histograms; the MSDU size histogram; the TCP/ACK packet-location scatter; and
the final RTT comparison plot described above.
