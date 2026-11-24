import sys
import json
import os
import requests
import base64
import pprint
import time
import math
pp = pprint.PrettyPrinter(indent=4)

from pathlib import Path

def _findHeader(headers, mustContainAll):
        """Return the first header string containing every substring in mustContainAll, or None."""
        for h in headers:
                if all(sub in h for sub in mustContainAll):
                        return h
        return None

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

def main(directory_name,json_dir,ea_root=None):

        #Expert Analysis normally runs on port 8080 on the same box as script manager.
        #Callers can pass their own ea_root (e.g. from sd2Utils.whereIsEA()); this is just a safe fallback.
        if not ea_root:
                ea_root = "http://localhost:8080/"
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
            runNumber = splits[0]
            #print('>>> splits: ', splits)
            #theName = splits[2]
            theName = directoriesJson["title"]
            theTitle = theName.replace(" ","_")
        except:
            theTitle = "No Name Found"
            theName = theTitle.replace(" ","_")
            runNumber = "0"                

        print("theName: ", theName)

        # print("Command line part is " + CL)
        print('>>> theTitle: ', theTitle)

        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        print('>>> createReport_main json_dir', json_dir)

        #For this test, pull the JSON information created.
        for x in os.listdir(json_dir):
            #print (x)
            if "testresultlog" in x:
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
                        #print(theZips)
        #Most recent first (filenames are timestamp-prefixed).
        theZips.sort(reverse=True)

        # Copy report image(s) to script-manager/storage
        #Verify where scriptManager is running
        api_endpoint = "http://localhost:5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        if scriptManagerLocation[len(scriptManagerLocation)-1] != "/": scriptManagerLocation += "/"        
        print('>>> scriptManagerLocation: ', scriptManagerLocation)
        storageLocation = scriptManagerLocation+'storage/'
        print('>>> storageLocation: ', storageLocation)

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

        imageStorage = 'reportImages/'
        pathToImages = storageLocation+imageStorage
        print(">>> createReport: Copy report image(s) to ", pathToImages)
        if not os.path.exists(pathToImages):
                    os.makedirs(pathToImages)
        #print(directory_name)
        for file in os.listdir(directory_name):
                #print('>>> createReport file: ', file)
                if ".png" in file or ".jpg" in file:
                        #print('>>> createReport copying ', file)
                        command = 'cp ' + directory_name + file + ' ' + pathToImages + file
                        #print('>>> command ', command)
                        os.popen(command)
                        time.sleep(1)

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
                    #fwString = fwString + "PAL Version :<br>" + key + " :" + palFw[key] + "<br>"
                    fwString = "{} PAL Version :<br/> {} : {} <br/>".format(fwString,key, palFw[key])
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
        # crunchedData/Notes are then available for whatever custom plots/tables you want to add below.

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
                        #Uncomment to inspect the actual shape of crunchedData/headers/dataSet while building a new custom plot:
                        #pp.pprint(headers)
                        #pp.pprint(crunchedData)

                except Exception as err:
                        print(">>> Expert Analysis pipeline failed: {}".format(err))
                        crunchedData = None

        #Surface any Alerts Expert Analysis found, same convention used elsewhere (e.g. OFDMA-Decode's createReport).
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
        #
        # For PHY-layer stats (rate/MCS/bandwidth/streams), "RX" at the STA endpoint corresponds to
        # downlink (AP -> STA) and "TX" corresponds to uplink (STA -> AP), regardless of which
        # direction the iperf traffic itself was run in. We use the per-second "Mode" statistic
        # (the single most-represented value in that second) as the representative instantaneous
        # value, rather than Min/Max, since that's the natural choice for a plain time-series line.
        # These all currently assume a single Pal Endpoint (endpoint 1); if a test has more than
        # one STA/endpoint, this would need to loop over endpoints and add a series per endpoint.
        # -------------------------------------------------------------------------------------
        if headers and dataSet:
                try:
                        # Find the aggregate throughput column. objectify() recomputes this column itself
                        # as the sum of all per-traffic-pair throughputs, so it's reliable even though the
                        # raw CSV often shows "#N/A" in that column before objectify runs.
                        throughputHeader = None
                        for h in headers:
                                if "Throughput [Mbps]" in h and "Aggregate" in h and "calc" not in h.lower():
                                        throughputHeader = h
                                        break
                        if not throughputHeader:
                                # Fall back to any single throughput column if there's no aggregate one.
                                for h in headers:
                                        if "Throughput [Mbps]" in h and "calc" not in h.lower():
                                                throughputHeader = h
                                                break

                        otherThroughputHeaders = []
                        for header in headers:
                            if "Throughput [Mbps]" in header and "Aggregate" not in header and "calc" not in header: otherThroughputHeaders.append(header)
                        otherThroughputHeaders.sort()
                        #print(otherThroughputHeaders)

                        # Find a time column. Prefer a wall-clock timestamp ("Server timestamp", in
                        # seconds) over the synthetic "Time [ms]" filler objectify() adds when there's
                        # no better time column, since the real timestamp gives an evenly-scaled x-axis.
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
                                # Anchor all plots to the same t0 (first parseable time value) so their x-axes line up.
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
                                        # --- Average Throughput vs. Time ---
                                        allThroughputPlots = []
                                        if throughputHeader:
                                                points = _extractSeries(dataSet, timeHeader, throughputHeader, t0)
                                                allThroughputPlots.append(("Throughput ({})".format(throughputHeader), points, "green"))
                                        otherPoints = []
                                        icnt = 10
                                        if len(otherThroughputHeaders)>0:
                                            for otherHeader in otherThroughputHeaders:
                                                thesePoints = _extractSeries(dataSet, timeHeader, otherHeader, t0)
                                                otherPoints.append(thesePoints)
                                                thisColor = colors[icnt % len(colors)]
                                                allThroughputPlots.append(("Throughput ({})".format(otherHeader), thesePoints, thisColor))
                                                icnt += 1
                                        if len(allThroughputPlots)>0:
                                            _addTimeSeriesPlot(myReport, "Throughputs vs. Time", "Throughput (Mbps)",allThroughputPlots)
                                        else:
                                                print(">>> Could not find a throughput column; skipping throughput-vs-time plot.")

                                        # --- PHY Rate (UL/DL) vs. Time ---
                                        dlHeader = _findHeader(headers, ["RX rate [Mbps]", "Mode"])
                                        ulHeader = _findHeader(headers, ["TX rate [Mbps]", "Mode"])
                                        dlPoints = _extractSeries(dataSet, timeHeader, dlHeader, t0)
                                        ulPoints = _extractSeries(dataSet, timeHeader, ulHeader, t0)
                                        _addTimeSeriesPlot(myReport, "PHY Rate (UL/DL) vs. Time", "PHY Rate (Mbps)",
                                                [("Downlink (RX)", dlPoints, "blue"), ("Uplink (TX)", ulPoints, "red")])

                                        # --- MCS (UL/DL) vs. Time ---
                                        dlHeader = _findHeader(headers, ["RX MCS", "Mode"])
                                        ulHeader = _findHeader(headers, ["TX MCS", "Mode"])
                                        dlPoints = _extractSeries(dataSet, timeHeader, dlHeader, t0)
                                        ulPoints = _extractSeries(dataSet, timeHeader, ulHeader, t0)
                                        _addTimeSeriesPlot(myReport, "MCS (UL/DL) vs. Time", "MCS Index",
                                                [("Downlink (RX)", dlPoints, "blue"), ("Uplink (TX)", ulPoints, "red")])

                                        # --- Bandwidth (UL/DL) vs. Time ---
                                        dlHeader = _findHeader(headers, ["RX bandwidth [MHz]", "Mode"])
                                        ulHeader = _findHeader(headers, ["TX bandwidth [MHz]", "Mode"])
                                        dlPoints = _extractSeries(dataSet, timeHeader, dlHeader, t0)
                                        ulPoints = _extractSeries(dataSet, timeHeader, ulHeader, t0)
                                        _addTimeSeriesPlot(myReport, "Bandwidth (UL/DL) vs. Time", "Bandwidth (MHz)",
                                                [("Downlink (RX)", dlPoints, "blue"), ("Uplink (TX)", ulPoints, "red")])

                                        # --- Number of Streams (UL/DL) vs. Time ---
                                        dlHeader = _findHeader(headers, ["RX Nss", "Mode"])
                                        ulHeader = _findHeader(headers, ["TX Nss", "Mode"])
                                        dlPoints = _extractSeries(dataSet, timeHeader, dlHeader, t0)
                                        ulPoints = _extractSeries(dataSet, timeHeader, ulHeader, t0)
                                        _addTimeSeriesPlot(myReport, "Number of Streams (UL/DL) vs. Time", "Streams (Nss)",
                                                [("Downlink (RX)", dlPoints, "blue"), ("Uplink (TX)", ulPoints, "red")])
                except Exception as err:
                        print(">>> Could not build time-series plots: {}".format(err))

        # -------------------------------------------------------------------------------------
        # Plots vs. Attenuation
        #

        item = {
                        "elementType": "section",
                        "headingType": "h2",
                        "headingContent": "Plots vs. Attenuation"
        }
        myReport["Report"].append(item)
        

        #Get basic test results information
        api_endpoint = ea_root + "getStats"
        data = {'csv':csv,'filter':'counts'}
        try:
            r = requests.post(url=api_endpoint, data=data, timeout=5)
        except requests.exceptions.RequestException as error:
            info("Error: ", error)
            sys.exit(44)
        
        y = json.loads(r.text)
        #print(json.dumps(y,indent=4))

        item = {
                        "elementType": "section",
                        "headingType": "h2",
                        "headingContent": "Throughput vs. Attenuation"
        }
        
        myReport["Report"].append(item)
        tpNames = y["filteredData"]["trafficPairs"]["map"]
        #print(tpNames)
        theNames = list(tpNames.values())
        theNames.sort()

        tputValues = {}
        attenuations = []
        for tpName in tpNames: tputValues[tpNames[tpName]] = []
        firstEP = crunchedData[0]
        for attenData in firstEP:
            if attenData["attenuation"] not in attenuations: attenuations.append(attenData["attenuation"])
            for index in range(0,len(attenData["tpairData"])):
                aTpairData =  attenData["tpairData"][index]
                #print(aTpairData["throughput"]["mean"])
                tputValues[tpNames[str(index)]].append(aTpairData["throughput"]["mean"])
        allData = []
        idx = -1
        for name in theNames:
            idx += 1
            thisData = []
            theseValues = tputValues[name]
            for i in range(0,len(attenuations)): thisData.append({"x":attenuations[i],"y":theseValues[i]})
            thisPlot = {"data":thisData,"label":name,"color":colors[idx % len(colors)]}
            allData.append(thisPlot)
        #print(allData)

        AveThroughput = []
        for attenData in firstEP:
            AveThroughput.append({"x":attenData["attenuation"],"y":attenData["throughput"]["mean"]})
        allData.append({"data":AveThroughput,"label":"Aggregate Throughput","color":"red","width":3,"radius":1})

        item = {
            "elementType": "plot",
            "type": "scatter",
            "title": "Throughputs vs. Attenuation",
            "xaxis": {"string": "Attenuation (dB)"},
            "yaxis": {"string": "Throughput (dBm)"},
            "showTable": False,
            "plotWidth": "800px",
            "data": allData
        }
        #print(item)
        myReport["Report"].append(item)
            

        print("{} JSON report is complete. {}".format(cGreen,cNormal))

        # Safety net: strip any non-finite floats (nan/inf/-inf) anywhere in the report, not just in
        # the throughput-vs-time plot above. json.dumps() will silently emit invalid "NaN"/"Infinity"
        # tokens for these instead of raising an error, and the HTML/Chart.js side then fails to parse it.
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
        #print("storageLocation is {}".format(storageLocation))
        #fileName = theName+".html"
        fileName = theName + "_" + runNumber + ".html"
        fullPath = storageLocation + fileName
        #print("The full path for the saved file is {}".format(fullPath))

        #Write out this html file
        f = open(fullPath, "w")
        f.write(html)
        f.close()

        print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

        #Also, store the JSON formatted plot, and put a link to it in ReportList.json.
        jsonName = theName + ".json"
        plotPath = storageLocation + jsonName
        f = open(plotPath, "w")
        f.write(json.dumps(myReport,indent=3))
        f.close()

        #......... Update ReportList.json
        jsonPath = storageLocation + "ReportList.json"
        try:	f = open(jsonPath, "r")
        except:	f = open(jsonPath, "w+")	# Create the file if it doesn't exist
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
                        "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
                        "label": "Report for " + theTitle + ", " + runNumber
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'TestReport-'+theTitle+ "_" + runNumber + '.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))


#===
#Use this for debugging.  Otherwise, comment it out.
'''
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-21_17-58_calix/1_2026-10-21_17-58_vstaExample/"
ea_root = "http://localhost:8080/"
main(directory_name,json_dir,ea_root)
'''
