# throughputScan

## Test Type
Basic Functionality

## Overall Description
Systematically sweeps through a whole matrix of configurations -- 802.11 standard, band, channel,
bandwidth, packet size, direction, and offered load level -- and for every combination, compares the
actually-achieved throughput against both the theoretical maximum PHY rate for that configuration and
the specific rate that was intentionally offered. Note that despite the name, this isn't an
attenuation sweep (RvR) test: attenuation is set once to a single fixed value and left there: the thing
being scanned across is the configuration matrix itself, not signal range.

For each standard/band/bandwidth combination, before any traffic runs, the script asks Expert Analysis
for the theoretical ceiling: `getMCS` (at RSSI=0, i.e. assuming ideal signal conditions) finds the best
MCS that standard/bandwidth/stream-count combination could ever achieve, and `getDRate` converts that
MCS (plus bandwidth, streams, and guard interval) into an actual theoretical data rate in Mbps. That
theoretical rate is the 100% reference point for every loading level tested at that configuration: a
"50% load" test, for example, deliberately offers traffic at half the theoretical rate, not half of
whatever the DUT actually turns out to achieve.

For each resulting combination (standard x band x bandwidth x packet size x direction x loading level),
the script:
* Reconfigures the AP and STA only when the standard or bandwidth has actually changed since the last
  test (to avoid unnecessary reconfiguration churn across what can be a very large matrix) --
  otherwise it just updates the existing traffic pair's offered bitrate, packet length, and direction.
* Runs a short traffic test at the offered rate for that combination.
* Immediately analyzes that one archive (`createReport.analyze()`) to extract the achieved mean
  throughput, logs `{config, data}` for that combination into the result log, and **deletes the
  archive** before moving to the next combination -- since this test can run through a very large
  number of short combinations in one invocation, keeping every raw archive around would use a lot of
  disk space for no benefit once its one number has been extracted.
* The STA can be a real Pal STA, or a plain iperf2/iperf3 client endpoint (`customAlias`/`customIP`/
  `customPort`) instead.

Once every combination has run, the full set of accumulated results is turned into the final report.

## Executable Code
### throughputScan.py
This is the main code, and does almost everything described above: building the full test matrix
(including the theoretical-rate lookups), looping through every combination with the
minimal-reconfiguration logic, running each short test, and triggering the per-combination analysis.
As always, it also does the initial configuration: reading in the configuration files, reading in the
testbed configuration, setting up the directory for output files, etc. `createReport.py` is optional --
the script checks whether it exists before importing it, and skips all analysis/reporting gracefully
if it's missing.

### createReport.py
Two functions:
* **`analyze(directory_name, json_dir, ea_root)`** -- called once per test combination, right after it
  completes. Runs that one archive through the standard Expert Analysis pipeline (zip2csv -> getStats
  -> objectify -> crunch) and returns just the mean achieved throughput for the active traffic pair.
* **`report(directory_name, json_dir, ea_root)`** -- called once at the very end. Reads back every
  accumulated per-combination result from the result log, groups them by (standard, band, channel,
  bandwidth, packet size, direction), and for each group builds one combo chart across loading levels:
  measured throughput as bars, with the theoretical PHY rate and the offered/target rate both drawn as
  reference lines. This is the direct answer to "how close does achieved throughput get to both the
  intended target and the theoretical ceiling, as load increases." The report JSON is always saved
  locally in the script's own directory; if a local Script Manager instance can be reached, it's also
  converted to HTML with a script-manager link (`TestReportLocal.json`).

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `do11n`/`do11ac`/`do11ax` (which standards to include) with matching
`Settings11n`/`Settings11ac`/`Settings11ax` (per-band channel, list of bandwidths, and stream count for
each standard), `packetSizes`, `doUplink`/`doDownlink`, `loadingLevels` (the list of percentages of
theoretical rate to test at each configuration), `palToUse` (a Pal STA, or `"iperf2"`/`"iperf3"` for a
client endpoint, with `customAlias`/`customIP`/`customPort` for the latter), `usePalAsAP` (plus
`palToUseAsAP`/`palToUseAsAPSSID`/`palToUseAsAPPassword`/`palToUseAsAPSecurity`), `attensToUse`/
`quadAttenStart` (a single fixed attenuation, not swept), `iperfMode`, and (for the non-Pal iperf-client
path) `dscp`/`parallel`/`window`/`length`/`settlingTime`.

## Output
This test produces a CSV/JSON/zip archive per combination tested, but **each is deleted immediately**
after its one throughput value is extracted -- what persists is the accumulated result log and the
final report: a local JSON copy, plus an HTML report (and script-manager link) when Script Manager is
reachable locally, containing the measured-vs-theoretical-vs-offered throughput comparison described
above for every combination tested.
