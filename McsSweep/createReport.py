import sys
import json
import os
import requests
import base64
from pathlib import Path
from datetime import datetime

def analyze(directory_name,json_dir,ea_root):

    #print(directory_name)
    #print(json_dir)
    #print(ea_root)
    
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
    
    colors = ["red","blue","green","orange","black","grey","purple"]
    curves = []
    ctrlRssiPlots = []
    dataRssiPlots = []
    i = -1

    #Grab the directory information as created by SM.
    if directory_name[len(directory_name)-1] != "/": directory_name += "/"
    dirFile = directory_name + "directories.json"

    try:
        f = open(dirFile)
        directoriesJson = json.load(f)
        subDir = directoriesJson["subDirectory"]
        splits = subDir.split("_")
        runNumber = splits[0]
        CL = ""
        for i in range(2,len(splits)):CL += splits[i] + "_"
        CL = CL[0:len(CL)-1]
        theTitle = directoriesJson["title"]
        theName = theTitle.replace(" ","_")
    except:
        CL = ""
        theTitle = "Mesh Rate vs. Range"
        theName = theTitle.replace(" ","_")
        runNumber = "0"

    if directory_name[len(directory_name)-1] != "/": directory_name += "/"
    if json_dir[len(json_dir)-1] != "/": json_dir += "/"
    
    #Find the testlog file
    for x in os.listdir(json_dir):
        if "testresultlog" in x:
            logFile = json_dir + x
    try:
        f = open(logFile)
        logs = json.load(f)
    except:
        print("no logfile")
        sys.exit(55)

    jsons = {}
    for item in logs:
        if ".json" in item: jsons[item] = logs[item]

    #print(jsons)
    
    for mcs in jsons:
        print("Doing MCS {}".format(mcs))
        
        i += 1

        fileName = jsons[mcs]

        with open(fileName, "rb") as f:
            bytes = f.read()
            encoded = base64.b64encode(bytes)
            api_endpoint = ea_root + "zip2csv"
            data = {'zip':encoded}
            theResponse = requests.post(url=api_endpoint, data=data,timeout=300)
            theJson = json.loads(theResponse.text)

        # Analyze the CSV
        csv = theJson["csv"]
        api_endpoint = ea_root + "objectify"
        data = {'csv':csv}
        theResponse = requests.post(url=api_endpoint, data=data,timeout=300)
        theJson = json.loads(theResponse.text)    

        #Get basic test results information
        api_endpoint = ea_root + "getStats"
        data = {'csv':csv,'filter':'counts'}
        try:
            r = requests.post(url=api_endpoint, data=data, timeout=300)
        except requests.exceptions.RequestException as error:
            print("Error: ", error)
            sys.exit(44)

        theStats = json.loads(r.text)
        #print("Here are the stats for this data.\n{}".format(json.dumps(theStats,indent=4)))
        print("Here are the stats for this data.\n{}".format(json.dumps(theStats)))
    
        tpairs = theStats["filteredData"]["trafficPairs"]["map"]
        epoints = theStats["filteredData"]["palEndpoints"]["map"]
        #print(tpairs)

        theTarget = 0
        for entry in epoints:
            if "iperf" in epoints[entry]: theTarget = int(entry)

        print("The target endpoint to use is {}".format(theTarget))
        #The endpoint isn't really important for traffic pairs.
    
        # Analyze the CSV file
        api_endpoint = ea_root + "objectify"
        data = {'csv':csv}
        theResponse = requests.post(url=api_endpoint, data=data,timeout=300)
        theJson = json.loads(theResponse.text)

        headers = theJson["headers"]
        dataSet = theJson["dataSet"]
        if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

        api_endpoint = ea_root + "crunch"
        run = 1
        data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
        theResponse = requests.post(url=api_endpoint, data=data,timeout=300)
        theJson = json.loads(theResponse.text)
        if "error" in theJson: info("crunch: This data returned an error: {}".format(theJson["error"]))
        analyzedData = theJson["crunchedData"]
        theNotes = theJson["Notes"]
        #info(theNotes)
        #info(json.dumps(analyzedData,indent=4))

        print("The number of pal Endpoints for which you have data is {}".format(len(analyzedData)))

        numberOfPalEndpoints = len(analyzedData)
        thisData = analyzedData[0]
        _analyzedData = thisData
    
        thisAttenPlot = []
        thisRssiPlotCtrl = []
        thisRssiPlotData = []
        for thisData in _analyzedData:
            #print(thisData["throughput"]["mean"])
            if thisData["throughput"]["mean"] != None:
                thisAttenPlot.append({"x":thisData["attenuation"], "y":thisData["throughput"]["mean"]})
                thisRssiPlotCtrl.append({"x":thisData["allRssi"]["combinedControlMeanLogMean"], "y":thisData["throughput"]["mean"]})
                thisRssiPlotData.append({"x":thisData["allRssi"]["combinedDataMeanLogMean"], "y":thisData["throughput"]["mean"]})
            else:
                thisAttenPlot.append({"x":thisData["attenuation"], "y":0})            
                thisRssiPlotCtrl.append({"x":thisData["allRssi"]["combinedControlMeanLogMean"], "y":0})
                thisRssiPlotData.append({"x":thisData["allRssi"]["combinedDataMeanLogMean"], "y":0})

        #print(thisAttenPlot)
        
        thisCurve = {}
        thisCurve["label"] = mcs
        ci = i % len(colors)    
        thisCurve["color"] = colors[ci]
        thisCurve["width"] = 1
        thisCurve["data"] = thisAttenPlot  #thisTimePlot
        thisCurve["fill"] = -1

        #print(thisCurve)

        curves.append(thisCurve)
        ctrlRssiPlots.append({"label":mcs,"color":colors[ci],"width":1,"data":thisRssiPlotCtrl,"fill":-1})
        dataRssiPlots.append({"label":mcs,"color":colors[ci],"width":1,"data":thisRssiPlotData,"fill":-1})

    #....................
    #Find the maximum envelope curve.  That is, of all of the fixed MCS points, find the highest value at each attenuation.
    print("\n {} Making the maximum envelope curve... {}\n".format(cRed,cNormal))    
    attens = []
    ctrlRssis = []
    dataRssis = []
    
    for point in thisAttenPlot:   attens.append(point["x"])
    for point in thisRssiPlotCtrl:   ctrlRssis.append(point["x"])
    for point in thisRssiPlotData:   dataRssis.append(point["x"])
    '''
    #Assume that lower MCS is checked first, so use the first plot to set these X values so that you get the widest range of RSSI.  Attenuation will always be the same.
    curve = curves[0]
    for point in curve["data"]: attens.append(point["x"])
    curve = ctrlRssiPlots[0]
    for point in curve["data"]: ctrlRssis.append(point["x"])
    curve = dataRssiPlots[0]
    for point in curve["data"]: dataRssis.append(point["x"])
    '''
    
    envelopeData = []
    envelopeData2 = []
    envelopeData3 = []
    idx = 0
    for atten in attens:
        tputs = []
        for curve in curves:
            if "Adapt" not in curve["label"]:
                for point in curve["data"]:
                    if point["x"] == atten:
                        if point['y'] != None: tputs.append(point["y"])
                        break
        maxTput = max(tputs)
        envelopeData.append({"x":atten,"y":maxTput})
        envelopeData2.append({"x":ctrlRssis[idx],"y":maxTput})
        envelopeData3.append({"x":dataRssis[idx],"y":maxTput})
        idx += 1

    thisCurve = {}
    thisCurve["label"] = "Outer Envelope"
    thisCurve["color"] = "lightgrey"
    thisCurve["width"] = 20
    thisCurve["data"] = envelopeData
    thisCurve["fill"] = "origin"
    curves.append(thisCurve)

    rssiLooksGood = False
    for curve in ctrlRssiPlots:
        theData = curve["data"]
        for element in theData:
            if element["x"] != None: rssiLooksGood = True
            
    print("You have RSSI data: {}".format(rssiLooksGood))

    if rssiLooksGood:
        highestRSSI = None
        highestThroughput = None
        for curve in ctrlRssiPlots:
            if "Adapt" not in curve["label"]:
                for item in curve["data"]:
                    if highestRSSI == None: highestRSSI = item["x"]
                    if item["x"] > highestRSSI: highestRSSI = item["x"]
                    if highestThroughput == None: highestThroughput = item["y"]
                    if item["y"] > highestThroughput: highestThroughput = item["y"]
        #envelopeData2.insert(0,{"x":highestRSSI,"y":highestThroughput})
        envelopeData2[0] = {"x":highestRSSI,"y":highestThroughput}    
        ctrlRssiPlots.append({"label":"Outer Envelope", "color":"lightgrey", "width":20, "data":envelopeData2, "fill":"origin"})

        highestRSSI = None
        highestThroughput = None
        for curve in dataRssiPlots:
            if "Adapt" not in curve["label"]:
                for item in curve["data"]:
                    if highestRSSI == None: highestRSSI = item["x"]
                    if item["x"] > highestRSSI: highestRSSI = item["x"]
                    if highestThroughput == None: highestThroughput = item["y"]
                    if item["y"] > highestThroughput: highestThroughput = item["y"]
        #envelopeData3.insert(0,{"x":highestRSSI,"y":highestThroughput})
        envelopeData3[0] = {"x":highestRSSI,"y":highestThroughput}    
        dataRssiPlots.append({"label":"Outer Envelope", "color":"lightgrey", "width":20, "data":envelopeData3, "fill":"origin"})


    print("\n {} Maximum envelope curves complete. {}\n".format(cGreen,cNormal))

    #print(curves)
    
    #....................

    #Write a report
    myReport = {}
    myReport["Title"] = theTitle
    myReport["Report"] = []

    item = {
        "elementType": "section",
        "headingType": "h1",
        "headingContent": theTitle
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent": "Throughput vs. Attenuation"
    }
    myReport["Report"].append(item)
    
    item = {
    	"elementType":"plot",
	"type": "scatter",
	"title": "MCS Sweep vs. Attenuation",
	"xaxis":{"string":"Attenuation (dB)"},
	"yaxis":{"string":"Throughput (Mbps)"},
        "data": curves
    }
    myReport["Report"].append(item)

    if rssiLooksGood:
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent": "Throughput vs. Control RSSI"
        }
        myReport["Report"].append(item)

        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "MCS Sweep vs. Control RSSI",
            "xaxis":{"string":"Control RSSI (dBm)","reverse":True},
            "yaxis":{"string":"Throughput (Mbps)"},
            "data": ctrlRssiPlots
        }
        myReport["Report"].append(item)

        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent": "Throughput vs. Data RSSI"
        }
        myReport["Report"].append(item)

        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "MCS Sweep vs. Data RSSI",
            "xaxis":{"string":"Data RSSI (dBm)","reverse":True},
            "yaxis":{"string":"Throughput (Mbps)"},
            "data": dataRssiPlots
        }
        myReport["Report"].append(item)
    

    print("Report Creation Complete")
    
    #######################

    # Let's see if we can find script manager running here.  If so, put some local copies
    try:
        #Verify where scriptManager is running
        localSM = True
        api_endpoint = "http://localhost:5678/exec?command=pwd"
        r = requests.get(url=api_endpoint,timeout=300)
    except requests.exceptions.RequestException as error:
        print(">>> initializeAutotest: Unable to find a local copy of script manager.  So not going to do anything here.")
        print("initializeAutotest: Error: ", error)
        localSM = False

    #Put the JSON file somewhere if you want to be able to look at plots inside SM
    jsonPath = directory_name + theName + "_" + runNumber + ".json"
    f = open(jsonPath, "w")
    f.write(json.dumps(myReport,indent=4))
    f.close()    
    print("{} JSON report has been written to {}. {}".format(cGreen,jsonPath,cNormal))
    
    if localSM:
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        if scriptManagerLocation[len(scriptManagerLocation)-1] != "/": scriptManagerLocation += "/"        
        storageLocation = scriptManagerLocation + "/" + "storage/"
        #print("storageLocation is {}".format(storageLocation))
        fileName = theName + "_" + runNumber + ".html"
        fullPath = storageLocation + fileName
        #print("The full path for the saved file is {}".format(fullPath))

        #Generate the proper html for this report
        api_endpoint = "http://localhost:5678/jsonToHtmlReport"
        data = {'json':json.dumps(myReport,indent=4)}
        r = requests.post(url=api_endpoint,data=data,timeout=300)
        y = json.loads(r.text)
        html = y["html"]
        print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))

        #Write out this html file
        f = open(fullPath, "w")
        f.write(html)
        f.close()    
        print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

        #Create a JSON file that will put a link to the previous file into script manager.
        jsonPlot = {}
        jsonPlot["reportLink"] = {
            "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
            "label": "Report for " + theName,
            "withTitle": theTitle            
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'TestReportLocal.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

    return myReport


#===
#Use this for debugging.  Otherwise, comment it out.
'''
print("This is the debugging section of createReport for McsSweep.  Comment it out if you don't expect to see it.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2025-02-06_10-34_calix/1_2025-02-06_10-34_McsSweep/"
ea_root = "http://localhost:8080/"
analyze(directory_name,json_dir,ea_root)
'''

