# throughputSearchConfigurable

## Test Type
Basic Functionality

## Overall Description
Finds the maximum sustainable throughput for increasing numbers of simultaneous traffic streams
(vSTAs, if the STA is a Pal6 that supports them), across a configurable matrix of packet size, TCP MSS,
direction, and traffic mode (TCP and/or UDP) -- and the method used to find "maximum" is genuinely
different depending on which traffic mode is being tested:

* **TCP**: there's no meaningful packet-loss target for TCP (TCP's own congestion control already
  prevents meaningful loss under normal conditions), so the test just offers traffic at the
  unconstrained max rate (`0M`, i.e. "as fast as possible") and reports whatever throughput results.
  There's no search here at all -- one test per configuration is enough.
* **UDP**: UDP has no built-in flow control, so overloading the link produces real, measurable packet
  loss. For each configuration, the test runs an actual **binary search** over the offered bitrate,
  looking for the specific rate that produces packet loss right at (not below, not far above) the
  configured target percentage (`thresholdPercent`). Each iteration either raises or lowers the
  offered rate based on whether every active traffic pair passed the loss threshold, halving the step
  size each time, until the step size shrinks below `bitrateThreshold` (convergence) or the loss
  threshold is satisfied.

For each number of active traffic pairs/vSTAs (stepping from `tpairCountStart` to `tpairCountStop` by
`tpairCountStep`), the search above runs to convergence, and the result -- the per-vSTA rate that hit
the target loss (or the unconstrained TCP rate) -- becomes the headline number for that pair count.
Once one pair count's search converges, the next pair count's search starts from a bitrate scaled down
proportionally (so it doesn't have to search from scratch each time), and the whole process repeats
until `tpairCountStop` is reached. The result, across the whole run, is a curve of "how much throughput
can you sustain per stream as you add more simultaneous streams," at a fixed target loss level.

The STA can be a real Pal6 (vSTAs only make sense on a Pal6, since they're the ones that support
virtual stations), or a plain iperf2/iperf3/multiperf client endpoint instead -- in which case only one
traffic pair exists (vSTA count stepping doesn't apply) and `customAlias`/`customIP`/`customPort` (or
the configured multiperf device) identify the non-Pal side of the pair.

The report is regenerated after *every* search iteration, not just at the end, for interim visibility
into the search as it progresses (and published to a Kafka `plotStream` topic too, if a broker is
reachable) -- so you can watch the binary search converge live rather than only seeing the final
answer.

## The search algorithm, in detail
`selectNewRate()` implements both search strategies:
* **`"highToLow"`** (used for TCP): simply decrements the offered rate by a fixed amount (10 Mbps) each
  iteration -- a straightforward ramp-down, not really a search, since TCP always "passes" (there's no
  loss target to search for) and the first result is kept.
* **`"search"`** (used for UDP): a true binary search. If the last trial passed the loss threshold, it
  becomes the new known-good lower bound; if it failed, it becomes the new known-bad upper bound. The
  next step size is set to double the known-good rate (if no known-bad rate exists yet), half the
  known-bad rate (if no known-good rate exists yet), or half the *gap* between the known-good and
  known-bad rates (once both exist) -- the classic binary-search halving pattern, converging on the
  boundary between "passes" and "fails" rather than searching blindly.

Note that packet loss here is **derived**, not taken from iPerf's own reported loss statistic: for each
active traffic pair, `createReport.extract()` computes `1 - (measured throughput / offered rate per
vSTA)` and uses that as the loss percentage for every pass/fail decision, rather than trusting iPerf's
self-reported value.

## Executable Code
### throughputSearchConfigurable.py
This is the main code, and drives essentially everything described above: building the vSTA/traffic
pair configuration, the outer loop over traffic-pair counts, and the inner binary-search (or ramp-down)
loop for each one. As always, it also does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc.

### createReport.py
Two functions:
* **`extract(directory_name, fileName, ea_root, useTPairs, bitrate)`** -- called after every single
  search iteration. Runs that one iteration's archive through the standard Expert Analysis pipeline
  (zip2csv -> objectify -> getStats -> crunch), pulls per-traffic-pair throughput/latency, computes the
  derived loss percentage described above for each active pair, and returns the result for that one
  trial (used immediately to decide the next search step).
* **`main(directory_name, json_dir, ea_root)`** -- called after every iteration too, for the live
  interim report, and once more at the very end for the final one. Builds: a plot of per-vSTA
  throughput achieved vs. number of active vSTAs/traffic pairs (the final, converged answer for each
  pair count); for every configuration searched, a "path to solution" plot showing the actual sequence
  of trial bitrates the search took to converge (so you can see the binary search -- or the TCP
  ramp-down -- happening step by step, not just its answer); and a final summary table across every
  configuration tested (traffic pair count, offered load, average/total throughput, average loss, and
  average latency -- loss and latency are reported as "N/A" for TCP, since those aren't meaningful
  there).

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `palToUse` (a Pal6 STA, or `"iperf2"`/`"iperf3"`/`"multiperf"` for a client
endpoint), `numberOfVstas` (how many vSTAs to configure -- must be 1 for a non-Pal STA),
`band`/`primaryChannel`/`bw`/`iface`/`nss`/`txAtten`, `thresholdPercent` (the target UDP packet-loss
percentage to search for), `tpairCountStart`/`tpairCountStop`/`tpairCountStep` (the outer loop over
simultaneous traffic pairs), `bitrateThreshold` (the binary search's convergence step size),
`searchType` (`"search"` for the real binary search, `"highToLow"` for a simple ramp-down),
`packetSizes`/`MSSes`, `doUplink`/`doDownlink`/`doBidirectional`, `doTCP`/`doUDP`,
`usePalAsAP` (plus its band/channel/SSID/security/password), `attensToUse`/`quadAttenValue` (a single
fixed attenuation, not swept), and `earlyExit.json` (a separate file checked every iteration, letting
you stop a long-running search early without killing the script outright).

## Output
This test produces a CSV/JSON/zip archive per search iteration (named by its rate/packet size/MSS/
direction/pair count/traffic mode), a `TestResults.json_<config>` file per configuration (the
interim/final search results for that specific configuration), an `AllResults.json` with every
configuration's converged result, plus the HTML report described above -- regenerated after every
search iteration for live visibility, and published to Kafka's `plotStream` topic too if a broker is
reachable.
