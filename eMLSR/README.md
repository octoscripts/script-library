# eMLSR

## Test Type
Advanced Test

## Overall Description
This is a fairly complex test, or set of tests, designed to expose eMLSR operation.

The idea is to run traffic in a clean environment (which will select one of the bands to use), and then to
add interference into the test to drive the traffic from one band to a different band by congesting the various bands.

1. Understand the MLO configuration.  Imagine it is a 5/6 GHz configuration.
2. Run traffic on 5 GHz only.
3. Run traffic on 6 GHz only.
4. Run traffic on 5 GHz with 5 GHz OBSS interference.
5. Run traffic on 5 GHz with 6 GHz OBSS interference.
(etc.)
6. Set up the MLO configuration.
7. Run traffic with 5/6 configured.  (Only one band can be used, since this is eMLSR.  Which band is up to the devices.)
8. Run traffic with 5/6 configured and 5 GHz OBSS.
9. Run traffic with 5/6 configured and 6 GHz OBSS.
10. Do comparisons of all of this.  Compare throughputs and latency for single channel, eMLSR, with OBSS, without OBSS, etc.
11. Look at the packets, per-band, as a function of time, and (hopefully) see the packets move from one band to another as a result of OBSS interference.

## Executable Code
### eMLSR.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
This code runs a LOT Of different (sub)tests, as described above.  Data is analyzed with analysis written to the log file, and individual JSON, PCAP, etc. files are saved.
### createReport.py
Uses Expert Analysis tools to analyze JSON and PCAP files and generate the final report.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

params_test specifically includes:
* The STA MLO configuration
* The OBSS AP and STA settings

## Output
This test produces the CSV, JSON etc. output.
In addition, createReport.py produces a report with many plots showing comparisons between MLO and non-MLO behavior, performance.
