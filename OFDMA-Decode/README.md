# OFDMA-Decode

## Test Type
Basic Functionality

## Overall Description
Generates downlink traffic to several STAs at once -- the condition that should cause an AP to use
802.11ax OFDMA to serve them -- and then uses targeted packet capture plus packet-level decoding to
show direct, over-the-air evidence of whether it actually did. Most of this script's length is spent
on a genuinely elaborate setup: finding out which Association ID (AID) the AP gave each client, and
which physical client (MAC address) each AID actually belongs to, so that a dedicated sniffer can be
retuned to shadow each specific client during the real test. That per-client targeting is what makes
the packet-level analysis afterward possible -- without it, a single capture of all clients'
traffic interleaved together would be far harder to decode per-client.

### Setup, step by step
1. **Traffic pairs.** One traffic pair is set up per configured STA (from `STApalPairs`, a list of
   (STA, dedicated-sniffer) pairs -- plus optionally some "real" physical-device STAs with their own
   assigned sniffers), all on the same band/channel, all downlink, all against the same AP (the real
   DUT, or a Pal configured as the AP). Having several clients all pulling downlink traffic
   simultaneously is what creates the scheduling pressure that should cause the AP to use OFDMA.
2. **Finding the BSSID.** One Linux STApal associates first, purely to scan the channel and find the
   candidate BSSID(s) present (filtered by an RSSI threshold), and the strongest one found is used as
   `bssidToUse` for the rest of the test. All the other STAs then associate specifically to that BSSID.
3. **Finding the AIDs in use.** With every sniffer set up, a single sniffer runs a short (10 second)
   unfiltered capture while a short traffic test runs across all clients at once. That capture
   (`allAIDs.pcap`) is handed to Expert Analysis' `pcapAPI` (`action=getAIDlist`), which returns every
   AID seen in use for the chosen BSSID -- the AP's own lightweight per-client identifier, used
   instead of a full MAC address in things like Trigger frames and multi-user PHY signaling. Knowing
   which AIDs exist is necessary, but an AID alone doesn't say *which* client it belongs to --
   that's the next problem.
4. **Mapping each AID to a real MAC address, fast path.** Using that same `allAIDs.pcap` capture,
   `pcapAPI`'s `action=getAID2MAC` is called repeatedly over growing chunks of the capture (up to a
   50,000-packet cap), looking for packets that reveal an AID and a MAC address together directly.
   Any AID resolved this way is done; whatever's left over moves to the slower fallback below.
5. **Mapping each AID to a real MAC address, fallback.** For any AID the fast path couldn't resolve,
   the script reconfigures one sniffer, live, to shadow *only that one AID* -- using a direct
   `octosniff.sh AID <aid> <bssid> <name>` command sent to the sniffer STApal's management REST
   interface -- and runs another short (10 second) focused capture. That capture is decoded with
   Expert Analysis' general-purpose `parsePCAP`, specifically looking for 802.11ax HE-MU frames
   (PPDU format 2 -- a downlink multi-user PPDU, where the **receiver** address is the real client
   MAC) and HE-TRIG frames (PPDU format 3 -- an uplink response to a Trigger frame, where the
   **transmitter** address is the real client MAC). Whichever MAC address shows up most often as
   receiver (of HE-MU) or transmitter (of HE-TRIG) is taken as that AID's real address.
6. **Targeted, simultaneous capture -- the actual test.** With every AID now mapped to a MAC, and
   every MAC mapped to its own dedicated sniffer STApal, each sniffer is individually retuned (again
   via `octosniff.sh`) to shadow exactly one client's AID. All of the sniffers are then started
   *together*, and the real traffic test runs across every client simultaneously. The result is one
   combined capture (`All_Sniffers.pcap`) in which each client's packets were captured by a sniffer
   specifically tuned to that client -- the foundation the whole analysis below depends on.
7. `createReport.py` is called with the BSSID, the AID-to-MAC map, and the full per-STA mapping table
   already known (`someData`), so it doesn't need to rediscover any of this -- only decode the capture.

## How OFDMA operation is identified
All of this happens in `createReport.py`, working from the `All_Sniffers.pcap` capture described
above:

