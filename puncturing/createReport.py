import sys
import json
import os
import requests
import base64
import pprint
import time
import math
import re
pp = pprint.PrettyPrinter(indent=4)
import copy

from pathlib import Path

import numpy as np

colors = [
        "#000000", "#FFFF00", "#1CE6FF", "#FF34FF", "#FF4A46", "#008941", "#006FA6", "#A30059",
        "#FFDBE5", "#7A4900", "#0000A6", "#63FFAC", "#B79762", "#004D43", "#8FB0FF", "#997D87",
        "#5A0007", "#809693", "#FEFFE6", "#1B4400", "#4FC601", "#3B5DFF", "#4A3B53", "#FF2F80",
        "#61615A", "#BA0900", "#6B7900", "#00C2A0", "#FFAA92", "#FF90C9", "#B903AA", "#D16100",
        "#DDEFFF", "#000035", "#7B4F4B", "#A1C299", "#300018", "#0AA6D8", "#013349", "#00846F",
        "#372101", "#FFB500", "#C2FFED", "#A079BF", "#CC0744", "#C0B9B2", "#C2FF99", "#001E09",
        "#00489C", "#6F0062", "#0CBD66", "#EEC3FF", "#456D75", "#B77B68", "#7A87A1", "#788D66",
        "#885578", "#FAD09F", "#FF8A9A", "#D157A0", "#BEC459", "#456648", "#0086ED", "#886F4C",
        "#34362D", "#B4A8BD", "#00A6AA", "#452C2C", "#636375", "#A3C8C9", "#FF913F", "#938A81",
        "#575329", "#00FECF", "#B05B6F", "#8CD0FF", "#3B9700", "#04F757", "#C8A1A1", "#1E6E00",
        "#7900D7", "#A77500", "#6367A9", "#A05837", "#6B002C", "#772600", "#D790FF", "#9B9700",
        "#549E79", "#FFF69F", "#201625", "#72418F", "#BC23FF", "#99ADC0", "#3A2465", "#922329",
        "#5B4534", "#FDE8DC", "#404E55", "#0089A3", "#CB7E98", "#A4E804", "#324E72", "#6A3A4C"
]

# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

# ---------------------------------------------------------------------------------------------
# Shared helpers for the "basic plots" section appended after the puncturing-specific analysis.
# Same pipeline/approach used for the other scripts' createReport.py: run each result archive
# through Expert Analysis (zip2csv -> objectify -> crunch) and plot straight from the objectified
# per-second dataSet.
# ---------------------------------------------------------------------------------------------

def _findHeader(headers, mustContainAll):
    """Return the first header string containing every substring in mustContainAll, or None."""
    for h in headers:
        if all(sub in h for sub in mustContainAll):
            return h
    return None

def _findHeaderWithPrefix(headers, prefix, mustContainAll):
    """Like _findHeader, but also requires the header to start with an exact prefix.
    Used for per-endpoint lookups, since e.g. "Pal Endpoint 1 " must NOT match headers
    for endpoint 10-16 (a plain substring check on "Pal Endpoint 1" would)."""
    for h in headers:
        if h.startswith(prefix) and all(sub in h for sub in mustContainAll):
            return h
    return None

def _findNumberedEntities(headers, entityPrefix):
    """Scan headers for '<entityPrefix><N> ' (e.g. 'Pal Endpoint 3 ...') and return the sorted,
    de-duplicated list of N's found, so the report adapts to however many radio endpoints a given
    test actually configured, rather than a fixed count."""
    pattern = re.compile(r'^' + re.escape(entityPrefix) + r'(\d+) ')
    found = set()
    for h in headers:
        m = pattern.match(h)
        if m:
            found.add(int(m.group(1)))
    return sorted(found)

