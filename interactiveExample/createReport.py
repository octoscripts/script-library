import sys
import json
import os
import requests
import base64
import pprint
import time
pp = pprint.PrettyPrinter(indent=4)

from pathlib import Path

#################################################################################
# Helpers for the "standard" time-based plots: Throughput vs. Time, and the
# UL/DL combined MCS, Spatial Streams, Bandwidth, and PHY Rate vs. Time grid.
# These pull directly from the per-second dataSet returned by the expert
# analysis "objectify" API (one dict per second, keyed by the CSV column names).
#################################################################################

def toNum(v):
        # Turn a raw CSV/objectify cell into a float, or None if it isn't a real number (e.g. "#N/A").
        if v is None: return None
        s = str(v).strip()
        if s == "" or "N/A" in s.upper(): return None
        try:
                return float(s)
        except (TypeError, ValueError):
                return None

def findFirstTimestamp(dataSet, timeCol):
        for row in dataSet:
                t = toNum(row.get(timeCol))
                if t is not None: return t
        return 0

def buildTimeSeries(dataSet, timeCol, valueCol, t0):
        # Build a [{"x":t,"y":value}, ...] series, skipping rows with a missing time or value.
        # timeCol is "Time [ms]", so convert the elapsed time to seconds for the x-axis.
        series = []
        for row in dataSet:
                t = toNum(row.get(timeCol))
                y = toNum(row.get(valueCol))
                if t is None or y is None: continue
                series.append({"x": round((t - t0)/1000.0, 2), "y": y})
        return series

def parseAliasNames(csvContent, mappingTag):
        # The CSV's own top-of-file comment lines declare the real name behind each traffic pair /
        # pal endpoint, e.g.:
        #   # tpMapping: Traffic Pair 1 is ServerTopalBox-L2-STApal7,1,ServerTopalBox-L2-STApal7
        #   # epMapping: Pal Stats Endpoint 1 is palBox-L2-STApal7 (172.16.28.2_RADIO_2456),1,palBox-L2-STApal7
        # Each line ends in "...,<index>,<name>", where <index> is the same 1-based number used in
        # the matching column headers (e.g. "Traffic Pair 1 Throughput [Mbps]"). Parse that directly
        # out of the raw CSV text rather than trusting expert analysis's internal alias map, which
        # stores these 0-based internally -- so for this CSV's 1-based convention it ends up shifted
        # by one and hands back no name (or the wrong one) for these pairs/endpoints.
        names = {}
        for line in csvContent.splitlines():
                if mappingTag not in line: continue
                parts = line.split(",")
                if len(parts) < 2: continue
                try:
                        num = int(parts[-2].strip())
                except (TypeError, ValueError):
                        continue
                name = parts[-1].strip()
                if name: names[num] = name
        return names

def getCounts(ea_root, csvContent):
        # Ask expert analysis how many traffic pairs/radio endpoints exist. getStats' "counts"
        # filter crunches the CSV and hands back the authoritative lengths -- far more reliable
        # than guessing by scanning column headers with regex, since the same CSV also contains
        # an RvR summary section that reuses similar-looking column names.
        # Returns (numTrafficPairs, numEndpoints).
        resp = requests.post(url=ea_root+"getStats", data={'csv':csvContent, 'filter':'counts'})
        statsJson = json.loads(resp.text)
        if statsJson.get("status") != "OK":
                print(">>> createReport: getStats(counts) returned an error: {}".format(statsJson.get("error")))
                return 0, 0

        filteredData = statsJson.get("filteredData", {})
        numTrafficPairs = filteredData.get("trafficPairs", {}).get("length", 0)
        numEndpoints = filteredData.get("palEndpoints", {}).get("length", 0)
        return numTrafficPairs, numEndpoints

