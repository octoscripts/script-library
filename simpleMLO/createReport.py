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

from pathlib import Path

import numpy as np

def _findHeaderWithPrefix(headers, prefix, mustContainAll):
    """Return the first header starting with an exact prefix and containing every substring in
    mustContainAll. The prefix match matters for per-endpoint lookups -- "Pal Endpoint 1 " must
    NOT match headers for endpoint 10-19 (a plain substring check on "Pal Endpoint 1" would)."""
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

def _runExpertAnalysis(ea_root, archiveFile):
    """Run one archive through the zip2csv -> objectify -> crunch pipeline. Returns
    (headers, dataSet, crunchedData, notes) -- any of which may be None/empty on failure."""
    headers, dataSet, crunchedData, notes = None, None, None, {}
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
    return (headers, dataSet, crunchedData, notes)

def _addStandardPlots(myReport, headers, dataSet, colors):
    """Builds the standard set of plots from the objectified JSON-archive data:
    1. Aggregate Throughput vs. Time.
    2. Mbps (UL/DL) vs. Time, for every radio endpoint, combined -- derived from the raw
       bits-per-second data (divided by 1E6), not a dedicated rate column.
    3-6. MCS / Streams (Nss) / Bandwidth / Rate (UL/DL) vs. Time, for every radio endpoint, combined.
    """
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
        print(">>> Could not find a time column; skipping the standard JSON-archive plots.")
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
        print(">>> Could not find a usable starting time value; skipping the standard JSON-archive plots.")
        return

    colorIdx = [0]  # shared mutable counter so every series across a plot gets a distinct color
    def _nextColor():
        c = colors[colorIdx[0] % len(colors)]
        colorIdx[0] += 1
        return c

    # --- 1. Aggregate Throughput vs. Time ---
    aggHeader = None
    for h in headers:
        if "Throughput [Mbps]" in h and "Aggregate" in h and "calc" not in h.lower():
            aggHeader = h
            break
    if aggHeader:
        points = _extractSeries(dataSet, timeHeader, aggHeader, t0)
        _addTimeSeriesPlot(myReport, "Aggregate Throughput vs. Time", "Throughput (Mbps)",
            [("Aggregate Throughput", points, "green")])
    else:
        print(">>> Could not find an aggregate throughput column; skipping that plot.")

    endpointNumbers = _findNumberedEntities(headers, "Pal Endpoint ")
    if not endpointNumbers:
        print(">>> No 'Pal Endpoint <N>' columns found; skipping Mbps/MCS/streams/bandwidth/rate plots.")
        return

    # --- 2. Mbps (UL/DL) vs. Time, every endpoint, derived from raw bits-per-second ---
    def _toMbps(points):
        return [{"x": p["x"], "y": p["y"] / 1E6} for p in points]

    colorIdx[0] = 0
    series = []
    for epNum in endpointNumbers:
        prefix = "Pal Endpoint {} ".format(epNum)
        # Note: unlike the other PHY stats (which use fully-capitalized "RX"/"TX"), Expert
        # Analysis names this field with mixed case: "Rx Bits Per Second" / "Tx Bits Per Second".
        rxH = _findHeaderWithPrefix(headers, prefix, ["Rx Bits Per Second"])
        txH = _findHeaderWithPrefix(headers, prefix, ["Tx Bits Per Second"])
        series.append(("Pal Endpoint {} DL (RX)".format(epNum), _toMbps(_extractSeries(dataSet, timeHeader, rxH, t0)), _nextColor()))
        series.append(("Pal Endpoint {} UL (TX)".format(epNum), _toMbps(_extractSeries(dataSet, timeHeader, txH, t0)), _nextColor()))
    _addTimeSeriesPlot(myReport, "Mbps (UL/DL) vs. Time", "Mbps", series)

    # --- 3-6. MCS / Streams / Bandwidth / Rate (UL/DL) vs. Time, every endpoint, combined ---
    def _combinedAcrossEndpoints(statSubstrings):
        colorIdx[0] = 0
        series = []
        for epNum in endpointNumbers:
            prefix = "Pal Endpoint {} ".format(epNum)
            rxH = _findHeaderWithPrefix(headers, prefix, ["RX"] + statSubstrings)
            txH = _findHeaderWithPrefix(headers, prefix, ["TX"] + statSubstrings)
            series.append(("Pal Endpoint {} DL (RX)".format(epNum), _extractSeries(dataSet, timeHeader, rxH, t0), _nextColor()))
            series.append(("Pal Endpoint {} UL (TX)".format(epNum), _extractSeries(dataSet, timeHeader, txH, t0), _nextColor()))
        return series

    _addTimeSeriesPlot(myReport, "MCS (UL/DL) vs. Time", "MCS Index", _combinedAcrossEndpoints(["MCS", "Mode"]))
    _addTimeSeriesPlot(myReport, "Streams (UL/DL) vs. Time", "Streams (Nss)", _combinedAcrossEndpoints(["Nss", "Mode"]))
    _addTimeSeriesPlot(myReport, "Bandwidth (UL/DL) vs. Time", "Bandwidth (MHz)", _combinedAcrossEndpoints(["Bandwidth [MHz]", "Mode"]))
    _addTimeSeriesPlot(myReport, "Rate (UL/DL) vs. Time", "Rate (Mbps)", _combinedAcrossEndpoints(["Rate [Mbps]", "Mode"]))

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
        