def _extractSeries(dataSet, timeHeader, valueHeader, t0):
    """Pull {x,y} points for one column, skipping non-numeric and non-finite (nan/inf) values."""
    points = []
    if not valueHeader:
        return points
    for row in dataSet:
        tVal = row.get(timeHeader)
        yVal = row.get(valueHeader)
        try:
            tVal = float(tVal)
            yVal = float(yVal)
        except (TypeError, ValueError):
            continue  # skips "#N/A" and similar non-numeric entries
        if not math.isfinite(tVal) or not math.isfinite(yVal):
            continue  # skips "nan"/"inf"/"-inf" strings -- float() parses these without error
        points.append({"x": round(tVal - t0, 3), "y": yVal})
    return points

def _addTimeSeriesPlot(myReport, sectionTitle, yAxisLabel, series):
    """series: list of (label, points, color) tuples. Skips empty series; skips the whole
    plot (with a log message) if none of the series have any data."""
    plotData = []
    for label, points, color in series:
        if len(points) == 0:
            print(">>> No data for series '{}' in plot '{}'; leaving it out.".format(label, sectionTitle))
            continue
        plotData.append({
            "label": label,
            "color": color,
            "width": 1,
            "radius": 0,
            "data": points,
            "fill": -1,
            "style": "solid"
        })
    if len(plotData) == 0:
        print(">>> No data available at all for plot: {}; skipping it entirely.".format(sectionTitle))
        return

    myReport["Report"].append({
        "elementType": "section", "headingType": "h2", "headingContent": sectionTitle, "text": ""
    })
    myReport["Report"].append({
        "elementType": "plot",
        "type": "scatter",
        "title": "",
        "xaxis": {"string": "Elapsed Time (s)"},
        "yaxis": {"string": yAxisLabel},
        "showTable": False,
        "plotWidth": "800px",
        "data": plotData
    })

def _endpointNamesFromTopLines(topLines):
    """Parse the "# epMapping: Endpoint X is LABEL, X, LABEL" comment lines that Expert Analysis
    writes into the CSV (returned to us via objectify's "topLines" field) directly in Python.
    This is done here rather than relying on crunchedData[a]["epMap"] (which crunch computes
    internally the same way) because that field is attached to a JS array object, and
    JSON.stringify() silently drops named properties attached to arrays -- it never survives the
    trip back to us over the /crunch REST response, regardless of what we send it.
    Returns {endpointNumber (1-indexed): name} for whichever endpoints have a resolved name."""
    names = {}
    flatLines = []
    for item in (topLines or []):
        if isinstance(item, list):
            flatLines.extend(item)
        else:
            flatLines.append(item)
    for line in flatLines:
        if not isinstance(line, str) or "epMap" not in line:
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            idx = int(parts[1].strip())  # 0-indexed, matching "Pal Endpoint idx+1"
        except ValueError:
            continue
        label = parts[2].strip() if len(parts) > 2 and parts[2].strip() not in ("", "undefined") else parts[1].strip()
        names[idx + 1] = label
    return names

def _runExpertAnalysis(ea_root, archiveFile):
    """Run one archive through the zip2csv -> objectify -> crunch pipeline. Returns
    (headers, dataSet, crunchedData, notes, topLines) -- any of which may be None/empty on failure."""
    headers, dataSet, crunchedData, notes, topLines = None, None, None, {}, []
    try:
        with open(archiveFile, "rb") as f:
            encoded = base64.b64encode(f.read())

        api_endpoint = ea_root + "zip2csv"
        theResponse = requests.post(url=api_endpoint, data={'zip': encoded})
        theJson = json.loads(theResponse.text)
        if "error" in theJson:
            print(">>> zip2csv returned an error: {}".format(theJson["error"]))
        csv = theJson["csv"]

        api_endpoint = ea_root + "objectify"
        theResponse = requests.post(url=api_endpoint, data={'csv': csv})
        theJson = json.loads(theResponse.text)
        if "error" in theJson:
            print(">>> objectify returned an error: {}".format(theJson["error"]))
        headers = theJson["headers"]
        dataSet = theJson["dataSet"]
        topLines = theJson.get("topLines", [])

        api_endpoint = ea_root + "crunch"
        theResponse = requests.post(url=api_endpoint, data={'headers': headers, 'dataSet': json.dumps(dataSet), 'topLines': json.dumps(topLines), 'run': 1})
        theJson = json.loads(theResponse.text)
        if "error" in theJson:
            print(">>> crunch returned an error: {}".format(theJson["error"]))
        crunchedData = theJson["crunchedData"]
        notes = theJson.get("Notes", {})
    except Exception as err:
        print(">>> Expert Analysis pipeline failed on {}: {}".format(archiveFile, err))
    return (headers, dataSet, crunchedData, notes, topLines)

