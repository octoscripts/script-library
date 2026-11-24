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

# MUST HAVE. Contains functions used in this script and other helpful functions
import sd2Utils
import globalsfile

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
        """Scan headers for '<entityPrefix><N> ' (e.g. 'Pal Endpoint 3 ...' or 'Traffic Pair 12 ...')
        and return the sorted, de-duplicated list of N's found. Lets the report adapt to however many
        traffic pairs/radio endpoints a given test actually configured, rather than a fixed count."""
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

        item = {
                        "elementType": "section",
                        "headingType": "h2",
                        "headingContent": sectionTitle,
                        "text": ""
        }
        myReport["Report"].append(item)

        item = {
                        "elementType": "plot",
                        "type": "scatter",
                        "title": "",
                        "xaxis": {"string": "Elapsed Time (s)"},
                        "yaxis": {"string": yAxisLabel},
                        "showTable": False,
                        "plotWidth": "800px",
                        "data": plotData
        }
        myReport["Report"].append(item)

def _addPlotGrid(myReport, gridTitle, cells, columns=4, cellPlotWidth=220, cellPlotHeight=180):
        """Lay out a family of related small plots in a grid instead of one full-width plot per row,
        using scriptManager's "gridFormatting" elementType (a borderless HTML table you build cell by
        cell: start -> [newItem ... endItem]* -> newRow between rows -> end).
        cells: list of (cellHeading, yAxisLabel, series) tuples, series in the same (label, points,
        color) format _addTimeSeriesPlot takes."""
        validCells = []
        for cellHeading, yAxisLabel, series in cells:
                nonEmptySeries = [(label, points, color) for (label, points, color) in series if len(points) > 0]
                if nonEmptySeries:
                        validCells.append((cellHeading, yAxisLabel, nonEmptySeries))
                else:
                        print(">>> No data for grid cell '{}' in '{}'; leaving it out.".format(cellHeading, gridTitle))
        if not validCells:
                print(">>> No data available at all for plot grid: {}; skipping it entirely.".format(gridTitle))
                return

        myReport["Report"].append({
                "elementType": "section", "headingType": "h2", "headingContent": gridTitle, "text": ""
        })

        myReport["Report"].append({"elementType": "gridFormatting", "action": "start"})
        for i, (cellHeading, yAxisLabel, series) in enumerate(validCells):
                if i > 0 and i % columns == 0:
                        myReport["Report"].append({"elementType": "gridFormatting", "action": "newRow"})
                myReport["Report"].append({"elementType": "gridFormatting", "action": "newItem", "padding-left": 5, "padding-right": 5})
                myReport["Report"].append({"elementType": "section", "headingType": "h4", "headingContent": cellHeading, "text": ""})
                myReport["Report"].append({
                        "elementType": "plot",
                        "type": "scatter",
                        "title": "",
                        "xaxis": {"string": "Elapsed Time (s)"},
                        "yaxis": {"string": yAxisLabel},
                        "showTable": False,
                        "plotWidth": "{}px".format(cellPlotWidth),
                        "plotHeight": "{}px".format(cellPlotHeight),
                        "data": [
                                {"label": label, "color": color, "width": 1, "radius": 0, "data": points, "fill": -1, "style": "solid"}
                                for (label, points, color) in series
                        ]
                })
                myReport["Report"].append({"elementType": "gridFormatting", "action": "endItem"})
        myReport["Report"].append({"elementType": "gridFormatting", "action": "end"})

def _anglesFromCrunch(endpointData):
        """endpointData = crunchedData[e] (list of per-attenuation-step dicts, one per Pal endpoint).
        Returns the sorted list of distinct angle values seen across all steps, or [] if there's no
        real turntable rotation in this data (e.g. plain 'RvR' mode has a single dummy position)."""
        angleSet = set()
        for step in endpointData:
                for p in step.get("positions", []):
                        try:
                                p = float(p)
                        except (TypeError, ValueError):
                                continue
                        if math.isfinite(p):
                                angleSet.add(p)
        return sorted(angleSet)

