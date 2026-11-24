# MuMIMO

## Test Type
Basic Functionality

## Overall Description
Confirms whether the DUT (or a Pal configured as the AP) actually groups clients together for
downlink Multi-User MIMO (MU-MIMO is a downlink-only feature in this test; uplink is explicitly
rejected). Three STApals are associated, and traffic is alternated between two different client
groupings while a sniffer captures the exact packets exchanged with one targeted client, so the
capture can be analyzed afterward for direct over-the-air evidence of MU-MIMO.

The key idea is the physical/logical setup: STA 1 and STA 2 are assumed to be positioned such that the
AP's MU-MIMO grouping algorithm should **not** be able to pair them together (the test calls this "the
same quadrant"), while STA 3 is positioned such that it **should** be groupable with STA 1 ("a
different quadrant"). The test then runs traffic in a sequence designed to show that contrast
directly:

1. A short calibration run (STA 1 + STA 3 active) purely to capture a few packets and extract the
   AID (association ID) of each client from the capture, so the sniffer can later be pointed at one
   specific client's AID.
2. **STA 1 + STA 2 active together** ("same quadrant" -- MU-MIMO should *not* engage) for ~30 seconds.
3. **STA 1 + STA 3 active together** ("different quadrants" -- MU-MIMO *should* engage) for ~15
   seconds, with the sniffer's AID filter switched to the second discovered AID partway through.
4. **Back to STA 1 + STA 2** ("same quadrant" again) for ~30 seconds.

Throughout steps 2-4, the sniffer captures continuously (AID-filtered, to keep the capture focused on
one client's packets rather than all three clients interleaved), and that single capture is what
`createReport.py` analyzes afterward.

## How MU-MIMO operation is identified
`createReport.py` uses two independent checks, one supporting and one definitive:

**1. A throughput-based heuristic (supporting evidence, not proof).** It finds the single highest PHY
data rate recorded by *any one* of the three endpoints individually (across both Rx and Tx, all three
Pals) -- call this `maxPhy`, the most any one client could possibly have carried alone. It also finds
the aggregate throughput during the first 30 seconds (the "same quadrant" phase, `max30`) versus the
peak aggregate throughput across the whole run (`maxAll`, which should fall in the middle "different
quadrants" phase if MU-MIMO is working). If `maxAll` comes within 90% of `maxPhy`, that's a strong
hint that more than one client was being served *at the same time* on the full channel -- no single
client's own link could explain that much aggregate throughput alone. This check can't fully
distinguish MU-MIMO from OFDMA on its own (both let multiple clients transmit simultaneously), which
is why it's treated as supporting evidence rather than the final word.

**2. A PCAP-based check for the actual PHY-layer signature of MU-MIMO (the definitive evidence).**
This is the real confirmation. The capture is scanned, in 20,000-packet chunks (up to 200,000 packets,
or stopping early once 10 qualifying packets are found), via Expert Analysis' `pcapAPI` with
`action=getHeMuInfo`, which decodes 802.11ax HE-MU (multi-user) PPDUs. For each one found, the code
checks the raw `SIGB_Compression` field: **when SIG-B is compressed, the whole channel was allocated
to one multi-user group transmitted together -- that's specifically what distinguishes full-bandwidth
MU-MIMO from OFDMA** (which splits the channel into separate resource units per user and does *not*
use compressed SIG-B). If any such packet is found, the report shows a concrete example, including
`NumSymOrMU_MIMO` from that frame -- which, when SIG-B is compressed, is literally the number of users
grouped together in that transmission, read directly from the over-the-air signaling. If none are
found anywhere in the capture, the report says so plainly: "There is no evidence of MU-MIMO operation
in this data."

The rest of the report (throughput, RSSI, data rate, MCS, stream, and bandwidth time series per
endpoint, plus any Alerts) is the same kind of time-series detail used elsewhere, included so the
three phases above are visible directly in context alongside the MU-MIMO evidence.

## Executable Code
### MuMIMO.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. It also
checks that the configured PHY interface actually supports MU-MIMO (802.11ac/ax only) and that the
traffic direction is downlink (uplink isn't supported here), checks that the required background
services (SnifferRelay, the basic server) are running, sets up the three STAs/traffic pairs and the
sniffer, runs the AID-discovery capture, then drives the same-quadrant / different-quadrants /
same-quadrant traffic-pair switching sequence described above while capturing continuously.

### createReport.py
`createReport(directory_name, json_dir, ea_root, someData=None)` -- runs the result archive through
the standard Expert Analysis pipeline (zip2csv -> getStats -> objectify -> crunch) for the time-series
plots and Alerts, and separately runs the captured pcap through `pcapAPI`'s `getHeMuInfo` action for
the SIG-B-compression-based MU-MIMO check described above. Converts the report to HTML, writes a
script-manager link, and writes a short `TestMessages.json` summarizing whether any Alerts were found.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `palToUse1`/`palToUse2`/`palToUse3` (the three STAs; 1 and 3 are the
"different quadrant" pairing, 1 and 2 are the "same quadrant" pairing), `palToUseSniffer`,
`realStas` (optional additional physical-device traffic pairs), `usePalAsAP`/`palToUseAsAP` (plus its
channel/SSID/security/password) to test against a Pal-as-AP instead of the real DUT -- when used, the
AP is explicitly configured with `beamformeeMUEnable`/`beamformerMUEnable` on and an `enableOFDMA`
toggle -- `band`/`primaryChannel`/`bw`/`iface`/`nss`/`security`/`password`/`ssid`, `ulDl` (downlink
only -- the script exits if uplink is selected), `iperfMode`/`trafficBW`/`length`/`parallel`/`window`/
`dscp`/`pingPayload`, and `eaLocation`.

## Output
This test produces the standard CSV/JSON/zip output, plus a saved copy of the capture (named by AID,
e.g. `captureWithAid<N>.pcap`), plus the HTML report (`MU-MIMOv2.html`) with the throughput/RSSI/data
rate/MCS/stream/bandwidth time series, the throughput-based MU-MIMO heuristic, and the definitive
PCAP-based MU-MIMO evidence (or lack thereof) described above.
