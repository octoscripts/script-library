# simplest

## Test Type
Testbed Use

## Overall Description
This is the most foundational example script in the suite -- even more stripped-down than
`simpleExample.py`. It sets up a single traffic pair on a single STA and runs it, with no sniffer, no
packet capture, and no attenuation ramp to analyze -- just the bare minimum needed to configure a
testbed device, associate it, run traffic, and produce a report. If you're brand new to writing
automation scripts, this is the one to start with before looking at anything more elaborate.

The thing that makes it genuinely the "simplest" starting point, though, isn't just that it does less
-- it's *how* it's configured. Every device-identifying field in `params_test.json` --
`palToUse`, `attensToUse`, `usePalAsAP` -- is read as a plain text string
(`paramsDict["palToUse"]["val"]`), not unwrapped from a dropdown-style selection list the way `band`,
`iface`, `bw`, and `ulDl` are (those remain genuine multiple-choice options, since their valid values
don't depend on your testbed). That means you don't need Script Manager to have already discovered and
listed your testbed's devices before you can use this script -- as long as you know the names of the
devices in your own testbed, you can type them in directly and run it.

At a high level, the script:
* Sets attenuation on the configured attenuators/MPEs (to a single value, or a fixed range -- this
  test doesn't ramp or collect attenuation-swept results the way an RvR-style test does).
* Optionally sets up a Pal as the AP (`usePalAsAP`); otherwise tests against the real DUT.
* Sets up one traffic pair and one STA, waits for association, and runs the traffic
  (`totalTests` times, if configured for more than one repeat -- each repeat's result archive is saved
  separately).
* Generates the final HTML report via `createReport.py`.

Note: this script did not previously log any test info to the result log at all (no `testresultlog`
content), which would leave `createReport.py` with nothing to read. A basic test-info log entry
(matching the convention used by every other script) was added so the report can be generated, along
with the final run-time log entry and the `createReport.py` call itself -- none of that existed before
this update.

## Executable Code
### simplest.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. The
single traffic pair / STA setup specific to this test is done here.

### createReport.py
Newly added, following this project's standard structure (the same helper functions and overall
layout used across the other scripts' `createReport.py` files). Reads the result-log JSON, finds every
result archive the run produced (one per `totalTests` iteration, labeled separately if there's more
than one), and runs each through Expert Analysis (zip2csv -> objectify -> crunch) to produce this
project's standard plots: Throughput vs. Time (the aggregate), and Data Rate, MCS, Streams, and
Bandwidth vs. Time (UL/DL, combined across every radio endpoint on each chart). Radio endpoints are
labeled with their real name when Expert Analysis can resolve one, falling back to "Pal Endpoint N"
otherwise. Like the other `createReport.py` files, it ends with a commented-out debug block so it can
be run as a standalone script (pointed at an existing results directory) without going through Script
Manager at all.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Key configuration includes: `palToUse` and `attensToUse` (plain text device names -- see above),
`usePalAsAP` (plus `palAPssid`/`palAPsecurity`/`palAPpassword`/`palAPchannel`) to test against a
Pal-as-AP instead of the real DUT, `band`/`primaryChannel`/`bw`/`iface`/`nss`, `ulDl`/`iperfMode`/
`trafficType`/`trafficBW`/`parallel`/`length`, `quadAttenStart`/`quadAttenStop`, and `totalTests` (how
many times to repeat the traffic run).

## Output
This test produces the standard CSV/JSON/zip output (one archive per iteration), plus the HTML report
described above.