def _radarSeriesForStat(endpointData, angles, statKey, leafKey, colors):
        """Build one radar series per attenuation step for a given crunched stat.
        statKey: top-level stat name in each attenuation-step dict (e.g. "throughput", "rssi", "mcs").
        leafKey: the field to pull out of each perPos[p] object (e.g. "mean", "dataMean", "rxMode")."""
        series = []
        for i, step in enumerate(endpointData):
                stat = step.get(statKey)
                if not stat or "perPos" not in stat:
                        continue
                perPos = stat["perPos"]
                positions = step.get("positions", [])
                valueByAngle = {}
                for p, posVal in enumerate(positions):
                        try:
                                posVal = float(posVal)
                        except (TypeError, ValueError):
                                continue
                        if p >= len(perPos):
                                continue
                        v = perPos[p].get(leafKey) if isinstance(perPos[p], dict) else None
                        try:
                                v = float(v)
                                if not math.isfinite(v):
                                        v = None
                        except (TypeError, ValueError):
                                v = None
                        valueByAngle[posVal] = v
                values = [valueByAngle.get(a) for a in angles]
                if any(v is not None for v in values):
                        attenLabel = step.get("attenuation", "?")
                        series.append(("{} dB".format(attenLabel), values, colors[i % len(colors)]))
        return series

def _addRadarPlot(myReport, title, angles, series, radialLabel):
        """series: list of (label, values, color); values is a list aligned to angles, may contain
        None for angle/attenuation-step combos with no data (Chart.js just leaves a gap)."""
        validSeries = [(l, v, c) for (l, v, c) in series if any(x is not None for x in v)]
        if not validSeries:
                print(">>> No data available for radar plot: {}; skipping.".format(title))
                return
        myReport["Report"].append({"elementType": "section", "headingType": "h2", "headingContent": title, "text": ""})
        myReport["Report"].append({
                "elementType": "plot",
                "type": "radar",
                "title": "",
                "labels": [str(a) for a in angles],
                "yaxis": {"string": radialLabel},
                "showLegend": True,
                "plotWidth": "500px",
                "data": [{"label": l, "color": c, "fill": False, "data": v, "style": "solid"} for (l, v, c) in validSeries]
        })

