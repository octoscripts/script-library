# simpleMLO

## Test Type
Basic Functionality

## Overall Description
A simple 802.11be Multi-Link Operation (MLO) test: a single real Pal STA (no virtual STAs, unlike
`simpleMLOvSTA.py`) associates across whichever MLO bands/links are configured as "members", against
either the real DUT or a Pal configured as the MLO AP. One traffic pair runs over whichever link the
STA actually ends up using, optionally alongside per-band inline packet capture, and the capture is
later decoded specifically for MLO/multi-link evidence.

At a high level, the script:
* Sets up the AP side -- either a Pal configured with full MLO AP settings (`mloConfig_AP`), or the
  real DUT -- and the STA side (`sd2Utils.setupMloAP()`/`setupMloSTA()`), picking up the per-link IP
  mapping each returns.
* Sets up one traffic pair on whichever MLO band is listed first as a "member", then fixes up its
  endpoint addresses using the discovered IP mapping.
* If `staInlineSniffing` is enabled, sets up one sniffer **per configured MLO band member** (so each
  link gets its own capture), with unique probe IDs per radio.
* Runs the traffic `totalTests` times (default 1), saving each iteration's result archive with a
  numbered suffix. **Only the last iteration's archive and pcap are passed to `createReport.py`** --
  unlike some other multi-iteration scripts in this suite, earlier iterations' data isn't reprocessed
  into the report.
* Generates the final report via `createReport.py` (optional -- the script checks whether the file
  exists before importing it, and skips reporting gracefully if it's missing).

## Executable Code
### simpleMLO.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. All of
the MLO AP/STA setup, per-band sniffer setup, and the traffic-iteration loop happens here.

### createReport.py
Builds two distinct halves of the report, in order:

1. **Standard plots from the JSON archive** (added in this update, and placed *before* the MLO/pcap
   analysis below). The last iteration's result archive is run through the usual Expert Analysis
   pipeline (zip2csv -> objectify -> crunch), producing: Aggregate Throughput vs. Time; Mbps (UL/DL)
   vs. Time for every radio endpoint combined on one chart (derived from the raw bits-per-second data,
   divided by 1E6 -- not a dedicated rate column); and MCS, Streams, Bandwidth, and Rate (UL/DL) vs.
   Time, each as its own chart combining every radio endpoint.
2. **MLO-specific packet analysis**, using the captured pcap. This calls Expert Analysis'
   `pcapAPI` with `action=getMLO`, which merges the packets captured across however many per-band
   capture files are involved (it auto-detects which channels/bands actually appear, rather than
   assuming a strict one-capture-per-band layout) and decodes the 802.11be Multi-Link Element
   information needed to establish which frames across different links belong to the same
   Multi-Link Device. That call returns its own ready-made set of plots, which are merged directly
   into the final report.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `palToUse`, `mloConfig_STA`/`mloConfig_AP` (which bands are MLO members,
and their per-band channel/bandwidth/streams settings), `usePalAsAP` (test against a Pal-as-AP instead
of the real DUT), `attensToUse`/`quadAttenStart`/`quadAttenStop`, `ulDl`/`iperfMode`/`trafficType`/
`trafficBW`/`parallel`/`length`, `iface`/`nss`, `staInlineSniffing` (per-MLO-band packet capture), and
`totalTests` (how many times to repeat the traffic run -- only the last iteration feeds the report).

## Output
This test produces the standard CSV/JSON/zip output (one archive per iteration, though only the last
is analyzed), a capture pcap per configured MLO band when `staInlineSniffing` is enabled, and the HTML
report (`Simple_MLO_Plots.html`) containing the standard Expert-Analysis-derived plots followed by the
MLO-specific multi-link packet analysis described above.
