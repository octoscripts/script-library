# Bandsteer

## Test Type
Advanced Test

## Overall Description
Connects a STA to a multiband antenna, and using attenuation changes looks to
create the conditions to roam the STA from one band to another band on the same AP.
Has the ability to enable sniffing during the test.  Up to 3 sniffers on different channels.
Test begins with the STA connected to the DUT at relatively high attenuation, so the
connection should be made using the lowest loss channel available (lowest frequency.)
As the attenuation is lowered, access to a higher loss, but possibly higher bandwidth, higher
frequency channel should become available.  In which case, bandsteering should occur.

## Executable Code
### Bandsteer.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
### createReport.py
Uses Expert Analysis tools to create Throughput vs. Attenuation plots, and other plots
as a function of attenuation (data rate, latency, ping latency.)  Also these same plots
as a function of control RSSI rather than attenuation.
In addition, if packet sniffing is enabled, Expert Analysis PCAP analysis is used
to do a roaming analysis as the traffic moves from one radio to another.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

The STA to be used is configurable from a menu that may need to be tuned to the testbed.
The traffic is configurable.
Roaming parameters are configurable.
Sniffing can be enabled/disabled, and the sniffers can be configured.

## Output
This test produces the CSV, JSON etc. output.
In addition, createReport.py produces a report with plots of various statistics
as a function fo attenuation and RSSI, and also, if available, a roaming analysis
of the PCAP file.