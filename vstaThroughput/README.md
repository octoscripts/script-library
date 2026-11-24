# vstaThroughput

## Test Type
Testbed Use

## Overall Description
Answers a specific capacity question: *given a fixed number of simulatneous users N,
what is the largest per-user data rate B the system can support while keeping packet loss below a target threshold T?*
Think of this script as a "cousin" of vstaBinarySearch, which fixes the data rate and discovers the number of users, N.
Each "user" is a vSTA (virtual STA) -- a Pal is configured to create a pool of vSTAs up
front, and the test searches, by binary search, for the largest data rate B offered to each member of that pool that can run
traffic at rate B each without exceeding the loss target. Since loss percentage requires UDP, this
test only makes sense for `trafficMode = "udp"`, but the test itself allows configuration for TCP as well, but in that case
the test just measures throughput using make rate, and no searching is done.  In addition, the test allows configuration
of non-Pal devices, but for those devices, since no vSTAs can be created, the test just runs with a single endpoint.

## Executable Code
### vstaThroughput.py
This is the main code, and does everything described above: creating the vSTA pool across the
configured Pals/radios, etc. As always, it also does the initial configuration: reading in the
configuration files, reading in the testbed configuration, setting up the directory for output files,
etc.

### createReport.py
Creates the final report.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

## Output
This test produces the standard CSV/JSON/zip output per trial, plus the HTML report described above --
the packet-loss-vs-pair-count convergence plot, throughput and divergence-from-expectation plots, the
found-vs-expected-pairs diagnostic, the headline "highest supported N" result, and the detailed
loss-distribution plots for the final good/bad boundary cases. If the test exited early because even
the full vSTA pool was already below the loss target, the report reflects that outcome rather than a
completed search.
