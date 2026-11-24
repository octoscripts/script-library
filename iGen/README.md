# iGen

## Test Type
Testbed Use

## Overall Description
A utility script that demonstrates how to control an iGen device (a waveform/traffic generator) directly through the oBox server's `exec`/`spawn` curl-proxy mechanism, rather than through a Wi-Fi traffic pair on the DUT. Unlike most automation scripts in this project, iGen does not run an actual over-the-air Wi-Fi test or produce traffic/expert-analysis style results — it only exercises the iGen's REST API to show how such a device can be queried and driven from script manager.

The script is built around two independently toggleable sections, each guarded by a boolean flag at the top of the section:

* **Waveform section** (`doWaveForm`, default `False`)
  * Reads the iGen's current `/api/wave` state.
  * Computes the AP's center frequency from `primaryChannel` in the params file.
  * Updates the iGen dictionary to put the device into `waveform` mode, radar sub-mode, 0 dB attenuation, and `radar1` radar type, then PUTs it back via curl.
  * Polls `/api/wave` until the reported mode becomes `"waveform"`.
  * Waits 10 seconds, then returns the iGen to `standby` mode.
* **Traffic section** (`doTraffic`, default `True`)
  * Reads the iGen's current `/api/traffic` state.
  * Updates the dictionary to set `mode` to `traffic`, `interface` to `ac`, and `gapValue` to 223, then PUTs it back via curl.
  * Also prints an equivalent URL for the newer Stardust traffic API (`/traffic?mode=traffic&...`) built from the same parameters, for reference/debugging.
  * Polls `/api/traffic` until the reported mode becomes `"playback"`.
  * Waits 10 seconds, then returns the iGen to `standby` mode.

Because all iGen commands go through the oBox server's generic `exec`/`spawn` endpoints (curl wrapped in a REST call) rather than a dedicated iGen driver, this script is primarily meant as a reference/example for how to talk to the iGen until a native API wrapper exists.

## Executable Code
### iGen.py
This is the only file in the test. As always, it performs the standard initial setup: reading in `globalsfile`/`sd2Utils`, pulling in `paramsDict`, resolving the results directory from script manager, applying any alternate test-parameter JSON file, and creating the output folder and result log path.

After that boilerplate, all of the iGen-specific logic (building curl commands, PUTting new state to the iGen, and polling for mode changes) lives directly in this one script. There is no other code of interest, and no traffic pairs, STAs, or sniffers are set up — the DUT/AP referenced in the test description is only required because the AP's channel is used to compute a frequency for the (disabled) waveform section.

## Configurability
Configurable files are always, by default, `params_test.json` and `params_system.json`.
`params_system.json` is for overall system configuration (IP addresses, DUT security, etc.).
`params_test.json` is for changes made to the test itself.

Relevant parameters used by this script include:
* `iGen-A.address` — IP address of the iGen device.
* `oBox_server.publicip` — IP address of the oBox server used to proxy curl commands.
* `primaryChannel` — used only when `doWaveForm` is enabled, to compute the radar frequency.

The `doWaveForm` and `doTraffic` flags are hard-coded in the script body rather than exposed as parameters, so enabling the waveform section (or disabling the traffic section) currently requires editing the script directly.

## Output
This test produces no CSV/JSON expert-analysis output and has no corresponding `createReport.py`. Its only output is the standard test result log file and console/stdout logging of the iGen's reported state at each step (status queries, the curl commands issued, and the mode the iGen reports while polling).
