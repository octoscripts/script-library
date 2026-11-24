import sys
import json
import os
import requests
import base64
import math
import pprint
import time
pp = pprint.PrettyPrinter(indent=4)

from pathlib import Path

def main(directory_name,json_dir,cRvalues):

        lossQuantile = cRvalues["lossQuantile"]

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
                theTitle = "Mesh Roaming"
                theName = theTitle.replace(" ","_")
        #print("Command line part is " + CL)
        print('>>> theTitle: ', theTitle)

        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        print('>>> createReport_main json_dir', json_dir)

        #For this test, pull the JSON information created.
        for x in os.listdir(json_dir):
                #print (x)
                if "testresultlog" in x:
                    jsonFile = json_dir + x

        print("The JSON log file is {}".format(jsonFile))
        f = open(jsonFile)
        testResultLogJson = json.load(f)
        f.close
        
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

        imageStorage = 'reportImages/mesh/'
        pathToImages = storageLocation+imageStorage
        print(">>> createReport: Copy report image(s) to ", pathToImages)
        if not os.path.exists(pathToImages):
                os.makedirs(pathToImages)

        for file in os.listdir(directory_name):
                #print('>>> createReport file: ', file)
                if ".png" in file or ".jpg" in file:
                        print('>>> createReport copying ', file)
                        command = 'cp ' + file + ' ' +pathToImages+ file
                        #print('>>> command ', command)
                        os.popen(command)
                        time.sleep(1)

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
                        fwString = str(fwString) + "STApal Version :<br>" + new + " :" + str(palFw[str(key)]) + "<br>"
                    else :
                        fwString = str(fwString) + str(new) + " :" + str(palFw[str(key)]) + "<br>"
                    i = i + 1
                elif "Pal-" in str(key):
                    if j == 0 :
                        fwString = str(fwString) + "PAL Version :<br>" + str(key) + " :" + str(palFw[str(key)]) + "<br>"
                    else :
                        fwString = str(fwString) + str(key) + " :" + str(palFw[str(key)]) + "<br>"
                    j = j + 1
                elif "P" in str(key):
                    if j == 0 :
                        fwString = str(fwString) + "PAL Version :<br>" + str(str(key)) + " :" + str(str(palFw[str(key)])) + "<br>"
                    else :
                        fwString = str(fwString) + str(key) + " :" + str(palFw[str(key)]) + "<br>"
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
                        "Mesh Script Version",
                        "Spirent OCTOBOX Software Version",
                        "DUT Model Name",
                        "DUT Firmware Version",
                        "Pal/STApal Version",
                        #"Total Run Time (HH:MM:SS)",
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
                            #testResultLogJson["testRunTime"],
                            dt_string,
                            new_testname
                        ]
                    }
                ]
        }
        myReport["Report"].append(item)

        palsUsed = []
        for key in testResultLogJson["testInfo"]["palFWversions"]:
                palsUsed.append(key)
        vstasCreated = testResultLogJson["allTestResults"][0]["nTrafficPairs"]

        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Test configuration"
        }
        myReport["Report"].append(item)        
        item = {
                "elementType": "table",
                "type": "table",
                "title": "",
                "tableWidth": "700px",
                "data": [
                        {
                                "data": [
                                        "Traffic Tool",
                                        "Traffic Type",
                                        "Traffic Direction",
                                        "Traffic Bandwidth",
                                        "Pals used",
                                        "VSTAs per Pal",
                                        "Packet Loss Target (%)",
                                        "Step Size Target",
                                ]
                        },
                        {
                                "data": [
                                        testResultLogJson["testInfo"]["trafficType"],
                                        testResultLogJson["testInfo"]["trafficMode"],
                                        testResultLogJson["testInfo"]["upOrDown"],
                                        testResultLogJson["trafficBW"],
                                        (palsUsed),
                                        vstasCreated,
                                        str(testResultLogJson["packetLossTarget"]) + "%",
                                        str(testResultLogJson["stepSizeTarget"])                                       
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

        allTestResults = testResultLogJson["allTestResults"]
        packetLossTarget = testResultLogJson["packetLossTarget"]
        trafficBW = testResultLogJson["trafficBW"]
        trafficBW = trafficBW.upper().replace("M","").replace("K","")
        trafficBW = int(trafficBW)

        #===============================================
        plotTitlemod = "Packet Loss vs. Number of Pairs"
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":plotTitlemod,
                "text": ""
        }
        myReport["Report"].append(item)

        xyPlot = []
        for test in allTestResults:
                xData = test["activePairs"]
                thisValue = test["lossMetric"]
                xyPlot.append({"x": xData, "y": thisValue})
        ordered = []
        while len(xyPlot) > 0:
                item = 0
                for i in range(0,len(xyPlot)):
                        if xyPlot[i]["x"] < xyPlot[item]["x"]: item = i
                ordered.append(xyPlot[item])
                xyPlot.remove(xyPlot[item])
        limit = []
        for element in ordered: limit.append({"x":element["x"],"y":packetLossTarget})
        
        item = {
                "elementType": "plot",
                "type": "scatter",
                "title": "",
                "xaxis": {"string": "Number of active traffic pairs"},
                "yaxis": {"string": "Packet Loss Rate (%)", "min":0},
                "showTable": True,
                "plotWidth": "800px",
                "data": [
                        {
                                "label": "Packet Loss Rate",
                                "color": "blue",
                                "width": 1,
                                "radius": 3,
                                "data": ordered,
                                "fill": -1,
                                "style": "solid"
                        },
                        {
                                "label": "Packet loss limit",
                                "color": "red",
                                "width": 1,
                                "radius": 0,
                                "data": limit,
                                "fill": -1,
                                "style": "solid"
                        }
                ]
        }
        myReport["Report"].append(item)

        #===============================================
        plotTitlemod = "Aggregate Throughput vs. Number of Pairs"
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":plotTitlemod,
                "text": ""
        }
        myReport["Report"].append(item)

        xyPlot = []
        for test in allTestResults:
                xData = test["activePairs"]
                thisArray = test["allThroughputs"]
                thisValue = 0
                for value in thisArray: thisValue += value
                xyPlot.append({"x": xData, "y": thisValue})
        ordered = []
        while len(xyPlot) > 0:
                item = 0
                for i in range(0,len(xyPlot)):
                        if xyPlot[i]["x"] < xyPlot[item]["x"]: item = i
                ordered.append(xyPlot[item])
                xyPlot.remove(xyPlot[item])
        limit = []
        for element in ordered: limit.append({"x":element["x"],"y":element["x"]*trafficBW})
        
        item = {
                "elementType": "plot",
                "type": "scatter",
                "title": "",
                "xaxis": {"string": "Number of active traffic pairs"},
                "yaxis": {"string": "Aggegate Throughput (Mbps)", "min":0},
                "showTable": True,
                "plotWidth": "800px",
                "data": [
                        {
                                "label": "Aggregate Throutput",
                                "color": "blue",
                                "width": 1,
                                "radius": 3,
                                "data": ordered,
                                "fill": -1,
                                "style": "solid"
                        },
                        {
                                "label": "Throughput Expected",
                                "color": "red",
                                "width": 1,
                                "radius": 0,
                                "data": limit,
                                "fill": -1,
                                "style": "solid"
                        }
                ]
        }
        myReport["Report"].append(item)
        
        #===============================================
        plotTitlemod = "Throughput divergence from expectation"
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":plotTitlemod,
                "text": ""
        }
        myReport["Report"].append(item)

        xyPlot = []
        for test in allTestResults:
                xData = test["activePairs"]
                thisArray = test["allThroughputs"]
                thisValue = 0
                for value in thisArray: thisValue += value
                xyPlot.append({"x": xData, "y": thisValue})
        ordered = []
        while len(xyPlot) > 0:
                item = 0
                for i in range(0,len(xyPlot)):
                        if xyPlot[i]["x"] < xyPlot[item]["x"]: item = i
                ordered.append(xyPlot[item])
                xyPlot.remove(xyPlot[item])
        limit = []
        for element in ordered: limit.append({"x":element["x"],"y":element["x"]*trafficBW})

        deltaDat = []
        for i in range(0,len(ordered)): deltaDat.append({"x":ordered[i]["x"],"y":(ordered[i]["y"]-limit[i]["y"])/limit[i]["y"]*100})
        
        item = {
                "elementType": "plot",
                "type": "scatter",
                "title": "",
                "xaxis": {"string": "Number of active traffic pairs"},
                "yaxis": {"string": "% difference in throughput from expected (%)"},
                "showTable": True,
                "plotWidth": "800px",
                "data": [
                        {
                                "label": "Throughput divergence",
                                "color": "blue",
                                "width": 1,
                                "radius": 3,
                                "data": deltaDat,
                                "fill": -1,
                                "style": "solid"
                        }
                ]
        }
        myReport["Report"].append(item)
        
        #===============================================
        plotTitlemod = "Difference between Found and Expected pairs vs. Number of Pairs"
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":plotTitlemod,
                "text": ""
        }
        myReport["Report"].append(item)

        countNonZero = 0
        xyPlot = []
        for test in allTestResults:
                xData = test["activePairs"]
                thisValue = len(test["allThroughputs"]) - test["activePairs"]
                if thisValue != 0: countNonZero +=1
                xyPlot.append({"x": xData, "y": thisValue})

        if countNonZero == 0:
                item = {
                        "elementType": "text",
                        "text": "In all cases found valid data for all of the traffic pairs."
                }
                myReport["Report"].append(item)

        else:                
                ordered = []
                while len(xyPlot) > 0:
                        item = 0
                        for i in range(0,len(xyPlot)):
                                if xyPlot[i]["x"] < xyPlot[item]["x"]: item = i
                        ordered.append(xyPlot[item])
                        xyPlot.remove(xyPlot[item])

                labels = []
                barDat = []
                for item in ordered:
                        labels.append(item["x"])
                        barDat.append(item["y"])

                item = {
                        "elementType": "plot",
                        "type": "bar",
                        "title": "",
                        "labels": labels,
                        "showDataValues":{"show":False,"color":"green","align":"top","offset":"12","fontSize":"30"},
                        "xaxis": {"string": "Expected number of active traffic pairs"},
                        "yaxis": {"string": "Found-Expected traffic pairs", "max":0},
                        "showTable": True,
                        "plotWidth": "800px",
                        "data": [
                                {
                                        "type": "bar",
                                        "label": "Found-Expected traffic pairs",
                                        "color": "blue",
                                        "width": 1,
                                        "radius": 3,
                                        "data": barDat,
                                        "fill": -1,
                                        "style": "solid"
                                }
                        ]
                }
                myReport["Report"].append(item)
        
        highestGood = -1
        lowestBad =   -1
        for i in range(0,len(allTestResults)):
                if allTestResults[i]["good"]:
                        if highestGood < 0:                                                               highestGood = i
                        if allTestResults[i]["activePairs"] > allTestResults[highestGood]["activePairs"]: highestGood = i
                if not allTestResults[i]["good"]:
                        if lowestBad < 0:                                                                 lowestBad = i
                        if allTestResults[i]["activePairs"] < allTestResults[lowestBad]["activePairs"]:   lowestBad = i

        hgi = highestGood
        lbi = lowestBad
        highestGood = allTestResults[highestGood]["activePairs"]
        lowestBad   = allTestResults[lowestBad]["activePairs"]

        plotTitlemod = "The results for the highest number of traffic pairs supported"
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":plotTitlemod,
                "text": ""
        }
        myReport["Report"].append(item)
        
        item = {
                "elementType": "text",
                "text": "\nPacket loss limit set at {}%".format(packetLossTarget)
        }
        myReport["Report"].append(item)
        
        item = {
                "elementType": "text",
                "text": "\nHighest good value: {}, and Lowest bad value: {}".format(highestGood,lowestBad)
        }
        myReport["Report"].append(item)
        
        item = {
                "elementType": "text",
                "text": "\nPer-pair traffic rate for the last good value: {} Mbps.".format(round(allTestResults[hgi]["allThroughputs"][0],0))
        }
        myReport["Report"].append(item)

        totalThroughput = sum(allTestResults[hgi]["allThroughputs"])
        item = {
                "elementType": "text",
                "text": "\nTotal throughput supported for the last good value: {} Mbps.".format(round(totalThroughput,0))
        }
        myReport["Report"].append(item)


        labels = []
        barDat = []
        limDat = []
        i = 1
        for item in allTestResults[hgi]["allLostPercent"]:
                labels.append(i)
                barDat.append(round(item,2))
                limDat.append(packetLossTarget)
                i+=1

        #Get the quantile value
        if(len(barDat)>0):
                sorted = []
                for item in barDat: sorted.append(item)
                sorted.sort()
                length = len(sorted)
                qItem = min(length-1, math.floor((lossQuantile/100)*(length+1))-1)
                quantile = sorted[qItem]
        else:
                quantile = 0
                
        
        plotTitle = "Lost plot data for the (good) case of {} traffic pairs. {}% quantile packet loss is {}%".format(highestGood,lossQuantile,quantile)
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":plotTitle,
                "text": ""
        }
        myReport["Report"].append(item)

        item = {
                "elementType": "plot",
                "type": "bar",
                "title": "",
                "labels": labels,
                "showDataValues":{"show":False,"color":"green","align":"top","offset":"12","fontSize":"30"},
                "xaxis": {"string": "Traffic pair index"},
                "yaxis": {"string": "Lost Percent Value (%)", "min":0},
                "showTable": True,
                "plotWidth": "800px",
                "data": [
                        {
                                "type": "bar",
                                "label": "Lost Percent Value (%)",
                                "color": "blue",
                                "width": 1,
                                "radius": 3,
                                "data": barDat,
                                "fill": -1,
                                "style": "solid"
                        },
		        {
		                "type" :"line",
		                "label":"Packet Loss Limit",
		                "color":"green",
		                "width": 1,
                                "radius":0,
		                "data":limDat,
		                "fill":False,
		                "style": "long-dash"
		        }                        
                ]
        }
        myReport["Report"].append(item)
        
        #-------------
        labels = []
        barDat = []
        limDat = []
        i = 1
        for item in allTestResults[lbi]["allLostPercent"]:
                labels.append(i)
                barDat.append(round(item,2))
                limDat.append(packetLossTarget)
                i+=1

        #Get the quantile value
        if(len(barDat)>0):
                sorted = []
                for item in barDat: sorted.append(item)
                sorted.sort()
                length = len(sorted)
                qItem = min(length-1, math.floor((lossQuantile/100)*(length+1))-1)
                quantile = sorted[qItem]
        else:
                quantile = 0
                
        
        plotTitle = "Lost plot data for the (bad) case of {} traffic pairs. {}% quantile packet loss is {}%".format(lowestBad,lossQuantile,quantile)
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":plotTitle,
                "text": ""
        }
        myReport["Report"].append(item)
                                
        item = {
                "elementType": "plot",
                "type": "bar",
                "title": "",
                "labels": labels,
                "showDataValues":{"show":False,"color":"green","align":"top","offset":"12","fontSize":"30"},
                "xaxis": {"string": "Traffic pair index"},
                "yaxis": {"string": "Lost Percent Value (%)", "min":0},
                "showTable": True,
                "plotWidth": "800px",
                "data": [
                        {
                                "type": "bar",
                                "label": "Lost Percent Value (%)",
                                "color": "blue",
                                "width": 1,
                                "radius": 3,
                                "data": barDat,
                                "fill": -1,
                                "style": "solid"
                        },
		        {
		                "type" :"line",
		                "label":"Packet Loss Limit",
		                "color":"green",
		                "width": 1,
                                "radius":0,
		                "data":limDat,
		                "fill":False,
		                "style": "long-dash"
		        }                                                
                ]
        }
        myReport["Report"].append(item)

        #---------------------
        lastPacketData = testResultLogJson["lastPacketData"]

        labels = []
        lineDat = []
        limDat = []
        i = 1
        for item in lastPacketData["aggregate"]["lostPercent"]:
                labels.append(i)
                lineDat.append(round(item,2))
                limDat.append(packetLossTarget)
                i+=1

        #Get the quantile value
        if(len(lineDat)>0):
                sorted = []
                for item in lineDat: sorted.append(item)
                sorted.sort()
                length = len(sorted)
                qItem = min(length-1, math.floor((lossQuantile/100)*(length+1))-1)
                quantile = sorted[qItem]
        else:
                quantile = 0

        plotTitle = "Aggregated lost plot data for the last good case of {} traffic pairs. {}% quantile packet loss is {}%".format(highestGood,lossQuantile,quantile)
        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":plotTitle,
                "text": ""
        }
        myReport["Report"].append(item)
                        
        item = {
                "elementType": "plot",
                "type": "line",
                "title": "",
                "labels": labels,
                "showDataValues":{"show":False,"color":"green","align":"top","offset":"12","fontSize":"30"},
                "xaxis": {"string": "Time (sec)"},
                "yaxis": {"string": "Aggregated Lost Percent Value (%)", "min":0},
                "showTable": True,
                "plotWidth": "800px",
                "data": [
                        {
                                "type": "line",
                                "label": "Lost Percent Value (%)",
                                "color": "blue",
                                "width": 1,
                                "radius": 3,
                                "data": lineDat,
                                "fill": -1,
                                "style": "solid"
                        },
		        {
		                "type" :"line",
		                "label":"Packet Loss Limit",
		                "color":"green",
		                "width": 1,
                                "radius":0,
		                "data":limDat,
		                "fill":False,
		                "style": "long-dash"
		        }                                                
                ]
        }
        myReport["Report"].append(item)
        
        
        

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
                "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
                "label": "Report for " + theTitle
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'TestReport-'+theName+'.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))


#===
'''
#Use this for debugging.  Otherwise, comment it out.
directory_name = "./" 
json_dir = "/home/octoscope/Documents/automationResults/2026-10-16_09-54_calix/1_2026-10-16_09-54_vstaBinarySearch/"
cRvalues = {"lossQuantile":90}
main(directory_name,json_dir,cRvalues)
'''