def main(directory_name,json_dir,attenToUse):

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
        '''
        ALTERNATE WAY TITLE from the scriptMachine Title
        # Grab the directory information as created by SM.
        if directory_name[len(directory_name) - 1] != "/": directory_name += "/"
        dirFile = directory_name + "directories.json"
        print('>>> dirFile: ', dirFile)
        try:
                f = open(dirFile)
                directoriesJson = json.load(f)
                subDir = directoriesJson["subDirectory"]
                splits = subDir.split("_")
                CL = ""
                for i in range(2, len(splits)): CL += splits[i] + "_"
                CL = CL[0:len(CL) - 1]
                theTitle = directoriesJson["title"]
                theName = theTitle.replace(" ", "_")
        except:
                CL = ""
                theTitle = "AnyMode Rate Vs Range"
                theName = theTitle.replace(" ", "_")
        '''
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
        #Get all of the zip files in the json directory
        theZips = []
        for x in os.listdir(json_dir):
                if ".zip" in x:
                        #print (x)
                    theZips.append(json_dir + x)
        #print(theZips)

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

        '''' ALTERNATE WAY
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"System Diagram",
                "text": "<img src = 'http://10.100.103.183:4000/api/v1/diagrams/system_diagram.png' width='760px'>"
        }
        '''
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


        # #################### PLOTS #######################
        # RvR throughput
        if "24g_down" in testResultLogJson.keys():
                plotTitle = "2.4 GHz Downlink RvR "
                banddir = "24g_down"
        elif "24g_up" in testResultLogJson.keys():
                plotTitle ="2.4 GHz Uplink RvR "
                banddir = "24g_up"
        elif "5g_down" in testResultLogJson.keys():
                plotTitle = "5 GHz Downlink RvR "
                banddir = "5g_down"
        elif "5g_up" in testResultLogJson.keys():
                plotTitle ="5 GHz Uplink RvR "
                banddir = "5g_up"
        print('>>> banddir: ', banddir)


        if testResultLogJson[banddir]["avg"]:
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

        # RvR Rssi
        if testResultLogJson[banddir]["rssiMgmtMean"]:
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


        #################### STANDARD TIME-BASED PLOTS ####################
        # Throughput vs. Time (single plot, one line per traffic endpoint), and
        # UL/DL combined MCS, Spatial Streams, Bandwidth, and PHY Rate vs. Time
        # (2x2 grid per radio endpoint, no data tables).
        try:
                ea_root = "http://localhost:8080/"
                mainZips = [json_dir + x for x in os.listdir(json_dir) if x.endswith(".zip") and "CSV" not in x and "taJSON" not in x]
                mainZips.sort(reverse=True)

                if mainZips:
                        with open(mainZips[0], "rb") as f:
                                encoded = base64.b64encode(f.read())
                        resp = requests.post(url=ea_root+"zip2csv", data={'zip':encoded})
                        csvJson = json.loads(resp.text)
                        if "error" in csvJson: print(">>> createReport: zip2csv returned an error: {}".format(csvJson["error"]))

                        resp = requests.post(url=ea_root+"objectify", data={'csv':csvJson["csv"]})
                        objJson = json.loads(resp.text)
                        if "error" in objJson: print(">>> createReport: objectify returned an error: {}".format(objJson["error"]))

                        dataSet = objJson["dataSet"]
                        timeCol = "Time [ms]"
                        t0 = findFirstTimestamp(dataSet, timeCol)

                        # Ask expert analysis how many traffic pairs and radio endpoints this run
                        # actually has, instead of guessing from headers. Get their real names
                        # directly from the CSV's own mapping comment lines (see parseAliasNames).
                        numTrafficPairs, numEndpoints = getCounts(ea_root, csvJson["csv"])
                        tpNameMap = parseAliasNames(csvJson["csv"], "tpMapping")
                        epNameMap = parseAliasNames(csvJson["csv"], "epMapping")
                        tpList = [(n, tpNameMap.get(n)) for n in range(1, numTrafficPairs+1)]
                        epList = [(n, epNameMap.get(n)) for n in range(1, numEndpoints+1)]

                        item = {"elementType": "pagebreak"}
                        myReport["Report"].append(item)

                        # ---- Throughput vs. Time ----
                        tpData = []
                        for i, (pairNum, pairName) in enumerate(tpList):
                                colName = "Traffic Pair {} Throughput [Mbps]".format(pairNum)
                                series = buildTimeSeries(dataSet, timeCol, colName, t0)
                                if series:
                                        label = pairName if pairName else "Traffic Pair {}".format(pairNum)
                                        tpData.append({
                                                "label": label,
                                                "color": colors[i % len(colors)],
                                                "width": 1,
                                                "radius": 0,
                                                "data": series,
                                                "fill": -1,
                                                "style": "solid"
                                        })

                        if tpData:
                                item = {
                                        "elementType": "section",
                                        "headingType": "h2",
                                        "headingContent": "Throughput vs. Time",
                                        "text": ""
                                }
                                myReport["Report"].append(item)

                                item = {
                                        "elementType": "plot",
                                        "type": "scatter",
                                        "title": "",
                                        "xaxis": {"string": "Time (s)"},
                                        "yaxis": {"string": "Throughput (Mbps)", "min": 0},
                                        "showTable": False,
                                        "plotWidth": "800px",
                                        "data": tpData
                                }
                                myReport["Report"].append(item)

                        # ---- MCS / Spatial Streams / Bandwidth / PHY Rate vs. Time ----
                        # UL (TX) and DL (RX) combined on each plot, 2x2 grid per radio endpoint, no tables.
                        statSpecs = [
                                ("MCS vs. Time",              "RX MCS Mode",             "TX MCS Mode",             "MCS"),
                                ("Spatial Streams vs. Time",  "RX Nss Mode",             "TX Nss Mode",             "Spatial Streams"),
                                ("Bandwidth vs. Time",        "RX Bandwidth [MHz] Mode", "TX Bandwidth [MHz] Mode","Bandwidth (MHz)"),
                                ("PHY Rate vs. Time",         "RX Rate [Mbps] Mode",     "TX Rate [Mbps] Mode",   "PHY Rate (Mbps)")
                        ]

                        for ep, epName in epList:
                                prefix = "Pal Endpoint {} ".format(ep)
                                epLabel = epName if epName else "Endpoint {}".format(ep)

                                item = {
                                        "elementType": "section",
                                        "headingType": "h2",
                                        "headingContent": "Radio Statistics vs. Time - {}".format(epLabel),
                                        "text": ""
                                }
                                myReport["Report"].append(item)

                                item = {"elementType": "gridFormatting", "action": "start"}
                                myReport["Report"].append(item)

                                for i, (plotTitle, rxCol, txCol, yLabel) in enumerate(statSpecs):
                                        if i == 2:
                                                item = {"elementType": "gridFormatting", "action": "newRow"}
                                                myReport["Report"].append(item)

                                        item = {"elementType": "gridFormatting", "action": "newItem"}
                                        myReport["Report"].append(item)

                                        dlSeries = buildTimeSeries(dataSet, timeCol, prefix+rxCol, t0)
                                        ulSeries = buildTimeSeries(dataSet, timeCol, prefix+txCol, t0)

                                        plotData = []
                                        if dlSeries:
                                                plotData.append({"label":"DL (RX)","color":"blue","width":1,"radius":0,"data":dlSeries,"fill":-1,"style":"solid"})
                                        if ulSeries:
                                                plotData.append({"label":"UL (TX)","color":"red","width":1,"radius":0,"data":ulSeries,"fill":-1,"style":"solid"})

                                        item = {
                                                "elementType": "plot",
                                                "type": "scatter",
                                                "title": plotTitle,
                                                "xaxis": {"string": "Time (s)"},
                                                "yaxis": {"string": yLabel},
                                                "showTable": False,
                                                "plotWidth": "600px",
                                                "plotHeight": "280px",
                                                "data": plotData
                                        }
                                        myReport["Report"].append(item)

                                        item = {"elementType": "gridFormatting", "action": "endItem"}
                                        myReport["Report"].append(item)

                                item = {"elementType": "gridFormatting", "action": "end"}
                                myReport["Report"].append(item)
                else:
                        print(">>> createReport: No non-CSV zip file found in {}; skipping standard time-based plots.".format(json_dir))
        except Exception as err:
                print(">>> createReport: Could not build standard time-based plots: {}".format(err))
        #################### END STANDARD TIME-BASED PLOTS ####################

        print("{} JSON report is complete. {}".format(cGreen,cNormal))

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
                "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
                "label": "Report for " + theTitle + ", " + runNumber
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'TestReport-'+theTitle+ "_" + runNumber + '.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

'''
#===
#Use this for debugging.  Otherwise, comment it out.
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-05_13-00_calix/1_2026-10-05_13-00_interactiveExample/"
main(directory_name,json_dir, "QJ-34")
'''

