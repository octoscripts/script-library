# vstaExample

## Test Type
Testbed Use

## Overall Description
Basic example of setting up virtual stations (vSTA) clients on a Pal
1. Use of the setupVsta library routine to set up traffic pairs with vSTA assignments on a Pal
2. Set up the Pal itself as required for the radio.  (vSTAs are not important here.)
3. Allow the Pal to associate, and get all of the vSTAs associations
4. Run the traffic to each vSTA

## Executable Code
### vstaExample.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
### createReport.py
This is the analysis code.  It creates time and attenuation plots for the data.  

All of the steps described above are implemented in the main code.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

## Output
Normal CSV, JSON, etc. files produced.  An HTML report is produced by createReport.py.