def _addBasicPlots(myReport, headers, dataSet, topLines, colors):
    """Builds the standard 5 full-size plots (no grid formatting) for one result archive:
    1. Throughput vs. Time -- every header with "throughput" and "[mbps]" in its name, combined.
    2. MCS (Mode) vs. Time -- RX and TX, for every (non-sniffer) radio endpoint, combined.
    3. Data Rate vs. Time -- RX and TX, for every (non-sniffer) radio endpoint, combined.
    4. Streams (Nss) vs. Time -- RX and TX, for every (non-sniffer) radio endpoint, combined.
    5. Bandwidth vs. Time -- RX and TX, for every (non-sniffer) radio endpoint, combined.
    Radio endpoints are labeled with their real name (from Expert Analysis' epMap, via topLines)
    when available, falling back to "Pal Endpoint N" otherwise. Endpoints whose resolved name
    contains "sn_" (sniffer endpoints) are left out of the MCS/rate/streams/bandwidth plots --
    those values aren't meaningful for a sniffer, only for a real traffic endpoint.
    """
    epNames = _endpointNamesFromTopLines(topLines)

    timeHeader = None
    for h in headers:
        if h == "Server timestamp" or (h.startswith("Server timestamp") and "MS" not in h):
            timeHeader = h
            break
    if not timeHeader:
        for h in headers:
            if "Time" in h:
                timeHeader = h
                break
    if not timeHeader:
        print(">>> Could not find a time column; skipping all basic plots for this archive.")
        return

    t0 = None
    for row in dataSet:
        try:
            t0 = float(row.get(timeHeader))
            if math.isfinite(t0):
                break
        except (TypeError, ValueError):
            continue
    if t0 is None:
        print(">>> Could not find a usable starting time value; skipping all basic plots for this archive.")
        return

    colorIdx = [0]  # shared mutable counter so every series across a plot gets a distinct color
    def _nextColor():
        c = colors[colorIdx[0] % len(colors)]
        colorIdx[0] += 1
        return c

    # --- Plot 1: Throughput vs. Time -- every header with "throughput" and "[mbps]" in its name ---
    colorIdx[0] = 0
    series = []
    for h in headers:
        if "throughput" in h.lower() and "[mbps]" in h.lower():
            series.append((h, _extractSeries(dataSet, timeHeader, h, t0), _nextColor()))
    _addTimeSeriesPlot(myReport, "Throughput vs. Time", "Throughput (Mbps)", series)

    endpointNumbers = _findNumberedEntities(headers, "Pal Endpoint ")
    if not endpointNumbers:
        print(">>> No 'Pal Endpoint <N>' columns found; skipping MCS/rate/streams/bandwidth plots.")
        return

    # Leave out sniffer endpoints (resolved name contains "sn_") -- MCS/rate/streams/bandwidth
    # aren't meaningful stats for a sniffer, only for a real traffic endpoint.
    statEndpointNumbers = [epNum for epNum in endpointNumbers if "sn_" not in epNames.get(epNum, "")]
    skipped = [epNum for epNum in endpointNumbers if epNum not in statEndpointNumbers]
    if skipped:
        print(">>> Leaving sniffer endpoint(s) out of MCS/rate/streams/bandwidth plots: {}".format(
            [epNames.get(n) for n in skipped]))

    # --- MCS / Data Rate / Streams / Bandwidth vs. Time -- RX and TX, every non-sniffer endpoint ---
    def _combinedAcrossEndpoints(statSubstrings):
        colorIdx[0] = 0
        series = []
        for epNum in statEndpointNumbers:
            prefix = "Pal Endpoint {} ".format(epNum)
            epLabel = epNames.get(epNum, "Pal Endpoint {}".format(epNum))
            rxH = _findHeaderWithPrefix(headers, prefix, ["RX"] + statSubstrings)
            txH = _findHeaderWithPrefix(headers, prefix, ["TX"] + statSubstrings)
            series.append(("{} RX".format(epLabel), _extractSeries(dataSet, timeHeader, rxH, t0), _nextColor()))
            series.append(("{} TX".format(epLabel), _extractSeries(dataSet, timeHeader, txH, t0), _nextColor()))
        return series

    _addTimeSeriesPlot(myReport, "MCS (Mode) vs. Time", "MCS Index", _combinedAcrossEndpoints(["MCS", "Mode"]))
    _addTimeSeriesPlot(myReport, "Data Rate vs. Time", "Data Rate (Mbps)", _combinedAcrossEndpoints(["Rate [Mbps]", "Mode"]))
    _addTimeSeriesPlot(myReport, "Streams (Nss) vs. Time", "Streams (Nss)", _combinedAcrossEndpoints(["Nss", "Mode"]))
    _addTimeSeriesPlot(myReport, "Bandwidth vs. Time", "Bandwidth (MHz)", _combinedAcrossEndpoints(["Bandwidth [MHz]", "Mode"]))

