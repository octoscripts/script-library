# CustomChartsExample

## Test Type
Testbed Use

## Overall Description
This is a somewhat complicated example that walks, in detail, through the creation of custom charts using the External Data Interface.
Roughly, here is how this works:
1. Enable the External Data Interface in the test
2. Upload a python script that can extract Pal data in real time, to the server.
3. Start a test
4. Run the data extraction test on the server, using basic-server
5. Stop the test
6. Stop the data extraction

## Executable Code
### CustomChartsExample.py
This is the main code.  As always, it does the initial configuration, reading in the configuration files, reading in the testbed configuration,
setting up the directory for output files, etc.

This code implements all of the steps, above, and explains them in detail.

### getDataStream.py
Uses the real-time data streams to get PAL TELEMETRY from all of the Pals, and then to format that data into custom plots which are
placed onto the Kafka External Plot Stream.

### createReport.py
Has two functions:
* analyze, which pulls the Pal Telemetry data out of the test report and stores it into the testResultsLog file.
* summarize, which creates various plots, like time plots and histograms for the Pal RSSI


## Configurability
Configurable files are always, by default, params_test.json, and params_system.json.
params_system.json is for overall system configuration (IP addresses, DUT security, etc.)
params_test.json is for changes made to the test itself.

Other than basic test configuration, the important configuration for this test includes:
* The name of the file that will do the real-time data extraction
* The location on the server where that file should be placed, and the name it should be given.

## Output
Normal CSV, JSON, etc. files produced.
createReport.py produces a simple report showing plots using the extracted Pal data.