1. **Packet-type breakdown.** Up to 40,000 "QoS Data"/"TCP" packets are pulled from the capture (via
   Expert Analysis' general `parsePCAP`, in 20,000-packet chunks) and classified by their HE (High
   Efficiency / 802.11ax) PPDU format field: no HE info at all ("Not HE"), a normal single-user HE
   frame ("HE-SU"), **a downlink multi-user PPDU ("HE-MU", PPDU format 2)**, or **an uplink
   Trigger-based response ("HE-TRIG", PPDU format 3)**. Any non-zero count of HE-MU or HE-TRIG frames
   is itself direct, literal evidence that the AP transmitted (or scheduled) more than one user within
   a single PPDU -- which is what OFDMA *is*. This count is reported as a simple table.
2. **Users-per-Trigger.** Up to 1,000 Trigger frames are separately pulled from the capture (same
   `parsePCAP` mechanism, filtered to "Trigger" packets), and for each one, the number of individual
   "triggerUser" entries it carries is counted -- i.e. how many clients that single Trigger frame
   scheduled together. A trigger that schedules more than one user at once is direct proof of
   multi-user uplink scheduling. The distribution across all triggers found is shown as a pie chart
   ("Users per Trigger"), so you can see not just *whether* multi-user triggers happened, but how
   consistently the AP grouped multiple clients together versus triggering them one at a time.
3. **RU (Resource Unit) allocation map.** For up to the first 1,000 triggers, every scheduled user's
   AID and assigned Resource Unit (a `subCarriers` range, e.g. "start:end", describing exactly which
   slice of the channel's bandwidth that AID was given) is extracted and plotted as a short horizontal
   line segment -- x-axis is the subcarrier range, y-axis is that trigger's packet number, colored by
   AID. The result is a literal, visual map of which client was given which slice of the channel, for
   every trigger in the capture: frequency-domain multi-user scheduling, shown directly rather than
   inferred.

Together, these three give an increasingly specific picture: first *whether* multi-user PPDUs existed
at all, then *how many* users got grouped together on average, then *exactly which* users shared the
channel and how it was divided between them at each point in time.

## Executable Code
### OFDMA-Decode.py
This is the main code, and where almost all of the setup described above (traffic pairs, BSSID
discovery, AID discovery, the two-stage AID-to-MAC mapping, and the final per-client sniffer
targeting) happens. As always, it also does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc.

### createReport.py
Takes the AID/MAC/BSSID information already discovered by the main script (via `someData`) and
decodes the final `All_Sniffers.pcap` capture as described above: the packet-type breakdown, the
users-per-trigger distribution, and the RU allocation map. It also runs the result archive through the
standard Expert Analysis pipeline (zip2csv -> objectify -> crunch) for a general Alerts section, and
writes an AID-to-MAC mapping table directly from the data it was given.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `STApalPairs` (the list of (STA, dedicated sniffer) pairs to use) and
`numSTApals` (how many of those pairs to actually use, capped at the list length), `realStaPairs`
(optional additional physical-device STAs, each with its own sniffer, MAC, and IP), `band`/
`primaryChannel`/`bw`/`iface`/`nss`, `ulDl`/`trafficType`/`iperfMode`/`trafficBW`/`length`/`parallel`/
`window`/`pingInterval` and the isochronous/"advanced" traffic settings, `usePalAsAP` (plus
`PalToUseAsAP`/`PalAPssid`/`PalAPsecurity`/`PalAPpassword`) to test against a Pal-as-AP instead of the
real DUT, `attensToUse`, `rssiLimit` (the threshold used when scanning for the BSSID to use), and
`sniffFilter`/`sniffmgmt`/`sniffheader` (extra packet-capture filtering options).

## Output
This test produces the standard CSV/JSON/zip output, several pcap files along the way (`allAIDs.pcap`
from the AID-discovery capture, one short per-AID capture for any AID the fast-path mapping couldn't
resolve, and the final combined `All_Sniffers.pcap`), plus the HTML report (`OFDMA-Decode.html`)
containing the AID-to-MAC mapping, the HE packet-type breakdown, the users-per-trigger distribution,
and the RU allocation map described above.