def dataAnalysis(directory_name,json_dir,pcapFile,jsonFile):
    if json_dir[len(json_dir)-1] != "/": json_dir += "/"
    fileName = pcapFile.replace(json_dir,"")
    pcapDir = json_dir

    base_endpoint = "http://localhost:8080/pcapAPI"

    #Get the total number of packets.
    api_endpoint = base_endpoint + "?action=getTotalPacketCount"
    api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
    print("The call is to:  " + api_endpoint)
    apiResponse = requests.get(url=api_endpoint)
    returnObject = json.loads(apiResponse.text)
    totalPackets = returnObject["result"]
    print("The total number of packets in this file is {}".format(totalPackets))

    #Find some beacons.
    beacons = {}
    nBeacons = 0
    stepsOf = 100
    firstPacket = 1
    lastPacket = firstPacket + stepsOf
    while len(beacons) == 0 and firstPacket<totalPackets:
        api_endpoint = "http://localhost:8080/parsePCAP?filters=Beacon&fileName={}&pcapDir={}&firstPacket={}&lastPacket={}".format(fileName,pcapDir,firstPacket,lastPacket)
        print("The call is to:  " + api_endpoint)
        apiResponse = requests.get(url=api_endpoint)
        returnObject = json.loads(apiResponse.text)
        if "fields" in returnObject:
            for item in returnObject["fields"]:
                ta = item["transmitterAddress"]
                if ta in beacons: beacons[ta].append(item)
                else: beacons[ta] = [item]
                nBeacons += 1
        firstPacket = lastPacket + 1
        lastPacket = firstPacket + stepsOf
    print("Found {} beacons.".format(nBeacons))
    print("Beacon TAs are :")
    for ta in beacons: print(ta)

    #Also let's find the main stream
    api_endpoint = "http://localhost:8080/pcapAPI?action=getMainStream&fileName={}&pcapDir={}&firstPacket=1&lastPacket=5000".format(fileName,pcapDir)
    print("The call is to:  " + api_endpoint)
    apiResponse = requests.get(url=api_endpoint)
    returnObject = json.loads(apiResponse.text)
    #Which has the most counts.  Because if you use a STApal sniffer, you CANNOT SEE THE DATA PACKETS from the traffic, so you can be misled here.
    highestCount = returnObject["result"]["result"]["streams"][0]
    for stream in returnObject["result"]["result"]["streams"]:
        if stream["count"] > highestCount["count"]: highestCount = stream
    
    #result = returnObject["result"]["result"]

    #DEBUG FORCE THIS TO BE THE PAL
    for stream in returnObject["result"]["result"]["streams"]:
        print(stream)
        if "2e.27" in stream["ta"] or "2e.27" in stream["ra"]: highestCount = stream

    highestCount["to"] = highestCount["ra"]
    highestCount["from"] = highestCount["ta"]
    result = highestCount
    print(result)
    allowed = [result["to"],result["from"]]

    _beacons = {}
    for ta in beacons:
        if ta in allowed: _beacons[ta] = copy.deepcopy(beacons[ta])

    beacons = copy.deepcopy(_beacons)

    print("Beacon TAs are :")
    for ta in beacons: print(ta)
    
    #Look at the puncturing information
    for ta in beacons:
        theseBeacons = beacons[ta]
        for beacon in theseBeacons:
            if "EHTopObj" in beacon:
                BW = beacon["EHTopObj"]["bandwidth"]
                DSB = beacon["EHTopObj"]["DSB"]
                #print("For beacon {}, the BW is {} and the DSB is {}".format(beacon["packetNumber"],BW,DSB))

    results = {}
    clean = []
    for ta in beacons:
        print("Doing ta {}".format(ta))
        good = False
        for theBeacon in beacons[ta]:
            if "EHTopObj" not in theBeacon: continue
            good = True
            #print("Beacon found with EHTopObj for ta {}".format(ta))
            BW = int(theBeacon["EHTopObj"]["bandwidth"])
            subChans = int(BW/20)
            DSB = beacons[ta][0]["EHTopObj"]["DSB"]
            subChanActive = []
            for i in range(subChans,0,-1):
                x = i-1
                try:
                    if DSB[x]=="1": subChanActive.append(False)
                    else: subChanActive.append(True)
                except: subChanActive.append(True)
            results[ta] = {"BW":BW, "subChans":subChans,"DSB":DSB,"subChanActive":subChanActive}
        if not good:
            print("Did not find a beacon with EHTopObj element for ta = {}".format(ta))
            clean.append(ta)
            #sys.exit()
    print(results)

    #for item in clean: del beacons[item]

    #Also do some statistics analysis
    ea_root = "http://localhost:8080/"

    with open(jsonFile, "rb") as f:
        bytes = f.read()
        encoded = base64.b64encode(bytes)
        api_endpoint = ea_root + "zip2csv"
        print('\n>>> api_endpoint: ', api_endpoint)
        data = {'zip':encoded}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)

    csv = theJson["csv"]

    print('\n### Running getStats')
    #Get basic test results information
    api_endpoint = ea_root + "getStats"
    data = {'csv':csv,'filter':'counts'}
    try:
        r = requests.post(url=api_endpoint, data=data, timeout=5)
    except requests.exceptions.RequestException as error:
        info("Error: ", error)
        sys.exit(44)		    
    y = json.loads(r.text)
    print('\n>>> y: ', y)
    palEndpoints = y["filteredData"]["palEndpoints"]["map"]
    print(palEndpoints)

    # Analyze the CSV file
    print('\n### Analyzing CSV file')
    api_endpoint = ea_root + "objectify"
    data = {'csv':csv}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    headers = theJson["headers"]
    dataSet = theJson["dataSet"]
    if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

    print('\n### Running crunch')
    api_endpoint = ea_root + "crunch"
    run = 1
    data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    if "error" in theJson: info("crunch: This data returned an error: {}".format(theJson["error"]))
    analyzedData = theJson["crunchedData"]
    theNotes = theJson["Notes"]
    print("The number of pal Endpoints for which you have data is {}".format(len(analyzedData)))

    stats = {}
    for ep in range(0,len(analyzedData)):
        name = palEndpoints[str(ep)]
        print(name)
        if "sn" in name: continue
        stats[name] = {}
        _analyzedData = analyzedData[ep]
        atten = 0
        AD = _analyzedData[atten]
        #for key in AD: print(key)
        if "rxRateModeMode" in AD["allRates"]: stats[name]["rxRate"] = AD["allRates"]["rxRateModeMode"]
        else: stats[name]["rxRate"] = None
        if "txRateModeMode" in AD["allRates"]: stats[name]["txRate"] = AD["allRates"]["txRateModeMode"]
        else: stats[name]["txRate"] = None

        if "rxBwModeMode" in AD["allBW"]: stats[name]["rxBW"] = AD["allBW"]["rxBwModeMode"]
        else: stats[name]["rxBW"] = None
        if "txBwModeMode" in AD["allBW"]: stats[name]["txBW"] = AD["allBW"]["txBwModeMode"]
        else: stats[name]["txBW"] = None

        if "rxNssModeMode" in AD["allNss"]: stats[name]["rxNss"] = AD["allNss"]["rxNssModeMode"]
        else: stats[name]["rxNss"] = None
        if "txNssModeMode" in AD["allNss"]: stats[name]["txNss"] = AD["allNss"]["txNssModeMode"]
        else: stats[name]["txNss"] = None
        
        if "rxMcsModeMode" in AD["allMcs"]: stats[name]["rxMcs"] = AD["allMcs"]["rxMcsModeMode"]
        else: stats[name]["rxMcs"] = None
        if "txMcsModeMode" in AD["allMcs"]: stats[name]["txMcs"] = AD["allMcs"]["txMcsModeMode"]
        else: stats[name]["txMcs"] = None
        
    #print(stats)

    return results,stats

