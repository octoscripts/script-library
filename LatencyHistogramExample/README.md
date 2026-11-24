# LatencyHistogramExample

## Test Type
Testbed Use

## Overall Description
An example showing how to gather and plot per-packet one-way-latency histograms from an iPerf2
traffic pair, for people who want to use Latency Histograms in their own tests. It runs one traffic
pair (with iPerf2's histogram option enabled) and one separate ping pair on a single STA (optionally
against a Pal configured as the AP, instead of the real DUT), at a single fixed attenuation setting --
there's no attenuation sweep here, since the point is the latency-histogram data itself, not an RvR
curve.

At a high level, the script:
* Sets all attenuators to isolate the boxes, then to the single configured attenuation value.
* Optionally sets up a Pal as the AP (`usePalAsAp`); otherwise tests against the real DUT.
* Sets up a ping pair and a traffic pair on two separate STAs (`palToUsePing` and `palToUseSTA`). The
  traffic pair is configured with iPerf2 histogram collection turned on: a 50,000-bin histogram,
  20 usec bin width, and 90%/99% confidence-interval thresholds pre-calculated per second.
* Runs the traffic, then deletes the CSV-only zip (not needed here; the full JSON archive is used
  instead).
* Calls `createReport.extract()` to pull the per-second histogram data (and the overall throughput/
  ping averages) out of the result archive, and `createReport.plot()` to turn that into the HTML
  report.

## Executable Code
### LatencyHistogramExample.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. All of
the ping-pair/traffic-pair/histogram-override setup specific to this test is done here.

### createReport.py
Two functions, called separately (not a single combined flow like most other scripts):

* **`extract(json_path, ea_root)`** -- runs the result archive directly through Expert Analysis
  (zip2csv -> getStats -> objectify -> crunch), and exits with an error if the archive doesn't have
  exactly one traffic pair and one ping pair (this example assumes that shape). Pulls overall mean
  throughput and mean ping latency from the crunched data, then goes back to the raw per-second
  `dataSet` to pull out, for every second of the run: the histogram itself (bins/counts/intervals/
  percentiles/bin width), the OBL/OBU/outlier counts, iPerf2's own reported min/mean/max one-way
  delay, and the ping pair's latency. All of that gets logged to the result log as `LatencyHists`.
* **`plot(directory_name, json_dir)`** -- reads `LatencyHists` back out of the result log and builds
  six plots: every second's full latency histogram overlaid on one chart (so you can see the
  distribution shift over the run); the pre-calculated percentile thresholds vs. time; edge events
  (OBL/OBU/outlier counts) vs. time; iPerf2's own min/mean/max one-way-delay vs. time; the separate
  ping pair's latency vs. time; and a direct comparison of the histogram percentile, iPerf2 OWD mean,
  and ping latency together on one chart. Then converts the report to HTML the usual way.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `eaLocation` (use a local or remote Expert Analysis instance),
`palToUseSTA`/`palToUsePing` (the traffic and ping STAs), `usePalAsAp`, `primaryChannel`/`bw`/`iface`/
`nss`, `ulDl`/`iperfMode`/`trafficBW`, and `quadAttenStart`/`quadAttenStop` (a single fixed
attenuation, not a sweep).

The histogram settings themselves (bin count, bin width, confidence-interval thresholds) are
currently **hardcoded** in the script rather than exposed in params_test.json -- worth pulling out
into configuration if you adapt this example, since that's the actual point of the test.

## Output
This test produces the standard JSON/zip output (the CSV-only zip is deleted after the run, since it
isn't needed), plus the HTML report described above: all latency histograms overlaid, percentile
thresholds vs. time, edge events vs. time, iPerf2 OWD vs. time, ping latency vs. time, and a
side-by-side latency comparison.
