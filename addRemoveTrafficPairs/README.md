# addRemoveTrafficPairs

## Test Type
Testbed Use

## Overall Description
A test designed to show how to add and remove traffic pairs from a test using automation.
The automation creates a simple test made up of many different traffic pair (16 by default.)
It then:
* Activates only one of the traffic pairs.
* Starts the test
* Waits 20 seconds and activates another traffic pair.
* Waits 20 seconds and activates yet another traffic pair.
* Etc. until all traffic pairs have been activated.
* Ends the test

## Executable Code
### addRemoveTrafficPairs.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
All manipulation of the traffic pairs is done in this code.

### createReport.py
Run automatically at the end of the script. Reads the result-log JSON produced above, along with the
raw JSON result archive (analyzed via Expert Analysis), and produces the final HTML report. Since
this test activates up to 16 traffic pairs one at a time, the report includes a per-traffic-pair
throughput-vs-time plot (so each pair's active window is visible), plus PHY rate, MCS, bandwidth,
and spatial-stream plots (UL and DL) vs. time, for every radio endpoint in the test.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Very basic configuration is available in this test.  The protocol type, traffic settings, etc.
Most information, like the names of devices to use, are hard-coded in this script.

## Output
In addition to the standard CSV/JSON output, this test now generates an HTML report via
`createReport.py` (throughput per traffic pair, and PHY rate/MCS/bandwidth/streams per radio
endpoint, all vs. time). Note that this test doesn't run an attenuation sweep, so the report has no
RvR throughput/RSSI plots -- those are only produced for tests that log a swept result.