def main(directory_name,json_dir):

        #Grab the directory information as created by SM.
        if directory_name[len(directory_name)-1] != "/": directory_name += "/"
        dirFile = directory_name + "directories.json"
        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        try:
                f = open(dirFile)
                directoriesJson = json.load(f)
                subDir = directoriesJson["subDirectory"]
                splits = subDir.split("_")
                runNumber = splits[0]
                theName = directoriesJson["title"]
                theTitle = theName.replace(" ","_")
        except:
                theTitle = "Puncturing"
                theName = theTitle.replace(" ","_")
                runNumber = "0"                

        #For this test, pull the JSON information created.
        for x in os.listdir(json_dir):
            if "testresultlog" in x:
                    jsonFile = json_dir + x
        f = open(jsonFile)
        testResultLogJson = json.load(f)
        f.close

        myReport = {}
        myReport["Title"] = "Puncturing Analysis"
        myReport["Report"] = []

        allowedPunctures = testResultLogJson["allowedPunctures"]
        item = {
            "elementType": "section",
            "headingType": "h1",
            "headingContent":"Allowed Punctures",
            "text": str(allowedPunctures)
        }
        myReport["Report"].append(item)
        punctureSelected = testResultLogJson["punctureSelected"]
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"Puncture Selected: {}".format(str(punctureSelected))
        }
        myReport["Report"].append(item)

        tests = []
        for key in testResultLogJson:
            if "Test_" in key: tests.append(testResultLogJson[key])

        item = {
            "elementType": "section",
            "headingType": "h1",
            "headingContent":"Number of Tests: {}".format(str(len(tests)))
        }
        myReport["Report"].append(item)

        idx = 0
        for test in tests:
            idx += 1
            item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Test {}".format(idx)
            }
            myReport["Report"].append(item)

            APs = list(test["pcap"].keys())
            item = {
                "elementType": "section",
                "headingType": "h3",
                "headingContent":"Number of APs found: {}".format(str(len(APs)))
            }
            myReport["Report"].append(item)

            item = {
                "elementType": "section",
                "headingType": "h4",
                "headingContent":"PCAP Analysis"
            }
            myReport["Report"].append(item)
            for AP in APs:
                pcap = test["pcap"][AP]

                countActive = 0
                for entry in pcap["subChanActive"]:
                    if entry: countActive += 1
                percentOfMaxPHY = countActive/pcap["subChans"] * 100

                item = {
                    "elementType": "text",
                    "text": "<b>For AP {}</b>".format(AP)
                }
                myReport["Report"].append(item)
                html = "<ul>"
                html += "<li> The bandwidth is {} MHz, which means {} 20 MHz channels.</li>".format(pcap["BW"],pcap["subChans"])
                html += "<li> The Disabled Channel Bitmap detected in the beacon is {}</li>".format(pcap["DSB"])
                html += "<li> Which means that the subchannels are active from low to high as follows: {}</li>".format(pcap["subChanActive"])
                html += "<li> This means that you can expect to achieve {}% of the maximum PHY.</li>".format(percentOfMaxPHY)
                html += "</ul>"
                item = {
                    "elementType": "text",
                    "text": html
                }
                myReport["Report"].append(item)

            PEs = list(test["stats"].keys())
            item = {
                "elementType": "section",
                "headingType": "h4",
                "headingContent":"Pal Stats Analysis"
            }
            myReport["Report"].append(item)

            Evidence = []

            for PE in PEs:
                stats = test["stats"][PE]
                item = {
                    "elementType": "text",
                    "text": "<b>For Pal Endpoint {}</b>".format(PE)
                }
                myReport["Report"].append(item)
                
                html = "<ul>"
                if stats["rxBW"] and stats["rxMcs"] and stats["rxNss"]:
                    html += "<li> Rx bandwidth is {} MHz</li>".format(stats["rxBW"])
                    html += "<li> Rx MCS is {} </li>".format(stats["rxMcs"])
                    html += "<li> Rx NSS is {} </li>".format(stats["rxNss"])
                    html += "<li> Rx rate is {} Mbps</li>".format(stats["rxRate"])

                    api_endpoint = "http://localhost:8080/getDRate"
                    standard = "11be"
                    MCS = stats["rxMcs"]
                    BW = stats["rxBW"]
                    streams = stats["rxNss"]
                    GI = "800"
                    api_endpoint += "?" + "standard=" + standard
                    api_endpoint += "&" + "MCS=" + str(MCS)
                    api_endpoint += "&" + "BW=" + str(BW)
                    api_endpoint += "&" + "streams=" + str(streams)
                    api_endpoint += "&" + "GI=" + str(GI)
                    print("The api endpoint is " + api_endpoint)
                    r = requests.get(url=api_endpoint)
                    y = eval(r.text)
                    status = y["status"]
                    rate    = y["rate"]
                    html += "<li> The expected Rx rate is {} Mbps</li>".format(rate)
                    percentage = stats["rxRate"]/rate *100
                    html += "<li> This is {:.2f}% of the expected Rx rate</li>".format(percentage)

                    compare = abs(percentOfMaxPHY-percentage)/percentOfMaxPHY * 100
                    if compare < 3:
                        Evidence.append({"pe":PE,"dir":"Rx","expectedRate":rate,"actualRate":stats["rxRate"],"percentage":percentage})
                
                if stats["txBW"] and stats["txMcs"] and stats["txNss"]:
                    html += "<li> Tx bandwidth is {} MHz</li>".format(stats["txBW"])
                    html += "<li> Tx MCS is {} </li>".format(stats["txMcs"])
                    html += "<li> Tx NSS is {} </li>".format(stats["txNss"])
                    html += "<li> Tx rate is {} Mbps</li>".format(stats["txRate"])
                    api_endpoint = "http://localhost:8080/getDRate"
                    standard = "11be"
                    MCS = stats["txMcs"]
                    BW = stats["txBW"]
                    streams = stats["txNss"]
                    GI = "800"
                    api_endpoint += "?" + "standard=" + standard
                    api_endpoint += "&" + "MCS=" + str(MCS)
                    api_endpoint += "&" + "BW=" + str(BW)
                    api_endpoint += "&" + "streams=" + str(streams)
                    api_endpoint += "&" + "GI=" + str(GI)
                    print("The api endpoint is " + api_endpoint)
                    r = requests.get(url=api_endpoint)
                    y = eval(r.text)
                    status = y["status"]
                    rate    = y["rate"]
                    html += "<li> The expected Tx rate is {} Mbps</li>".format(rate)
                    percentage = stats["txRate"]/rate *100
                    html += "<li> This is {:.2f}% of the expected Tx rate</li>".format(percentage)

                    compare = abs(percentOfMaxPHY-percentage)/percentOfMaxPHY * 100
                    if compare < 3:
                        Evidence.append({"pe":PE,"dir":"Tx","expectedRate":rate,"actualRate":stats["txRate"],"percentage":percentage})
                                    
                html += "</ul>"
                item = {
                    "elementType": "text",
                    "text": html
                }
                myReport["Report"].append(item)

            item = {
                "elementType": "section",
                "headingType": "h3",
                "headingContent":"Evidence of puncturing"
            }
            myReport["Report"].append(item)

            if len(Evidence)==0:
                item = {
                    "elementType": "text",
                    "text": "No evidence of puncturing found"
                }
                myReport["Report"].append(item)

            else:
                html = "<ul>"
                for item in Evidence:
                    line = "For the {} stats of Pal Endpoint {}, the actual rate of {} Mbps compared to the expected rate of {} Mbps is {:.2f}%, close to the expected puncturing value of {:.2f}%".format(item["dir"],item["pe"],item["actualRate"],item["expectedRate"],item["percentage"],percentOfMaxPHY)
                    html += "<li>{}</li>".format(line)                    
                html += "</ul>"
                item = {
                    "elementType": "text",
                    "text": html
                }
                myReport["Report"].append(item)                                                                    


        #----------------------------------------
        # BASIC PLOTS (appended after all of the puncturing-specific analysis above).
        # Discover every real result archive in this run (one per test iteration, since this
        # test's totalTests loop in puncturing.py saves "..._0.zip", "..._1.zip", etc.),
        # excluding the CSV-only zip, the time-aligned ("-TAJ") zip, and anything with "taJSON"
        # in the name -- none of those is the full archive Expert Analysis' zip2csv expects.
        ea_root = "http://localhost:8080/"
        theZips = []
        for x in os.listdir(json_dir):
            if ".zip" in x and "CSV" not in x and "-TAJ" not in x and "taJSON" not in x:
                theZips.append(json_dir + x)
        theZips.sort()

        if len(theZips) == 0:
            print(">>> No result archive zip found in {}; skipping the basic plots.".format(json_dir))
        else:
            multiIteration = len(theZips) > 1
            for iterNum, archiveFile in enumerate(theZips):
                print(">>> Running Expert Analysis on archive: {}".format(archiveFile))
                (bpHeaders, bpDataSet, bpCrunchedData, bpNotes, bpTopLines) = _runExpertAnalysis(ea_root, archiveFile)
                if not bpHeaders or not bpDataSet:
                    print(">>> No usable data from {}; skipping its basic plots.".format(archiveFile))
                    continue
                if multiIteration:
                    myReport["Report"].append({
                        "elementType": "section", "headingType": "h1",
                        "headingContent": "Test Iteration {} - Basic Plots".format(iterNum), "text": ""
                    })
                else:
                    myReport["Report"].append({
                        "elementType": "section", "headingType": "h1",
                        "headingContent": "Basic Plots", "text": ""
                    })
                _addBasicPlots(myReport, bpHeaders, bpDataSet, bpTopLines, colors)

        #----------------------------------------
        #Generate the proper html for this report
        api_endpoint = "http://localhost:5678/jsonToHtmlReport"
        data = {'json':json.dumps(myReport,indent=4)}
        r = requests.post(url=api_endpoint,data=data)
        y = json.loads(r.text)
        html = y["html"]

        print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))

        #Verify where scriptManager is running
        api_endpoint = "http://localhost:5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        storageLocation = scriptManagerLocation + "/" + "storage/"
        fileName = "Puncturing.html"
        fullPath = storageLocation + fileName

        #Write out this html file
        f = open(fullPath, "w")
        f.write(html)
        f.close()

        print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

        #Create a JSON file that will put a link to the previous file into script manager.
        jsonPlot = {}
        jsonPlot["reportLink"] = {
                "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
                "label": "Puncturing"
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'Puncturing.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

        return myReport

#===
#Use this for debugging.  Otherwise, comment it out.

'''

print("This is the debug section of Puncturing.  Comment it out if you see it and don't expect to.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-02_09-35_calix/1_2026-10-02_09-35_puncturing_Pal2Pal/"
pcapFile = json_dir + "2026-10-02_09-39_calix_calix_puncturingPCAP_0.pcap"
jsonFile = json_dir + "2026-10-02_09-39_calix_calix_puncturing_0.zip"

#analysis = dataAnalysis(directory_name,json_dir,pcapFile,jsonFile)
#print(analysis)

main(directory_name,json_dir)

'''

