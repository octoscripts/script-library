# Roaming

## Test Type
Basic Functionality

## Overall Description
Causes a STA to roam from one AP to another (box A / "root" -> box B / "leaf1", in a mesh-style
backhaul topology) by ramping attenuation against each box in turn, captures the roam on a sniffer,
and analyzes the capture to produce a detailed, multi-definition measurement of how long the roam
actually took, how it affected security re-handshaking, and how it affected data throughput. It can
do this once, or repeat it many times (optionally in both directions) to build up roam-time
statistics across many roam events.

### Finding (or being told) what it needs to know
Before any roaming can happen, the test needs to know three things, and for each one it can either be
told directly or work it out for itself:

* **The roaming STA's MAC address.** If `assign_STA_MAC` is set, the configured MAC(s)/tag(s) are used
  directly. Otherwise -- only relevant for a real (non-Pal) STA, since a Pal's MAC is already known --
  the test runs a short burst of traffic while sniffing, and picks out the STA's MAC by finding which
  address appears opposite the (already-identified) AP's address in the busiest data/TCP/UDP/probe-
  response stream in the capture.
* **Box A's and Box B's BSSIDs.** If `assign_Root_AP_MAC`/`assign_Leaf1_AP_MAC` are set, the configured
  BSSIDs are used directly (this also supports reading a pre-existing `meshinfo.json`, if one is found,
  for a mesh system that already documents its own node BSSIDs). Otherwise, the test isolates each box
  in turn (attenuating the other one to maximum) and sniffs beacons, picking whichever transmitter
  address appears most often per channel as that box's BSSID. Either way, the result is written out to
  a `meshinfo.json` file in the results directory.
* **The attenuation points at which each box's connection actually breaks.** If a valid
  `disconnectionPoints` pair is configured, those two values are used directly. Otherwise, the test
  ramps attenuation from 0 to 90 dB against each box in turn (while connected to it) and watches for
  the point at which the STA actually disconnects, recording that as `disconnectPointA`/
  `disconnectPointB`. These aren't the roam trigger points themselves -- they're used to center the
  actual roam-inducing ramp (`roamLowSide`/`roamHighSide`, relative to each disconnect point) in the
  attenuation range where a roam is actually likely to happen, rather than blindly sweeping the full
  range every time.

### Causing and capturing the roam
With all of that known, the actual roam-inducing sequence is: start the sniffer and the traffic, then
step attenuation against the current AP upward (from `disconnectPointA + roamLowSide` to
`disconnectPointA + roamHighSide`, in 2 dB steps, pausing `secondsPerAttenuationStep` seconds at each
one) while watching the STA's reported BSSID for a change. Once it changes (or, if
`allowEarlyRampStop` is set, a few steps after it changes), the ramp can stop early rather than
continuing needlessly. Traffic and the sniffer both keep running throughout. The result -- one zip
archive and one pcap per roam attempt -- is what gets analyzed afterward.

If `backAndForthRoaming` is enabled, immediately after the forward roam (A -> B) completes and is
analyzed, the same process runs in reverse (B -> A), within the same "roam set". Separately,
`AdditionalRoams` controls how many more complete roam sets (forward, and reverse if enabled) to
repeat -- resetting the STA back to its starting AP between sets -- so a single test run can
accumulate many independent roam events for the summary statistics described below.

If `palsAsAPs` and `doKick` are both set (only meaningful when testing against Pals acting as APs,
not a real DUT), the STA's MAC is actively removed from both Pal-APs' association tables before each
roam attempt -- forcing a clean reassociation rather than risking an instant reconnect from a cached
association.

## How a roam is detected and its timing calculated
This is the job of `doRoamingAnalysis2.py` (called once per roam attempt, via `createReport.main()`),
and it's where most of the real analysis happens:

* **Finding the roam in the capture, and the different ways "roam time" is defined.** The capture is
  handed to Expert Analysis' `pcapAPI` with `action=getRoaming`, along with the roaming STA's MAC(s),
  the candidate AP MACs, and the traffic direction. Expert Analysis itself computes "roam time" --
  the time between the last data packet successfully exchanged with the old AP and the first with the
  new one -- under several different definitions simultaneously (for example: requiring both packets
  to be ACKed, restricting to non-retried packets, uplink-only packets, a vendor-specific "Cisco"
  convention, and others). When a region looks like it should contain a roam (an Authentication frame
  is present) but no roam time was computed, the analysis window is widened and retried, to avoid
  missing a roam that fell near the edge of the originally-requested packet range.
* **Fast Transition (FT) timing.** Separately, and more narrowly, the code looks for an Authentication
  frame followed by a Reassociation Response frame, both attributable to the roaming STA. The time
  between these two is the "FT time" -- under 802.11r Fast BSS Transition, this is specifically the
  window during which the STA is *not* blocked from sending data at all: it can still talk to the old
  AP right up to the Authentication frame, and resume with the new AP immediately after the
  Reassociation Response. This makes FT time a meaningfully different (and usually much shorter)
  number than the data-interruption-based roam times above, worth reporting on its own.
* **Multiple roam-time calculations can describe the same physical roam event.** Since several roam-
  time definitions are computed at once, the analysis groups calculations that share the same
  underlying association events back into a single roam "id", and flags which of that group's values
  is the shortest (the vendor-specific "Cisco" definition is excluded from being picked as shortest).
  Any 802.11v WNM BSS-Transition-Management frames seen around a roam are also associated with it --
  evidence of whether the AP explicitly requested the roam rather than the client deciding on its own.
