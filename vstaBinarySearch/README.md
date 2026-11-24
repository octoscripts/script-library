# vstaBinarySearch

## Test Type
Basic Functionality

## Overall Description
Answers a specific capacity question: *given a fixed per-user data rate B, what's the largest number
of simultaneous users N the system can support while keeping packet loss below a target threshold T?*
Each "user" is a vSTA (virtual STA) -- one or more Pal6es are configured to create a pool of vSTAs up
front, and the test searches, by binary search, for the largest subset of that pool that can run
traffic at rate B each without exceeding the loss target. Since loss percentage requires UDP, this
test only accepts `trafficMode = "udp"` and exits immediately if anything else is configured.

### The number of vSTAs created at setup is the ceiling on what the search can ever find
This is the detail worth understanding before running the test: **the pool of vSTAs you configure at
setup time (`vstaSettings`) is the maximum possible value the search can ever return for N.** The very
first thing the test does, before any binary search begins, is run one trial using *every* vSTA in the
pool active at once. If that trial's packet loss is **already below** the target threshold T -- meaning
even the maximum possible N isn't enough to drive loss above the target -- **the test cannot answer the
question as configured**, and it stops immediately with a message to the effect of "the packet loss
with the largest number of traffic pairs is already below the limit; increase the number of vSTAs to
finish this test." There's no point searching in that case: the true answer lies somewhere above the
ceiling you gave it, which the test has no way to reach.

If that first full-pool trial *does* show loss above the target, the search proceeds: a second trial
runs with just one active vSTA (establishing the opposite end of the range), and from there a true
binary search narrows in -- each trial's result becomes a new known-good or known-bad bound, and the
next N tried is the midpoint between the current known-good and known-bad values. The search ends when
the gap between the best known-good N and the best known-bad N shrinks to `stepSizeTarget` or less.
Once that gap is found, the test also fills in every value strictly between the final good and bad
bounds, so the full picture across that narrow range is captured, not just the two boundary points.

A few more details worth knowing about how each trial is run:
* **Which vSTAs are active is chosen randomly** for each trial (not always "the first N"), and the
  selection deliberately avoids any vSTA previously flagged as behaving anomalously ("bad pairs" --
  ones that failed to report sensible throughput/loss data) -- falling back to allowing all vSTAs again
  if there aren't enough "good" ones left to reach the requested count.
* **The loss metric used isn't a simple average.** It's a configurable quantile (`lossQuantile`) of the
  loss distribution across active pairs -- a more robust choice than a plain mean, since it won't be
  thrown off by one unusually bad (or good) outlier pair.

## Executable Code
### vstaBinarySearch.py
This is the main code, and does everything described above: creating the vSTA pool across the
configured Pal6es/radios, the initial full-pool and single-vSTA trials, the binary search loop, and the
"not enough vSTAs" early-exit check. As always, it also does the initial configuration: reading in the
configuration files, reading in the testbed configuration, setting up the directory for output files,
etc.

### createReport_0e240a.py
Reads back every trial's result and builds: Packet Loss vs. Number of Pairs (the key plot -- every N
tried, and whether it landed above or below the target, letting you see the search's convergence
directly); Aggregate Throughput vs. Number of Pairs; a "throughput divergence from expectation" plot
(actual aggregate throughput vs. the theoretical N x B ideal, showing how far short of ideal the system
falls as N grows); a "found vs. expected pairs" plot (surfacing how many of the expected active vSTAs
actually reported usable data at each N, which is how "bad pairs" show up visually); the headline
answer -- the results for the highest N found to support the loss target; and, for the final converged
good case, bad case, and an aggregated view of the good case, the detailed per-trial loss distribution
at the configured quantile.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `palsToUse` (one or more Pal6es to create vSTAs across),
`vstaSettings` (per-radio band/bandwidth/interface/streams/channel/txAtten and, critically, how many
vSTAs to create on each -- this sets the ceiling described above), `trafficBW` (the fixed per-vSTA
rate B), `trafficMode` (must be `"udp"`), `upOrDown`, `packetLossTarget` (the threshold T),
`stepSizeTarget` (how small the good/bad gap must shrink to before the search stops),
`lossQuantile` (which quantile of the per-pair loss distribution to use as the loss metric),
`attensToUse`/`quadAttenStart`/`quadAttenStop` (a single fixed attenuation, not swept), `eaLocation`,
and `vstaWait` (extra settling time per vSTA added to association waits).

## Output
This test produces the standard CSV/JSON/zip output per trial, plus the HTML report described above --
the packet-loss-vs-pair-count convergence plot, throughput and divergence-from-expectation plots, the
found-vs-expected-pairs diagnostic, the headline "highest supported N" result, and the detailed
loss-distribution plots for the final good/bad boundary cases. If the test exited early because even
the full vSTA pool was already below the loss target, the report reflects that outcome rather than a
completed search.
