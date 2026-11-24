# ConnectDisconnect

## Test Type
Testbed Use

## Overall Description
An example of how to connect, and disconnect, the endpoints of one (or more) traffic pairs, over and over during a test.
So, a test is created consisting of one, or more, Pal endpoints.
Traffic is started.
Then, using one of two different modes, the traffic pairs are connected and disconnected at random while the traffic flows (or attempts to flow.)
The two methods of disconnecting the endpoints are:
* Standby Mode: putting the Pal endpoint into standby mode, so, essentially, turning off its radio, and
* Attenuation: raising the attenuation between the DUT and the Pal so that the two disconnect.  But the Pal radio is never turned off.

## Executable Code
### ConnectDisconnect.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
This code runs the test and implements the disconnection logic.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Configurables include:
* Pal endpoints to use
* Disconnection mode to use (standby, attenuation)
* Number of connect/disconnect cycles
* Dwell time at each setting

## Output
Normal CSV, JSON, etc. files produced.
No other analysis.