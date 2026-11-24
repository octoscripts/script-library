# simpleExample

## Test Type
Testbed Use

## Overall Description
This is one of the foundational example scripts in the whole automation suite -- the one meant to be
read first. Its job isn't really to test anything in particular; it's to walk through, in order,
every basic building block an automation script needs, using the `sd2Utils` utility library the way
it's meant to be used. If you're writing a new script from scratch, this is the one to start from and
copy patterns out of.

It runs a simple downlink test (one traffic pair, one STA, an attenuation sweep) while also capturing
packets with a sniffer, and produces a full HTML report at the end -- so by the time you've read
through it, you've seen the whole life cycle of a script: configure, run, collect results, report.

### What it walks through, step by step
1. **Boilerplate setup** (everything above the "DO NOT MODIFY" line, common to every script): finding
   the working directory so the script can run standalone from the command line or under Script
   Manager, reading `params_test.json`/`params_system.json` into `paramsDict`, creating the output
   directory, and building the path to the result log file.
2. **Reading test-specific parameters** out of `paramsDict`: which STA and sniffer Pal to use, band/
   channel/bandwidth/interface/streams, SSID/security/password (pulled from `params_system.json`'s
   per-band DUT credentials), traffic direction, and iperf mode.
3. **`sd2Utils.checkSystemConfig()`** -- confirms the testbed actually has the Pals/attenuators this
   test needs before going any further.
4. **Logging basic test info** to the result log (`sd2Utils.logToJSON()`) -- the test's own
   configuration, software versions, firmware versions -- so the final report has something to read
   back later. Every script that wants a report needs to do this.
5. **Setting attenuation** (`sd2Utils.setAtten()`) for the configured sweep range.
6. **Setting up a traffic pair** (`sd2Utils.setupTrafficPairs()`) between the STA and the server (or a
   Pal configured as the AP, if `usePalAsAP` is set -- this script illustrates that option too, as an
   alternative to testing against the real DUT).
7. **Setting up and associating the STA** (`sd2Utils.setupSTA()`, `sd2Utils.waitForAssociation()`).
8. **Setting up a sniffer** (`sd2Utils.setupSniffer()`), if `runPcapAnalysis` is enabled -- including
   making sure the `SnifferRelay` background service is running first. This is the part of the script
   specifically meant to illustrate packet-capture setup: starting the sniffer just before the traffic
   run, stopping it right after (`sd2Utils.stopSniffers()`) to get the first capture, and then --
   purely as an illustration of how you'd do it a second time if a test needed to -- optionally
   starting and stopping it again a few seconds later for a second, separate capture
   (`doSecondCapture`).
9. **Running the traffic** (`sd2Utils.runAutotest()`) and collecting results
   (`sd2Utils.avgDataPost()`) -- average throughput and mean management RSSI, logged into the result
   log under a band/direction key.
10. **Exporting a time-aligned JSON** and, optionally, a **PDF report** directly from the server's own
    REST API, alongside the usual Script Manager result archive.
11. **Generating the final HTML report** via `createReport.py` -- see below.

## Executable Code
### simpleExample.py
This is the main code, and walks through everything above in order. As always, it does the initial
configuration: reading in the configuration files, reading in the testbed configuration, setting up
the directory for output files, etc.

### createReport.py
Reads the result log and the raw JSON result archive (analyzed via Expert Analysis), and builds the
HTML report: an RvR throughput plot, an RvR RSSI plot, and time-series plots of average throughput,
PHY rate, MCS, bandwidth, and spatial streams (UL and DL) for the STA.

## simpleExample-REST-ONLY.py: the same idea, without sd2Utils
This companion script exists to show the other way of doing all of this: talking to the Octobox
server's REST API directly, with plain `requests` calls, instead of going through `sd2Utils`. It's not
meant to be run as a normal Script Manager automation script -- it has no `params_test.json`, no
output directory, no result log, and no `createReport.py` call. Everything is hardcoded in the script
itself (there's even a `usePal6Stack` flag near the top to switch between two different hardcoded
testbed setups).

What it actually does:
* **Builds the entire test configuration by hand.** Where `simpleExample.py` calls
  `sd2Utils.setupTrafficPairs()`/`setupSTA()` and lets `sd2Utils` assemble the right JSON underneath,
  this script defines the whole `autotest_dict` test configuration as one large, literal Python
  dictionary -- traffic pairs, Pal configuration, attenuators, all of it -- and POSTs it straight to
  `/api/v1/testConfigs`. This is the clearest way to see exactly what shape of JSON `sd2Utils` is
  building on your behalf when you call its higher-level functions.
* **Validates and auto-corrects the Pal types itself (`validateMe()`).** It fetches the testbed's
  actual component inventory (`/api/v1/testbedComponents`) and cross-checks it against what the
  hardcoded configuration *claims* each Pal is (Pal6 vs. Pal7 -- which use different radio-naming
  schemes, e.g. `RADIO_5` vs. `RADIO_5A`). If a management address is really a Pal7 but the
  configuration called it a Pal6 (or vice versa), it fixes the configuration automatically. This is a
  good illustration of exactly the kind of testbed-aware bookkeeping that `sd2Utils`'s own setup
  functions normally handle for you without your having to think about it.
* **Listens for association status directly over the socket**, using `StardustSocketListen` itself
  (subscribing to the `PAL_STATUS` namespace for the target Pal's management address, with a plain
  callback function) rather than calling `sd2Utils.waitForAssociation()`. This is the same mechanism
  `sd2Utils` uses internally, shown explicitly.
* Initializes and starts the test the same way the "real" script does (`/api/v1/testConfigs/initialize`,
  `/api/v1/autotest/start`), but via direct REST calls rather than `sd2Utils` wrappers, and doesn't wait
  for completion or collect any results -- it stops once the test has been kicked off.

In short: read `simpleExample.py` to learn the normal, supported way to write a test. Read
`simpleExample-REST-ONLY.py` afterward if you want to see what's actually happening underneath, or if
you have a reason to talk to the API directly instead of through `sd2Utils`.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

For `simpleExample.py`: `palToUseSTA`/`palToUseSniffer`, `primaryChannel`/`bw`/`iface`/`nss`, `ulDl`/
`iperfMode`, `quadAttenStart`/`quadAttenStop`, `usePalAsAP` (plus `palAPssid`/`palAPsecurity`/
`palAPpassword`/`palAPchannel`), `runPcapAnalysis`/`snifferBW`/`headersOnly`/`managementOnly`,
`doSecondCapture`, and `doPDF`.

`simpleExample-REST-ONLY.py` has no configuration file at all -- the server address, SSID/security/
password, and the entire test configuration are hardcoded in the script, with `usePal6Stack` as the
only switch (between two different hardcoded testbeds).

## Output
`simpleExample.py` produces the standard CSV/JSON/pcap output (including a second pcap if
`doSecondCapture` is enabled), a time-aligned JSON export, an optional PDF, and the HTML report
described above.

`simpleExample-REST-ONLY.py` produces nothing of its own -- it starts the test running on the server
and exits; whatever that test configuration itself is set up to produce happens independently of this
script.
