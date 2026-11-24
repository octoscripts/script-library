# anyModeRvR

## Test Type
Basic Functionality

## Overall Description
A test designed to do an RvR test of any of the various types.  So:
RvR
RvRwR
RvRvO
RvOvR
The traffic is run between a DUT and a configurable list of STA endpoints.
Very simple Throughput-vs-Attenuation plots are generated.

## Executable Code
### anymodeRvR.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
### createReport.py
This is the post-run analysis code. It reads the RvR-vs-attenuation data that anyModeRvR.py collects
via the avgData API (stored in the testResultsLog file) and plots simple Throughput/RSSI-vs-Attenuation
curves, same as before.

In addition, it now runs the raw JSON result archive through Expert Analysis (the zip2csv -> objectify
-> crunch pipeline) to produce: Throughput vs. Time (aggregate and per traffic pair), and PHY
Rate/MCS/Bandwidth/Streams vs. Time (UL and DL) for every radio endpoint.

For `rvrMode` values other than plain `RvR` (i.e. RvRwR, RvRvO, RvOvR, which add a turntable
rotation), it also builds angle-based plots -- Throughput, Data RSSI, MCS, Bandwidth, and Streams vs.
Angle, one radar chart per attenuation step -- using the per-angle ("perPos") breakdown Expert
Analysis computes during crunch. These are skipped automatically for plain `RvR` mode, since there's
no rotation and therefore no angle data to plot.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Very basic configuration is available in this test.  The protocol type, traffic settings, etc.
The STA device is configurable, but from within a list that may need to be modified for any given testbed.

## Output
This test produces the CSV, JSON etc. output.
In addition, createReport.py produces an HTML report with: RvR (Throughput/RSSI vs. Attenuation)
curves; Throughput/PHY Rate/MCS/Bandwidth/Streams vs. Time; and, for turntable modes (RvRwR, RvRvO,
RvOvR), Throughput/RSSI/MCS/Bandwidth/Streams vs. Angle.