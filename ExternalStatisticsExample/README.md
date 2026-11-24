# ExternalStatisticsExample

This test demonstrates the **External Statistics Interface** (also called the
External Data Interface): a mechanism for pulling proprietary, device-specific
data that the octoBox/Stardust system has no native way to measure, and
merging it directly into the same test record, timeline, and plots as the
built-in measurements (throughput, RSSI, rate, MCS, etc.).

In this example, the "external" data is AP-side RSSI pulled from a Calix
access point over SSH — something Stardust has no built-in way to read. The
same pattern works for any proprietary counter, log value, or sensor reading
you can get your hands on: battery level, temperature, a vendor's internal
signal-quality metric, a competitor's own throughput counter, anything.

## Why this needs an interface at all

Stardust already knows how to measure its own traffic and its own radios. The
External Data Interface exists for the data it *can't* see: something living
on the DUT itself, or on some other proprietary piece of hardware, that only
a vendor-specific script knows how to extract. That extraction script has to
run somewhere, has to run *during* the test (not just at the end), and its
output has to end up in the same test record as everything else so you can
plot it against time or attenuation alongside the built-in metrics. That's
the problem this interface solves.

## The three files, and what each one is responsible for

### 1. `ExternalStatisticsExample.py` — the test script (orchestrator)

This is the actual autotest. It runs on the script machine like any other
test, with one addition: it is responsible for getting the external-data
*plugin* running on the octoBox server, in the background, for the duration
of the test. Concretely, it:

1. Turns on the interface itself:
   ```python
   updateDict = {"externalDataInterfaceEnable": True}
   sd2Utils.updateAutotest(updateDict, pushConfig=True)
   ```
2. Copies the plugin script onto the server. The script runs on the
   **octoBox server**, not the script machine — this matters because the
   plugin needs to talk to Kafka, which runs on the server, not wherever the
   test itself happens to be running. Since a script machine has no direct
   filesystem access to the server, this copy is done over the network via
   `basic-server`'s `/writeFile` API.
3. Starts the actual test with `sd2Utils.startAutotest()` — deliberately the
   *non-blocking* call (not `runAutotest()`), because the script still has
   work to do (starting the plugin) while the test is running, not before or
   after it.
4. Spawns the plugin on the server with `basic-server`'s `/spawn` endpoint
   (also non-blocking — the plugin loops forever until told to stop).
5. Waits for the test to finish (`waitForAutotestDone`), then kills the
   plugin process on the server with `/exec` + `pkill`.
6. Hands the results off to `createReport.py` for analysis.

If you're adapting this test for your own external data source, this file
almost never needs to change — the only test-specific knowledge it needs is
*where* the plugin file lives locally (`localPluginFile` in
`params_test.json`) and what to call it on the server
(`pluginPath`/`pluginName`).

### 2. `calixDataIntegratedSimple.py` — the plugin (runs ON THE SERVER)

This file gets copied to the server and run there for the lifetime of the
test. It is the only file in this trio that is genuinely device-specific —
it's where you'd make changes to support a different DUT or a different
external data source. Structurally, it does two things in a loop:

- **Pulls the data.** In this example, `ssh_to_calix()` opens an SSH session
  to the AP and parses the output of `wlanconfig ... list -h` to get RSSI per
  radio. This part is 100% proprietary to the Calix AP and has nothing to do
  with the interface itself — swap this out entirely for whatever your own
  device needs (a different SSH command, an HTTP API call, reading a log
  file, anything).