* **EAPOL (security handshake) timing.** The packets around each roam are also scanned for EAPOL
  (WPA/WPA2/WPA3 4-way handshake) exchanges involving the roaming STA's MAC(s), grouped by which two
  addresses were exchanging them, with the time span of each group's packets recorded -- i.e. how long
  re-keying took as part of (or immediately after) the roam.
* **Application-level data gap.** Independent of the control-plane roam-time definitions above, the
  analysis finds the actual gap between the last pre-roam and first post-roam *data* packet, and --
  using the STA's own pre-roam average inter-packet timing -- estimates how many packets' worth of
  time was effectively lost to the roam from the application's point of view.
* **Pre-roam / post-roam throughput.** Average throughput just before and just after the roam is
  computed per traffic pair, tagged with the "from BSSID -> to BSSID" direction of that specific roam,
  which is what feeds the pre/post-roam throughput comparisons in the summary report.

**Output of this per-roam analysis**: an individual HTML report per roam attempt (RSSI across the
transition, the roam-time results table with every definition computed, FT timing, EAPOL group
durations, the estimated application-level gap, and pre/post-roam throughput), saved both to
Script Manager's storage and as `roamPlot_<N>.html` in the results directory, plus all of the same
data logged into the shared result log under `roamData["<N>"]` for the summary report to use
afterward. If Kafka is reachable, each roam's report is also published live to the `plotStream` topic
as it completes.

## The summary report: aggregating many roams
After all roams (across all roam sets and any additional repeats) are complete, `createReport.roamPlot()`
reads back every logged roam from `roamData` and builds one aggregate report covering the whole run:

* **Roam time**: for each roam, one headline value is picked from the available definitions, in
  preference order (`BothWaysData`, `AllData`, `TCP-UDP`, `ULpackets`, `Cisco`, `experimental` --
  whichever is available for that roam). Values are trimmed to the `outlierLow`-`outlierHigh`
  percentile range (configurable) before computing the average/standard deviation, so a handful of
  badly-behaved roams don't dominate the displayed statistics or the plot scaling. The result is shown
  as a scatter plot (one point per roam), a histogram, and a CDF.
* **FT time**: the same scatter/histogram/CDF treatment, applied to the Fast Transition times
  collected across every roam.
* **Pre-roam vs. post-roam throughput**: shown per traffic pair (averaged across every roam of that
  pair), and then broken out again per traffic pair *and* per roam direction (i.e. each distinct
  "from BSSID -> to BSSID" pairing gets its own comparison) -- so forward and reverse roams, or roams
  between specific boxes, can be compared rather than only seeing one blended average.

**Output of the summary report**: `Roam_Time_Plots.html`, with a script-manager link
(`Roam_Time_Reports.json`). If Kafka is reachable, this summary is also published to the `plotStream`
topic once complete.

## Executable Code
### Roaming.py
This is the main code, and where the use-model discovery/assignment logic, the disconnect-point
search, and the roam-inducing attenuation ramp (forward, and reverse if enabled, repeated as
configured) all happen. As always, it also does the initial configuration: reading in the
configuration files, reading in the testbed configuration, setting up the directory for output files,
etc. It calls `createReport.main()` once per roam attempt, and `createReport.roamPlot()` once at the
very end for the summary.

### createReport.py
A thin wrapper around `doRoamingAnalysis2.py` for the per-roam report (`main()`, described above),
plus the summary aggregation (`roamPlot()`, described above) in its own right.

### doRoamingAnalysis2.py
Does the actual per-roam packet-level analysis described above: finding the roam, computing every
roam-time definition Expert Analysis offers, FT timing, EAPOL group timing, the application-level
data gap, and pre/post-roam throughput.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes:
* `palsToUseSTA`/`stationCount` (which STA(s) to use, and how many of the configured list to actually
  use), `assign_STA_MAC` (plus the per-STA MAC/tag assignments) to skip STA MAC discovery.
* `assign_Root_AP_MAC`/`assigned_Root_AP_MAC` and `assign_Leaf1_AP_MAC`/`assigned_Leaf1_AP_MAC` to
  skip BSSID discovery for box A/box B respectively.
* `disconnectionPoints` (a comma-separated pair) to skip the disconnect-point search.
* `attenForRoot`/`attenForLeaf1`/`attenForRootToLeaf1`/`attensForSniffers`/`backhaulAttenValue` (the
  attenuators used for each box, the backhaul link, and the sniffers).
* `roamLowSide`/`roamHighSide` (the ramp window around each disconnect point), `secondsPerAttenuationStep`,
  `allowEarlyRampStop`.
* `backAndForthRoaming` (also roam back immediately after each forward roam) and `AdditionalRoams`
  (how many more full roam sets to repeat).
* `palsAsAPs` (test against Pals configured as APs instead of the real DUT, with `doKick` to force a
  clean reassociation by removing the STA's MAC from the Pal-APs' association tables before each roam).
* `channelToUseSTA`, `tGenerator`/`tProtocol`/`upOrDown`/`tRate`/`parallel`/`window`/`length` and the
  isochronous/"advanced" traffic settings, for the traffic running during the roam.
* `outlierLow`/`outlierHigh` (the percentile range used to trim outliers in the summary report).

## Output
This test produces the standard CSV/JSON/zip output (one per roam attempt), a `meshinfo.json`
describing the discovered or assigned box BSSIDs, a pcap per roam attempt, an individual HTML roam
report per attempt (`roamPlot_<N>.html`, plus a Script Manager link), and -- after every roam is
complete -- the aggregate `Roam_Time_Plots.html` summary described above (roam time and FT time
statistics with outlier trimming, histograms and CDFs, and pre/post-roam throughput broken out by
traffic pair and roam direction).
