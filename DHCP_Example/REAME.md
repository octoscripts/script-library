# DHCP_Example

## Test Type
Testbed Use

## Overall Description
Basic use of DHCP in the testbed.
1. Set up a traffic pair (note that this is what gets changed later)
2. Set up the Pal as endpoint
3. Allow the Pal to associate and get an IP address from the DHCP server
4. Modify the already created traffic pair to use the IP address assiged to the Pal

## Executable Code
### DHCP_Example.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.

All of the steps described above are implemented in the main code.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

## Output
Normal CSV, JSON, etc. files produced.