- **Publishes the data**, to two different Kafka topics with two different
  purposes:

  | Kafka topic | Purpose | Persists into the test record? |
  |---|---|---|
  | `EXTERNAL_DATA_STREAM` | The actual data point for this instant | **Yes** — this is what `createReport.py` reads back out after the test |
  | `EXTERNAL_PLOT_STREAM` | A full report-JSON structure (plots, histograms, etc.) | No — this is only for *live* visualization while the test is running |

  The data contract for `EXTERNAL_DATA_STREAM` is simple and is the single
  most important thing to get right if you adapt this: whatever JSON object
  you send (other than `timestamp` and `testName`, which are handled
  specially) has each of its keys turned into a column named
  `externalStatistic_<key>` in the final test record. In this example:

  ```python
  my_data = {"timestamp": timestamp, "MAC": thisMAC, "RSSI": thisRSSI, "testName": testName}
  my_producer.send('EXTERNAL_DATA_STREAM', value=my_data)
  ```

  ...is why `createReport.py` is later able to read
  `data["externalStatistic_RSSI"]` out of every row, and
  `dataPerAtten["externalStatistic_RSSI"]["externalStatistic_RSSILogMean"]`
  out of every attenuation step's summary — the EA server automatically
  computed that log-mean (and other stats) from the raw per-second values
  this plugin pushed, with no extra work required here. Push a `"Battery"`
  key instead of `"RSSI"` and you'd get `externalStatistic_Battery`
  everywhere, automatically, no other code changes needed.

### 3. `createReport.py` — the analysis/report script (runs after the test)

Once the test completes, this script turns the raw results zip into the
final report. The flow:

1. `zip2csv` — unpack the results into a flat CSV.
2. `getStats` / `objectify` — turn the CSV into a list of per-row
   dictionaries (`dataSet`), one dict per logged row, every external-data
   key already merged in as `externalStatistic_<key>`.
3. `crunch` — group those rows by attenuation step and compute summary
   statistics (mean, mode, log-mean, etc.) for every column, including the
   external ones.
4. Build time-series and attenuation-series arrays from both, and hand them
   back to `summarize()`, which turns them into the actual plots in the
   final JSON/HTML report.

This is the file this update actually changes — see below.

## What changed in this update

### Five new standard plots

`analyze()` now also builds per-row (i.e. "vs. Time") series for Throughput,
MCS, NSS, Data Rate, and Bandwidth, the same way it already did for RSSI.
`summarize()` renders them as:

- **Throughput vs. Time** — one standalone, full-width plot (800px), no data
  table beneath it.
- **MCS / NSS / Data Rate / Bandwidth vs. Time** — a 2×2 grid of four plots,
  each at half the standalone width (400px), none with a data table beneath
  them, each showing **Tx and Rx as two lines on the same plot**
  (blue/orange), the same way the original RSSI plots show the internal and
  external measurements as two lines on one plot.

(The two original RSSI plots are untouched and still show their data
tables — only the five new plots above were changed to omit theirs.)

### Where the five new column names come from

MCS, NSS, data rate, and bandwidth are always named the same way per Pal
Endpoint, e.g. `"Pal Endpoint 1 TX MCS Mode"` / `"Pal Endpoint 1 RX MCS
Mode"` — these are hardcoded in `ROW_COLUMN_NAMES` in `analyze()`.

Throughput is different: it's named after the **traffic pair itself**, e.g.
`"ServerTopalBox-L2-STApal7 Throughput [Mbps]"`, so there's no fixed string
to hardcode. Instead it's built at runtime from `tpName` — the traffic
pair's name, which `analyze()` already pulls from `getStats()` earlier in
the function (`y["filteredData"]["trafficPairs"]["map"]["0"]`) — via
`"{} Throughput [Mbps]".format(tpName)`. If a test ever has more than one
traffic pair, this only looks at pair `"0"`, matching how the rest of
`analyze()` already scopes everything to a single endpoint/pair.

Every one of these five lookups still fails gracefully to `"#N/A"` per data
point if a name doesn't match what's actually in a given row (same as the
existing RSSI column already does), so a naming mismatch would show up as a
thin or empty-looking plot rather than a crash.

## Files in this test

| File | Role |
|---|---|
| `ExternalStatisticsExample.py` | The autotest script |
| `calixDataIntegratedSimple.py` | The external-data plugin (copied to, and run on, the server) |
| `createReport.py` | Post-test analysis and report generation |
| `params_test.json` | Test parameters, including `pluginPath`/`pluginName`/`localPluginFile` |
| `README.md` | This file |
