# interactiveExample

## Test Type
Testbed Use

## Overall Description
A single-rate throughput test (set up one traffic pair, one STA, and an optional sniffer, then run traffic) that doubles as the reference example for making a Script Manager automation **interactive** — that is, able to pause mid-run and wait for a person to actively tell it to continue, rather than simply running start-to-finish unattended.

The interactive mechanism works through a small sidecar file, `interactive.json`, that lives alongside the script and holds a single toggle:

```json
{
  "go_flag": {
    "val": true,
    "label": "Toggle switch to allow the script to proceed from the point that this is checked."
  }
}
```

Script Manager treats this file as a *live* parameter for the currently running test — its `label` is shown next to an on/off control in the SM UI, and whatever value is stored in the file at any moment reflects (and can be changed through) that control while the script is running. The script uses this in three steps:

1. **Reset the flag at start-up.** Immediately after the standard boilerplate, the script opens `interactive.json` (creating it with a sensible default if it doesn't exist yet) and forces `go_flag` back to `False`. This guarantees a stale `true` left over from a previous run can't let the test skip straight through.
2. **Do all of the normal test setup anyway.** Attenuators are set, the sniffer (if enabled) is configured and started, traffic pairs are built, and the STA is configured, started, and associated — exactly as a non-interactive test would do. Nothing about setup depends on the flag.
3. **Block just before running traffic.** Once setup and association are complete, the script prints `"When you are ready to let this script go, enable the GO flag."` and then polls `interactive.json` every 10 seconds, re-reading `go_flag` on every pass. While it is `False`, the script simply sleeps and waits — the testbed is fully configured and associated, but no traffic runs yet. This is the window where a person can look at the live SM UI, inspect or adjust the testbed by hand, and decide when the test should actually proceed. As soon as someone flips the toggle in SM (setting `go_flag` to `true` in the file), the loop exits and the script continues.

After that gate, the rest of the test is conventional: it runs the autotest, pulls average throughput and management RSSI, optionally tears down and re-associates the STA to take a second sniffer capture (so packets can be decrypted), logs results to the test result JSON, generates the PDF/HTML reports via `createReport.py`, and exits.

## Executable Code
### interactiveExample.py
This is the main script. As always, it performs the standard initial configuration (reading `globalsfile`/`sd2Utils`, resolving `paramsDict`, getting the results directory from script manager, applying any alternate parameters file, and creating the output folder and result log path).

The interactive behavior — creating/resetting `interactive.json` and the polling wait loop — is implemented directly in this script, right after setup and before the attenuation/traffic-pair/STA configuration that follows. Everything else (attenuation, sniffer setup, traffic pair and STA setup, association wait, running the autotest, pulling throughput/RSSI results, and generating reports) follows the same pattern used by the other simple examples in this project.

### createReport.py
Generates the HTML/PDF test report from the results produced above. In addition to the existing RvR-style throughput and mean management RSSI plots (vs. attenuation), it now also builds the project's standard time-based plots directly from the per-second results data:
* **Throughput vs. Time** — a single plot with one line per traffic endpoint.
* **MCS, Spatial Streams, Bandwidth, and PHY Rate vs. Time** — shown as a 2x2 grid per radio endpoint, with uplink (TX) and downlink (RX) combined on each plot. These four plots are shown without data tables, to keep the grid compact.

These are pulled from the zipped per-second results via the expert analysis `zip2csv`/`objectify` APIs, so they appear automatically for any radio/traffic endpoints present in the run — no extra configuration is needed.

## Configurability
Configurable files are always, by default, `params_test.json` and `params_system.json`.
`params_system.json` is for overall system configuration (IP addresses, DUT security, etc.).
`params_test.json` is for changes made to the test itself (interface, bandwidth, streams, traffic direction, iperf mode, attenuation range, whether to run sniffer/PCAP analysis, etc.), following the same pattern as the other simple examples.

`interactive.json` is a special case: it is not a normal start-of-test configuration file. It is read and rewritten *while the test is running* and exists specifically so Script Manager can expose the `go_flag` toggle as a live control in its UI during the run — it's how a person interacts with an otherwise automated script partway through, rather than only before it starts.

## Output
This test produces the standard CSV/JSON/zip output plus the generated PDF and HTML reports (via `createReport.py`), now including the standard throughput-vs-time and MCS/streams/bandwidth/PHY-rate-vs-time plots described above. No further analysis beyond that is performed.
