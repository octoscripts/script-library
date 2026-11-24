# BuferBloat

## Test Type
Advanced Test

## Overall Description
https://www.bufferbloat.net/projects/bloat/wiki/Tests_for_Bufferbloat/.
Quick: Test for Bufferbloat
If you want to observe latency under load (“bufferbloat”) for yourself, try this:
Start a ping to google.com. You’ll see a series of lines, one per ping, typically with times in the 20-100 msec range.
Start a speed test from one of the speed test services below while the pings continue:
http://fast.com
http://speedtest.net
Watch the ping times while the speed test is running. If the times jump up when uploading or downloading, then your router is probably bloated.

This test does not do that, exactly, but it runs traffic over a set of different profiles as configured by the user.
The latency results are compared to determine the likelihood of bloated buffers.
Latency is determined both by a ping pair, and a traffic pair.

## Executable Code
### BufferBloat.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.
### createReport.py
Has two operations:
* extract, which pulls out the throughput and latency information from each run.  Results go into the testResultLog file.
* plot, which looks that the stored results, makes a determination about buffer bloating, and generates plots.

## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Main configurability is the choice of devices to use and traffic settings.

## Output
This test produces the CSV, JSON etc. output.
In addition, createReport.py produces a report the plots the latency information as a function of throughput,
and makes a determination about whether or not buffers are bloated.