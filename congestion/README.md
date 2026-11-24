# congestion

## Test Type
Testbed Use

## Overall Description
An example of using two Pals, one as AP and one as STA, to generate a targeted level of airtime congestion in the testbed.
The desired congestion level is set.
Traffic is run between the Pal (AP) and the Pal (STA).  Congestion is determined using the "loading" statistics from the Pal.
The data rate between the AP and STA is steadily modified until the target level of congestion is reached.

## Executable Code
### congestion.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
The search functionality (modifications of the data rate between devices to reach the desired congestion target) is done in this code.

### createReport.py
Has two operations:
* extract, which pulls the congestion values out of the Pal data and stores it as a function of the throughput, and
* plot, which generates a final report showing the congestion measured as a function of the offered data rate

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Very basic configuration is available in this test.  The protocol type, traffic settings, etc.
The target congestion level is configurable, as is the accuracy required to declare that the congestion level has been achieved.

## Output
Normal CSV, JSON, etc. files produced.
A final report from createReport.py that shows congestion as a function of offered load.