def main(directory_name,json_dir,jsonFile,pcapFile,ea_root):

        #Grab the directory information as created by SM.
        if directory_name[len(directory_name)-1] != "/": directory_name += "/"
        dirFile = directory_name + "directories.json"
        try:
                f = open(dirFile)
                directoriesJson = json.load(f)
                subDir = directoriesJson["subDirectory"]
                splits = subDir.split("_")
                runNumber = splits[0]
                #print('>>> splits: ', splits)
                #theName = splits[2]
                theName = directoriesJson["title"]
                theTitle = theName.replace(" ","_")
        except:
                theTitle = "simpleMLO"
                theName = theTitle.replace(" ","_")
                runNumber = "0"                

        #Write a report
        myReport = {}
        myReport["Title"] = theName
        myReport["Report"] = []

        # #################### STANDARD PLOTS FROM THE JSON ARCHIVE #######################
        # Added before the PCAP/MLO-specific analysis below: run the raw JSON archive through the
        # usual Expert Analysis pipeline (zip2csv -> objectify -> crunch) and plot straight from
        # the objectified per-second dataSet, the same approach used for the other scripts.
        if jsonFile and os.path.exists(jsonFile):
                print(">>> Running Expert Analysis on archive: {}".format(jsonFile))
                (saHeaders, saDataSet, saCrunchedData, saNotes) = _runExpertAnalysis(ea_root, jsonFile)
                if saHeaders and saDataSet:
                        item = {
                                "elementType": "section", "headingType": "h1",
                                "headingContent": "Standard Plots", "text": ""
                        }
                        myReport["Report"].append(item)
                        _addStandardPlots(myReport, saHeaders, saDataSet, colors)
                else:
                        print(">>> No usable data from {}; skipping the standard plots.".format(jsonFile))
        else:
                print(">>> No jsonFile provided (or it doesn't exist); skipping the standard plots.")

        pcapDir = json_dir

        if(pcapFile):
                split = pcapFile.split("/")
                fileName = split[len(split)-1]

                #base_endpoint = "http://localhost:8080/pcapAPI"
                base_endpoint = ea_root + "pcapAPI"        
                api_endpoint = base_endpoint + "?action=getMLO"
                api_endpoint += "&fileName=" + fileName + "," + fileName
                api_endpoint += "&pcapDir=" + pcapDir + "," + pcapDir
                api_endpoint += "&MLObands=" + "5" + "," + "6"
                api_endpoint += "&firstPacket=" + str(1) + "&lastPacket=" + str(1000)
                print("The call is to:  " + api_endpoint)
                print("Try from {} to {}".format(1,5000))
                apiResponse = requests.get(url=api_endpoint)
                returnObject = json.loads(apiResponse.text)
                #print(returnObject)
                retObj = returnObject["retObj"]
                #print("{}".format(retObj))


                for entry in retObj:
                    if entry == "html": continue
                    if entry == "allPlots": continue
                    item = {
                        "elementType":"section",
                        "headingType":"h1",
                        "headingContent": entry
                    }
                    #myReport["Report"].append(item)
                    text = json.dumps(retObj[entry],indent=4)
                    item = {
                        "elementType":"text",
                        "text": "<pre>{}</pre>".format(text)
                        #"text": "{}".format(text)
                    }
                    #myReport["Report"].append(item)

                #The API call itself generates a bunch of plots.
                JsonReport = retObj["JsonReport"]                
                JsonReport = json.loads(JsonReport)
                for item in JsonReport["Report"]:
                        myReport["Report"].append(item)

        #print(myReport)
        
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
        fileName = "Simple_MLO_Plots.html"
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
                "label": "Report for " + theTitle
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'MLO_Analysis.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

        return myReport
        
#===
#Use this for debugging.  Otherwise, comment it out.
'''
print("This is the debug section of simpleMLO, createReport.  Comment it out if you see it and don't expect to.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-13_16-31_AirTies/1_2026-10-13_16-31_simpleMLO_override/"
pcapFile = json_dir + "2026-10-13_16-34_AirTies_AirTies_simpleMLO_PCAP_0.pcap"
jsonFile = json_dir + "2026-10-13_16-34_AirTies_AirTies_simpleMLO_0.zip"
ea_root = "http://localhost:8080/"

main(directory_name,json_dir,jsonFile,pcapFile,ea_root)
'''