def main(directory_name,json_dir,attenToUse,STAisPal,ea_root=None):

        #Expert Analysis normally runs on port 8080 on the same box as script manager.
        #Callers can pass their own ea_root (e.g. from sd2Utils.whereIsEA()); this is just a safe fallback.
        if not ea_root:
                ea_root = "http://"+globalsfile.hostIpAddress+":8080/"
        if ea_root[len(ea_root)-1] != "/": ea_root += "/"

        # Set up some text coloring
        cRed=   '\033[33m'
        cGreen= '\033[32m'
        cNormal='\033[m'

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

        #Grab the directory information as created by SM.
        if directory_name[len(directory_name)-1] != "/": directory_name += "/"
        dirFile = directory_name + "directories.json"
        try:
                f = open(dirFile)
                directoriesJson = json.load(f)
                subDir = directoriesJson["subDirectory"]
                splits = subDir.split("_")
                CL = ""
                for i in range(2,len(splits)):CL += splits[i] + "_"
                CL = CL[0:len(CL)-1]
                theTitle = directoriesJson["title"]
                theName = theTitle.replace(" ","_")
        except:
                CL = ""
                theTitle = "Sample_anyModeRvR"
                theName = theTitle.replace(" ","_")
        #print("Command line part is " + CL)
        print('>>> theTitle: ', theTitle)

        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        print('>>> createReport_main json_dir', json_dir)

        #For this test, pull the JSON information created.
        for x in os.listdir(json_dir):
                if "testresultlog" in x:
                    #print (x)
                    jsonFile = json_dir + x

        f = open(jsonFile)
        testResultLogJson = json.load(f)
        f.close
        #Get all of the zip files in the json directory.
        #Exclude the CSV-only zip and the time-aligned ("-TAJ") zip -- neither of those is the
        #full result archive that Expert Analysis' zip2csv endpoint expects.
        theZips = []
        for x in os.listdir(json_dir):
                if ".zip" in x and "CSV" not in x and "-TAJ" not in x:
                    #print (x)
                    theZips.append(json_dir + x)
        #Most recent first (filenames are timestamp-prefixed).
        theZips.sort(reverse=True)
        #print(theZips)

        # Copy report image(s) to script-manager/storage
        #Verify where scriptManager is running
        api_endpoint = "http://"+globalsfile.hostIpAddress+":5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        if scriptManagerLocation[len(scriptManagerLocation)-1] != "/": scriptManagerLocation += "/"        
        print('>>> scriptManagerLocation: ', scriptManagerLocation)
        storageLocation = scriptManagerLocation+'storage/'
        print('>>> storageLocation: ', storageLocation)

        imageStorage = 'reportImages/mesh/'
        pathToImages = storageLocation+imageStorage
        print(">>> createReport: Copy report image(s) to ", pathToImages)
        if not os.path.exists(pathToImages):
                os.makedirs(pathToImages)

        for file in os.listdir(directory_name):
                #print('>>> createReport file: ', file)
                if ".png" in file or ".jpg" in file:
                        print('>>> createReport copying ', file)
                        command = 'cp ' + directory_name + '/' + file + ' ' + pathToImages + file
                        #print('>>> command ', command)
                        os.popen(command)
                        time.sleep(1)

        #print('>>> EXIT @ createreport LINE 81')
        #sys.exit()

        #Write a report
        myReport = {}
        myReport["Title"] = theTitle
        myReport["Report"] = []


        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"System Diagram",
                "text": ""
        }
        myReport["Report"].append(item)

        '''' ALTERNATE WAY
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"System Diagram",
                "text": "<img src = 'http://10.100.103.183:4000/api/v1/diagrams/system_diagram.png' width='760px'>"
        }
        '''

        imgPath = imageStorage+"STACK-MAX-Diagram.png"
        print('>>> imgPath: ', imgPath)
        item ={
                "elementType":"image",
                "path":imgPath,
                "alt":"STACK-MAX System Diagram",
                "width":"800"
                }

        myReport["Report"].append(item)

        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Test Information Summary",
                "text": ""
        }
        myReport["Report"].append(item)

        testname = testResultLogJson["testInfo"]["name"]
        new_testname = testname.replace("_", " ")
        from datetime import datetime
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        fwString = ""
        palFw = {}
        palFw = testResultLogJson['testInfo']["palFWversions"]
        #print('>>> palFw: ', palFw)
        i = 0
        j = 0
        for key in palFw:
                if "STApal" in key:
                    m = str(key)
                    new = m.replace("-STApal", "")
                    if i == 0 :
                        fwString = fwString + "STApal Version :<br>" + new + " :" + palFw[key] + "<br>"
                    else :
                        fwString = fwString + new + " :" + palFw[key] + "<br>"
                    i = i + 1
                if "Pal-" in key:
                    if j == 0 :
                        fwString = fwString + "PAL Version :<br>" + key + " :" + palFw[key] + "<br>"
                    else :
                        fwString = fwString + key + " :" + palFw[key] + "<br>"
                    j = j + 1
        #print('>>> fwString: ', fwString)
        item = {
                "elementType": "table",
                "type": "table",
                "title": "",
                "tableWidth": "700px",
                "data": [
                    {
                        "data": [
                        "Script Version",
                        "Spirent OCTOBOX Software Version",
                        "DUT Model Name",
                        "DUT Firmware Version",
                        "Pal/STApal Version",
                        "Total Run Time (HH:MM:SS)",
                        "Date and Time",
                        "Test Name"
                        ]
                    },
                    {
                        "data": [
                            testResultLogJson["testInfo"]["scriptSuiteVersion"],
                            testResultLogJson["testInfo"]["starDustVersion"],
                            testResultLogJson["testInfo"]["model"],
                            testResultLogJson["testInfo"]["revision"],
                            fwString,
                            testResultLogJson["testRunTime"],
                            dt_string,
                            new_testname
                        ]
                    }
                ]
        }
        myReport["Report"].append(item)

        ############## Location of data
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Path to stored data",
                "text": json_dir
        }
        myReport["Report"].append(item)

        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Test Description",
                "text": testResultLogJson["testInfo"]["description"]
        }
        myReport["Report"].append(item)

        item = {"elementType": "pagebreak"}
        myReport["Report"].append(item)

        # #################### EXPERT ANALYSIS ON THE RAW JSON ARCHIVE #######################
        # Take the zipped archive of per-endpoint JSONs that the automation script produced,
        # and run it through the Expert Analysis service's archive pipeline:
        #   zip -> zip2csv -> CSV -> objectify -> headers/dataSet -> crunch -> crunchedData/Notes

        crunchedData = None
        eaNotes = {}
        headers = None
        dataSet = None

        if len(theZips) == 0:
                print(">>> No result archive zip found in {}; skipping Expert Analysis.".format(json_dir))
        else:
                archiveFile = theZips[0]
                print(">>> Running Expert Analysis on archive: {}".format(archiveFile))

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

                        api_endpoint = ea_root + "crunch"
                        theResponse = requests.post(url=api_endpoint, data={'headers': headers, 'dataSet': json.dumps(dataSet), 'run': 1})
                        theJson = json.loads(theResponse.text)
                        if "error" in theJson:
                                print(">>> crunch returned an error: {}".format(theJson["error"]))
                        crunchedData = theJson["crunchedData"]
                        eaNotes = theJson.get("Notes", {})

                        print(">>> Expert Analysis crunch complete. {} endpoint(s) of crunched data available.".format(len(crunchedData) if crunchedData else 0))

                except Exception as err:
                        print(">>> Expert Analysis pipeline failed: {}".format(err))
                        crunchedData = None

        #Surface any Alerts Expert Analysis found.
        alerts = eaNotes["Alerts"] if eaNotes and "Alerts" in eaNotes else []
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent": "Expert Analysis Alerts",
                "text": "\n".join(alerts) if alerts else "There are no Alerts to report."
        }
        myReport["Report"].append(item)

        # -------------------------------------------------------------------------------------
        # CUSTOM TIME-SERIES PLOTS (built from the objectified `dataSet` -- a row-per-second time
        # series -- not from `crunchedData`, which is bucketed by attenuation step instead of time).
        # -------------------------------------------------------------------------------------
        if headers and dataSet:
                try:
                        throughputHeader = None
                        for h in headers:
                                if "Throughput [Mbps]" in h and "Aggregate" in h and "calc" not in h.lower():
                                        throughputHeader = h
                                        break
                        if not throughputHeader:
                                for h in headers:
                                        if "Throughput [Mbps]" in h and "calc" not in h.lower():
                                                throughputHeader = h
                                                break

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
                                print(">>> Could not find a time column; skipping all time-series plots.")
                        else:
                                t0 = None
                                for row in dataSet:
                                        try:
                                                t0 = float(row.get(timeHeader))
                                                if math.isfinite(t0):
                                                        break
                                        except (TypeError, ValueError):
                                                continue
                                if t0 is None:
                                        print(">>> Could not find a usable starting time value; skipping all time-series plots.")
                                else:
                                        if throughputHeader:
                                                points = _extractSeries(dataSet, timeHeader, throughputHeader, t0)
                                                _addTimeSeriesPlot(myReport, "Average Throughput vs. Time", "Throughput (Mbps)",
                                                        [("Throughput ({})".format(throughputHeader), points, "green")])
                                        else:
                                                print(">>> Could not find a throughput column; skipping throughput-vs-time plot.")

                                        tpNumbers = _findNumberedEntities(headers, "Traffic Pair ")
                                        tpSeries = []
                                        for i, tpNum in enumerate(tpNumbers):
                                                tpHeader = _findHeaderWithPrefix(headers, "Traffic Pair {} ".format(tpNum), ["Throughput [Mbps]"])
                                                if tpHeader and "calc" not in tpHeader.lower():
                                                        points = _extractSeries(dataSet, timeHeader, tpHeader, t0)
                                                        tpSeries.append(("Traffic Pair {}".format(tpNum), points, colors[i % len(colors)]))
                                        if tpSeries and len(tpNumbers) > 1:
                                                _addTimeSeriesPlot(myReport, "Throughput vs. Time (per Traffic Pair)", "Throughput (Mbps)", tpSeries)

                                        if STAisPal:
                                                endpointNumbers = _findNumberedEntities(headers, "Pal Endpoint ")
                                                for epNum in endpointNumbers:
                                                        prefix = "Pal Endpoint {} ".format(epNum)
                                                        epLabel = "Pal Endpoint {}".format(epNum)

                                                        def _ulDlSeries(statSubstrings):
                                                                dlH = _findHeaderWithPrefix(headers, prefix, ["RX"] + statSubstrings)
                                                                ulH = _findHeaderWithPrefix(headers, prefix, ["TX"] + statSubstrings)
                                                                return [("Downlink (RX)", _extractSeries(dataSet, timeHeader, dlH, t0), "blue"),
                                                                                ("Uplink (TX)", _extractSeries(dataSet, timeHeader, ulH, t0), "red")]

                                                        _addPlotGrid(myReport, "PHY Layer Stats vs. Time - {}".format(epLabel), [
                                                                ("PHY Rate (Mbps)", "PHY Rate (Mbps)", _ulDlSeries(["Rate [Mbps]", "Mode"])),
                                                                ("MCS Index", "MCS Index", _ulDlSeries(["MCS", "Mode"])),
                                                                ("Bandwidth (MHz)", "Bandwidth (MHz)", _ulDlSeries(["Bandwidth [MHz]", "Mode"])),
                                                                ("Streams (Nss)", "Streams (Nss)", _ulDlSeries(["Nss", "Mode"])),
                                                        ], columns=4, cellPlotWidth=220, cellPlotHeight=180)
                except Exception as err:
                        print(">>> Could not build time-series plots: {}".format(err))

        # -------------------------------------------------------------------------------------
        # ANGLE-BASED PLOTS (turntable rotation tests only -- rvrMode other than plain 'RvR').
        # Built from `crunchedData`, which for each attenuation step also carries a per-angle
        # ("perPos") breakdown for throughput, RSSI, MCS, bandwidth, and streams.
        # -------------------------------------------------------------------------------------
        if crunchedData:
                try:
                        for epIdx, endpointData in enumerate(crunchedData):
                                angles = _anglesFromCrunch(endpointData)
                                if len(angles) <= 1:
                                        continue  # no real rotation in this data (plain RvR mode, or a single fixed position)
                                epLabel = "Endpoint {}".format(epIdx + 1)

                                series = _radarSeriesForStat(endpointData, angles, "throughput", "mean", colors)
                                _addRadarPlot(myReport, "Throughput vs. Angle - {}".format(epLabel), angles, series, "Throughput (Mbps)")

                                if STAisPal:
                                        series = _radarSeriesForStat(endpointData, angles, "rssi", "dataMean", colors)
                                        _addRadarPlot(myReport, "Data RSSI vs. Angle - {}".format(epLabel), angles, series, "RSSI (dB)")

                                        dlSeries = _radarSeriesForStat(endpointData, angles, "mcs", "rxMode", colors)
                                        ulSeries = _radarSeriesForStat(endpointData, angles, "mcs", "txMode", colors)
                                        _addRadarPlot(myReport, "Downlink MCS vs. Angle - {}".format(epLabel), angles, dlSeries, "MCS Index")
                                        _addRadarPlot(myReport, "Uplink MCS vs. Angle - {}".format(epLabel), angles, ulSeries, "MCS Index")

                                        dlSeries = _radarSeriesForStat(endpointData, angles, "BW", "rxMode", colors)
                                        ulSeries = _radarSeriesForStat(endpointData, angles, "BW", "txMode", colors)
                                        _addRadarPlot(myReport, "Downlink Bandwidth vs. Angle - {}".format(epLabel), angles, dlSeries, "Bandwidth (MHz)")
                                        _addRadarPlot(myReport, "Uplink Bandwidth vs. Angle - {}".format(epLabel), angles, ulSeries, "Bandwidth (MHz)")

                                        dlSeries = _radarSeriesForStat(endpointData, angles, "streams", "rxMode", colors)
                                        ulSeries = _radarSeriesForStat(endpointData, angles, "streams", "txMode", colors)
                                        _addRadarPlot(myReport, "Downlink Streams vs. Angle - {}".format(epLabel), angles, dlSeries, "Streams (Nss)")
                                        _addRadarPlot(myReport, "Uplink Streams vs. Angle - {}".format(epLabel), angles, ulSeries, "Streams (Nss)")
                except Exception as err:
                        print(">>> Could not build angle-based plots: {}".format(err))


        # #################### PLOTS #######################
        # RvR throughput / RSSI. Guarded against no band/direction key being present at all
        # (e.g. if the THROUGHPUT avgDataPost call failed upstream but the script continued) --
        # otherwise 'banddir' would be undefined and crash the rest of this section.
        bandLabels = {"24g": "2.4 GHz", "5g": "5 GHz", "6g": "6 GHz"}
        banddir = None
        plotTitle = None
        for band in ["24g", "5g", "6g"]:
                for direction, dirLabel in [("down", "Downlink"), ("up", "Uplink")]:
                        candidate = "{}_{}".format(band, direction)
                        if candidate in testResultLogJson.keys():
                                banddir = candidate
                                plotTitle = "{} {} RvR ".format(bandLabels[band], dirLabel)
                                break
                if banddir:
                        break

        if banddir is None:
                print(">>> No RvR band/direction result data found in the test result log; skipping RvR plots.")
        else:
                print('>>> banddir: ', banddir)

                if testResultLogJson[banddir].get("avg"):
                        plotTitlemod = plotTitle + " - Average Throughput (Mbps)"
                        item = {
                                "elementType": "section",
                                "headingType": "h2",
                                "headingContent":plotTitlemod,
                                "text": ""
                        }
                        myReport["Report"].append(item)

                        rvrPlot = []
                        attendata = []
                        for data in testResultLogJson[banddir]["avg"]:
                                #print(data)
                                xData = data["atten"]
                                thisValue = data["value"]
                                #print(xData)
                                #print(thisValue)
                                rvrPlot.append({"x": xData, "y": thisValue})
                        item = {
                                "elementType": "plot",
                                "type": "scatter",
                                "title": "",
                                "xaxis": {"string": "Attenuation (dB)"},
                                "yaxis": {"string": "Throughput (Mbps)", "min":0},
                                "showTable": True,
                                "plotWidth": "800px",
                                "data": [
                                    {
                                        "label": "Throughput",
                                        "color": "blue",
                                        "width": 1,
                                        "radius": 0,
                                        "data": rvrPlot,
                                        "fill": -1,
                                        "style": "solid"
                                    }
                                ]
                        }
                        myReport["Report"].append(item)
                        #pp.pprint(item)
                        #print('>>> EXIT @ createreport LINE 214')
                        #sys.exit()

                if STAisPal and testResultLogJson[banddir].get("rssiMgmtMean"):
                        # RvR Rssi
                        plotTitlemod = plotTitle + "Mean Management RSSI (dB)"
                        item = {
                                "elementType": "section",
                                "headingType": "h2",
                                "headingContent":plotTitlemod,
                                "text": ""
                        }
                        myReport["Report"].append(item)

                        rvrPlot = []
                        attendata = []
                        for data in testResultLogJson[banddir]["rssiMgmtMean"]:
                                #print(data)
                                xData = data["atten"]
                                thisValue = data["value"]
                                #print(xData)
                                #print(thisValue)
                                rvrPlot.append({"x": xData, "y": thisValue})
                        item = {
                                "elementType": "plot",
                                "type": "scatter",
                                "title": plotTitlemod,
                                "xaxis": {"string": "Attenuation (dB)"},
                                "yaxis": {"string": "RSSI (dB)", "min":-100},
                                "showTable": True,
                                "plotWidth": "800px",
                                "data": [
                                    {
                                        "label": "RSSI",
                                        "color": "blue",
                                        "width": 1,
                                        "radius": 0,
                                        "data": rvrPlot,
                                        "fill": -1,
                                        "style": "solid"
                                    }
                                ]
                        }
                        myReport["Report"].append(item)
                        #pp.pprint(item)
                        #print('>>> EXIT @ createreport LINE 180')
                        #sys.exit()


        print("{} JSON report is complete. {}".format(cGreen,cNormal))

        # Safety net: strip any non-finite floats (nan/inf/-inf) anywhere in the report.
        # json.dumps() will silently emit invalid "NaN"/"Infinity" tokens for these instead of
        # raising an error, and the HTML/Chart.js side then fails to parse it.
        def _sanitizeForJSON(obj):
                if isinstance(obj, float):
                        return obj if math.isfinite(obj) else None
                elif isinstance(obj, dict):
                        return {k: _sanitizeForJSON(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                        return [_sanitizeForJSON(v) for v in obj]
                else:
                        return obj
        myReport = _sanitizeForJSON(myReport)

        #Generate the proper html for this report
        api_endpoint = "http://"+globalsfile.hostIpAddress+":5678/jsonToHtmlReport"
        data = {'json':json.dumps(myReport,indent=4)}
        r = requests.post(url=api_endpoint,data=data)
        y = json.loads(r.text)
        html = y["html"]

        print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))

        #Verify where scriptManager is running
        api_endpoint = "http://"+globalsfile.hostIpAddress+":5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        storageLocation = scriptManagerLocation + "/" + "storage/"
        #print("storageLocation is {}".format(storageLocation))
        fileName = theName+".html"
        fullPath = storageLocation + fileName
        #print("The full path for the saved file is {}".format(fullPath))

        #Write out this html file
        f = open(fullPath, "w")
        f.write(html)
        f.close()

        print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

        #Also, store the JSON formatted plot, and put a link to it in ReportList.json.
        jsonName = theName+".json"
        plotPath = storageLocation + jsonName
        f = open(plotPath, "w")
        f.write(json.dumps(myReport,indent=3))
        f.close()
        #.........
        jsonPath = storageLocation + "ReportList.json"
        f = open(jsonPath, "r")
        try:    currentList = json.load(f)
        except: currentList = {}
        f.close()
        currentList[fileName] = plotPath
        f = open(jsonPath, "w")
        f.write(json.dumps(currentList,indent=3))
        f.close()
        #print("Updated the current list to {}".format(currentList))

        #Create a JSON file that will put a link to the previous file into script manager.
        jsonPlot = {}
        jsonPlot["reportLink"] = {
                "val": {"htmlLink": "http://"+globalsfile.hostIpAddress+":5678/storage/"+fileName},
                "label": "Report for " + theTitle,
                "withTitle": theTitle
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'TestReport-'+theName+'.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

#===
#Use this for debugging.  Otherwise, comment it out.
'''
directory_name = "/home/octoscope/Documents/script-home/sd2-scripts/anyModeRvR"
json_dir = "/home/octoscope/Downloads/1_2022-10-04_14-02_anyModeRvR_rvrwr_DL6/"
main(directory_name,json_dir, "QJ-34")
'''
