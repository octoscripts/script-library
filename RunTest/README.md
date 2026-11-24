# RunTest

## Test Type
Testbed Use

## Overall Description
Runs an already-configured test on the server via its REST API -- useful when a test has been built
through the UI (or any other way) and you just want to automate running it repeatedly, without
reconfiguring anything. The script doesn't know or care what the named test actually does; it just
initializes it, starts it, waits for it to finish, and downloads the resulting JSON report.

At a high level, the script:
* Initializes the named test configuration (`POST /api/v1/testConfigs/initialize/<test_name>`). If the
  name isn't recognized, it fetches the full list of configured test names from the server, prints
  them so you can pick a valid one, and exits.
* Starts the test (`POST /api/v1/autotest/start/<test_name>`) with `pushConfigs: False` -- meaning it
  runs the test exactly as already configured on the server, pushing no new configuration.
* Waits for the configured duration (`sd2Utils.waitForAutotestDone(testDuration=...)`).
* Downloads the JSON zip report (`GET /api/v1/reports/json/<test_name>`) and saves it using the usual
  timestamped filename convention.

There is no `createReport.py` for this script, intentionally: since the named test can be literally
anything, there's no fixed set of plots or data that would make sense to generate automatically.

## RunTest.py vs. RunTestVerySmall.py
Both scripts do the same underlying thing -- initialize, start, wait, download the report -- via the
same three REST calls, but they're built for very different contexts:

* **RunTest.py** is a full Script Manager automation script: it reads `params_test.json`/
  `params_system.json` for the test name and server address, creates its output directory and result
  log through the normal Script Manager conventions, and waits for completion using the shared
  `sd2Utils.waitForAutotestDone()` helper. It runs the configured test exactly once per invocation
  (looping it multiple times means running it multiple times through Script Manager, or wrapping it
  yourself).
* **RunTestVerySmall.py** has none of that -- no Script Manager integration, no `params_test.json`, no
  output directory or result log. The test name, server IP, and REST timeout are all hardcoded at the
  top of the file, and it polls completion itself (checking `/api/v1/activeTest/get` for the test
  name's absence, with a simple timeout fallback) rather than using a shared helper. In exchange, it
  does one thing RunTest.py doesn't: it loops the whole initialize/start/wait/download sequence
  `howManyTimes` (hardcoded to 3) in a single run, saving each iteration's report as `json_<N>.zip` in
  the current directory. It's meant to be run directly with plain Python from the command line, not
  through Script Manager -- a minimal, standalone example of repeatedly driving the REST API with as
  little scaffolding as possible.

In short: use RunTest.py when you want this wired into the normal automation framework (configurable,
logged, reported on like any other script); use RunTestVerySmall.py as a quick, dependency-free way to
fire off the same test a few times from a plain Python shell.

## Executable Code
### RunTest.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. Starting
and monitoring the named test, and downloading its report, is all done here -- there's no other code
involved.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

The only test-specific configuration is `testName` (which already-configured test to run) and
`testDuration` (how long to wait for it to finish). `RunTestVerySmall.py` has no configuration file at
all -- its test name, server IP, timeout, and repeat count are hardcoded and must be edited directly in
the script.

## Output
This test produces a single JSON zip report, downloaded from the server exactly as the named test's
own configuration produces it. There is no additional analysis, plots, or HTML report -- what you get
is whatever the underlying test itself was already set up to generate.
