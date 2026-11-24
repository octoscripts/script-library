# DFS

## Test Type
Advanced Test

## Overall Description
Use the iGen to generate radar-like interference.  Using a sniffer, observe the DFS operation.
The test uses Expert Analysis to do automatic PCAP analysis and indentify the Channel Switch Announcement packets.
* A simple test is configured, with an AP and STA, and traffic running.  A Pal is also configured as a sniffer.
* The iGen is used to generate radar-like interference.
* Expert Analysis is used to pull out the DFS packets

## Executable Code
### DFS.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
This code also sets up the sniffer, and controls the iGen.
### createReport.py
Uses Expert Analysis tools to pull out DFS packets.
* parsePCAP is used to pull out the packets.
* The packets are searched for a "csa" element.
* All CSA packets are printed out

* Also does a second analysis using pcapAPI with action=getDFS
* This should always accomplish the same thing, but is the more modern DFS analysis technique

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Nothing very interesting to be configured.  Pal as STA and Pal as sniffer, traffic settings, etc.
There is a switch that allows the test to be run with a Pal as the AP (so, testing DFS capability of the Pal.)

## Output
This test produces the CSV, JSON etc. output.
In addition, createReport.py produces a report with DFS packet information.
