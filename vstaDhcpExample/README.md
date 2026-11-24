# vstaDhcpExample

## Test Type
Testbed Use

## Overall Description
Use of DHCP in the testbed when vSTA functionality is also being used on the Pal.
1. Set up traffic pairs (note that this is what gets changed later)
2. Set up the Pal as virtual STA endpoints
3. Allow the Pal to associate and get IP addresses from the DHCP server for each of the virtual STAs
4. Modify the already created traffic pairs to use the IP addresses assiged to the Pal vSTAs

## Executable Code
### DHCP_Example.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
### createReport.py
This is the analysis code.  It shows the assigned IP addresses, and it also shows time and attenuation plots for the data.  

All of the steps described above are implemented in the main code.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

## Output
Normal CSV, JSON, etc. files produced.  An HTML report is produced by createReport.py.

