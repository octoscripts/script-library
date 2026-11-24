# multiPair

## Test Type
Basic Functionality

## Overall Description
Runs traffic simultaneously across multiple Pal STA endpoints -- supporting dual- and tri-band
configurations, and bidirectional traffic -- against either the real DUT or a Pal configured as the
AP. Each STA and each traffic pair is independently configurable (band, direction, traffic type/rate,
packet size, streams, window, ping interval, and optional isochronous/advanced settings), so this can
model anything from a simple two-endpoint test up to several simultaneous multi-band clients each
with their own traffic profile. An attenuation sweep is run (across one or more attenuators/MPEs)
during the traffic run, giving RvR-style results for every endpoint at once.

At a high level, the script:
* Sets the configured attenuators/MPEs to isolate the boxes, then to the sweep range.
* Optionally sets up a Pal as the AP (`palAsAP`), with its own SSID/security/password, across
  whichever of 2.4/5A/5B/6 GHz radios are enabled for the configured band config (dual or tri-band);
  otherwise tests against the real DUT.
* Sets up one traffic pair per entry in `trafficPairs`, each on its own configured band/direction,
  with its own traffic settings (falling back to global defaults for anything not overridden).
* Sets up one STA per entry in `palStations`, each with its own band/channel/bandwidth/security
  settings (pulled from the Pal-as-AP's credentials if `palAsAP` is in use, or from the DUT's
  per-band credentials otherwise).
* Waits for every configured STA to associate, then runs the traffic.
* Generates the final HTML report via `createReport.py` (optional -- the script checks whether it
  exists before importing it, and skips reporting gracefully if it's missing).

## Executable Code
### multiPair.py
This is the main code. As always, it does the initial configuration: reading in the configuration
files, reading in the testbed configuration, setting up the directory for output files, etc. All of
the multi-STA/multi-band/multi-traffic-pair setup is done here.

### createReport.py
Processes every result archive found (normally just the one this test produces) through the Expert
Analysis pipeline (zip2csv -> objectify -> getStats -> crunch), and builds a notably thorough report:
* **Attenuation-swept views**: Throughput vs. Attenuation (aggregate, plus one curve per traffic
  pair), and -- when present -- iPerf2 Latency vs. Attenuation and Ping Latency vs. Attenuation.
* **RSSI-based views**: Throughput vs. Control RSSI, overlaid with the *theoretical* expected
  throughput for 802.11ax/ac/n at each measured RSSI/bandwidth/stream-count combination (computed via
  Expert Analysis' `getMCS`/`getDRate` endpoints) -- so measured throughput can be compared directly
  against the theoretical maximum for each standard. Also Ping Latency vs. Control RSSI, when present.
* **Time-series views**, one line per Pal endpoint (Rx and Tx separately): Throughput, iPerf2 Latency,
  Ping Latency, Data Rate, MCS, Spatial Streams, and Bandwidth.
* An Alerts section.

If Script Manager can be reached locally, the report is converted to HTML and a link is published
(`TestReportLocal.json`). There's also a commented-out alternate path for uploading results to a
cloud/S3-backed Expert Analysis instance and publishing a cloud link instead -- not currently active.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

This test has unusually rich per-entry configurability:
* `palStations` -- a list of STA definitions, one per simultaneous endpoint, each independently
  able to set `band`/`type`/`channel`/`bandConfig`/`streams`/`ssid`/`security`/`password`/`bandwidth`.
* `trafficPairs` -- a list of traffic-pair definitions, one per pair, each independently able to
  override `band`/`updn`/`trafficType`/`packetType`/`trafficRate`/`packetSize`/`trafficStreams`/
  `windowSize`/`pingInterval`/`advanced` (and, when advanced, `isochronous`/`dscp`/`iso_gap`/
  `iso_mean`/`iso_stdev`/`iso_fps`) -- falling back to the global defaults below for anything not set.
* Global traffic defaults: `trafficType`/`trafficMode`/`trafficBW`/`length`/`parallel`/`window`/
  `pingInterval`/`trafficAdvanced`/`useNagles`/`setMss`.
* `palAsAP`/`palAPbandConfig` (dual or tri-band) plus `palAPssid`/`palAPsecurity`/`palAPpass` and
  per-radio channels (`palAPchannel_24g`/`palAPchannel_5g`/`palAPchannel_5Ag`/`palAPchannel_5Bg`/
  `palAPchannel6g`), when testing against a Pal-as-AP instead of the real DUT.
* `attensToUse` (the attenuators/MPEs in play) and `quadAttenStart`/`quadAttenStop` (the shared sweep
  range).

## Output
This test produces the standard CSV/JSON/zip output, plus the HTML report described above (written
locally via Script Manager; the cloud-upload path exists in the code but is commented out).
