import os
import sys
import json
import requests
import time
import datetime
import base64
from urllib.parse import unquote

def extract(json_path,ea_root):
    
    with open(json_path, "rb") as f:
        bytes = f.read()
        encoded = base64.b64encode(bytes)
        api_endpoint = ea_root + "zip2csv"
        data = {'zip':encoded}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        #print(theJson)

    csv = theJson["csv"]

    #Get basic test results information
    api_endpoint = ea_root + "getStats"
    data = {
        'csv':csv,
        'filter':'counts'
        }

    try:
        r = requests.post(url=api_endpoint, data=data, timeout=5)
    except requests.exceptions.RequestException as error:
        print("Error: ", error)
        sys.exit(44)

    y = json.loads(r.text)
    #print(y)
    construct = y["filteredData"]
    if construct["trafficPairs"]["length"] == 1 and construct["pingPairs"]["length"] == 1:
        #print("Good construct")
        True
    else:
        print("You need 1 traffic pair and 1 ping pair,but you have {} traffic pairs and {} ping pairs.".format(construct["trafficPairs"]["length"],construct["pingPairs"]["length"]))
        sys.exit(55)

    tpName = y["filteredData"]["trafficPairs"]["map"]["0"]
    
    # Analyze the CSV
    api_endpoint = ea_root + "objectify"
    data = {'csv':csv}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)

    headers = theJson["headers"]
    dataSet = theJson["dataSet"]
    if "error" in theJson:
        print("objectify: This data returned an error: {}".format(theJson["error"]))
        sys.exit(77)

    api_endpoint = ea_root + "crunch"
    run = 1
    data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    if "error" in theJson:
        print("crunch: This data returned an error: {}".format(theJson["error"]))
        sys.exit(88)

    analyzedData = theJson["crunchedData"]
    theNotes = theJson["Notes"]

    analyzedDataPair1 = analyzedData[0]
    analyzedDataPair1Atten1 = analyzedDataPair1[0]
    throughputMean = analyzedDataPair1Atten1["tpairData"][0]["throughput"]["mean"]
    if not throughputMean: throughputMean = 0
    #print(throughputMean)
    pingAverage = analyzedDataPair1Atten1["ppairData"][0]["pingLatency"]["mean"]
    #print(pingAverage)

    #print ("throughput " + str(round(throughputMean,1)) + " ping " + str(round(pingAverage,1)) )

    #Get some iperf2 histogram information for testing
    tPairName = construct["trafficPairs"]["map"]["0"]
    pPairName = construct["pingPairs"]["map"]["0"]
    binHeader = tPairName + " histogram_bins"
    countHeader = tPairName + " histogram_counts"
    intervalHeader = tPairName + " histogram_intervals"
    percentileHeader = tPairName + " histogram_percentiles"
    bins = []
    counts = []
    intervals = []
    percentiles = []
    obl = []
    obu = []
    outliers = []
    allHistograms = []
    for data in dataSet:
        Bins = unquote(data[binHeader])
        Counts = unquote(data[countHeader])
        Intervals = unquote(data[intervalHeader])
        Percentiles = unquote(data[percentileHeader])
        if Bins == "#N/A":continue
        if Counts == "#N/A":continue
        bins = Bins.split(",")
        counts = Counts.split(",")
        for i in range(0,len(bins)): bins[i] = int(bins[i])
        for i in range(0,len(counts)): counts[i] = int(counts[i])

        intervals = Intervals.split(",")
        percentiles = Percentiles.split(",")
        for i in range(0,len(intervals)): intervals[i] = int(intervals[i])
        for i in range(0,len(percentiles)): percentiles[i] = float(percentiles[i])

        binWidth_us = data[tPairName + " histogram_binWidth_us"]
        obl = data[tPairName + " histogram_obl"]
        obu = data[tPairName + " histogram_obu"]
        outliers = data[tPairName + " histogram_outliers"]
        latency = {}
        latency["min"] = data[tPairName + " iPerf2 Latency Min [ms]"]
        latency["max"] = data[tPairName + " iPerf2 Latency Max [ms]"]
        latency["mean"] = data[tPairName + " iPerf2 Latency Mean [ms]"]
        pingAve = data[pPairName + " Ping Latency (ms)"]

        allHistograms.append({"time": data["Time [ms]"], "bins":bins, "counts":counts, "percentiles":percentiles, "intervals":intervals, "binWidth_us":binWidth_us, "obl":obl, "obu":obu, "outliers":outliers, "iperf2OWD":latency, "pingAve":pingAve})
        
    #print(bins)
    #print(counts)
    #print(allHistograms)

    return {"throughput":round(throughputMean,1), "ping":round(pingAverage,1), "LatencyHists":allHistograms}

#-------------------------------------------------------------------------------------------------------------------------
def plot(directory_name,json_dir):

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
        theTitle = directoriesJson["title"]
        theName = theTitle.replace(" ","_")
    except:
        theTitle = "Path Loss Calibration"
        theName = theTitle.replace(" ","_")
        runNumber = "0"

    if json_dir[len(json_dir)-1] != "/": json_dir += "/"
    print('>>> createReport_createReport json_dir', json_dir)

    #For this test, pull the JSON information created.
    for x in os.listdir(json_dir):
        #print (x)
        if "testresultlog" in x:
            jsonFile = json_dir + x

    f = open(jsonFile)
    testResultLogJson = json.load(f)
    f.close

    #Write a report
    myReport = {}
    myReport["Title"] = theTitle
    myReport["Report"] = []
    
    item = {
        "elementType": "section",
        "headingType": "h1",
        "headingContent":"iPerf2 Histograms"
    }
    myReport["Report"].append(item)

    histInfo = testResultLogJson["histInfo"]
    binWidth = histInfo["binWidth"]
    binWidth = int(binWidth)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Latency histograms",
        "text": "For each second in the capture, the latency histogram in msec."
    }
    myReport["Report"].append(item)        

    LatencyHists = testResultLogJson["LatencyHists"]
    LatencyPlots = []

    #Convert the histogram data into time units:
    for hist in LatencyHists:
        thisPlot = []
        for i in range(0,len(hist["bins"])):
            thisPlot.append({"x":hist["bins"][i]*binWidth/1000, "y":hist["counts"][i]})
        LatencyPlots.append({"Time":hist["time"], "plot":thisPlot})

    allData = []
    idx = 0
    for plot in LatencyPlots:
        allData.append({
            "label": "Time = {}".format(int(plot["Time"])/1000),
            "color": colors[idx % len(colors)],
            "width": 1,
            "data": plot["plot"],
            "fill": -1,
            "style": "solid"
        })
        idx += 1
    #print(json.dumps(allData,indent=3))

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "All iperf2 latency histograms",
        "xaxis": {"string": "Latency (msec)"},
        "yaxis": {"string": "Counts"},
        "tableStyle": {"font-size":"8px"},
        "data": allData
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Pre-defined latency thresholds",
        "text": "The % confidence level for each latency histogram in this interval."
    }
    myReport["Report"].append(item)
    
    percentiles = {}
    for hist in LatencyHists:
        tp = hist["percentiles"]
        ti = hist["intervals"]
        time = int (hist["time"])
        for x in range(0,len(tp)):
            if tp[x] not in percentiles: percentiles[tp[x]] = [{"x":time, "y":ti[x]*binWidth/1000}]
            else: percentiles[tp[x]].append({"x":time, "y":ti[x]*binWidth/1000} )

    #print(percentiles)
    allData = []
    idx = 0
    for plot in percentiles:
        allData.append({
            "label": "{}% latency".format(plot),
            "color": colors[idx % len(colors)],
            "width": 1,
            "data": percentiles[plot],
            "fill": -1,
            "style": "solid"
        })
        idx += 1
    #print(json.dumps(allData,indent=3))
    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Pre-calculated percentages",
        "xaxis": {"string": "Time (msec)"},
        "yaxis": {"string": "Latency (msec)"},
        "tableStyle": {"font-size":"10px"},
        "data": allData
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Edge Events",
        "text": "Edge events are packets that fall in the 5% and 95% of confidence interval, the outliers, and the out of bound lower (obl) and out of bound upper (obu) packets."
    }
    myReport["Report"].append(item)    

    outs = {"obl":[], "obu":[], "outliers":[]}
    for hist in LatencyHists:
        outs["obl"].append({"x": int(hist["time"]), "y":hist["obl"]})
        outs["obu"].append({"x": int(hist["time"]), "y":hist["obu"]})
        outs["outliers"].append({"x": int(hist["time"]), "y":hist["outliers"]})

    #print(outs)
    allData = []
    idx = 0
    for plot in outs:
        yid = "right"
        if plot == "outliers": yid="left"
        allData.append({
            "label": "{}".format(plot),
            "color": colors[idx % len(colors)],
            "width": 1,
            "data": outs[plot],
            "fill": -1,
            "style": "solid",
            "yAxisID": yid
        })
        idx += 1
    #print(json.dumps(allData,indent=3))
    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Edge events",
        "xaxis": {"string": "Time (msec)"},
        "yaxis": {"string": "Counts"},
	"yaxisNames":[
	    {"name":"left","location":"left","label":"Outlier (counts)","grid":True},
	    {"name":"right","location":"right","label":"OBU/OBL (counts)","grid":False}
	],
        "tableStyle": {"font-size":"10px"},
        "data": allData
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"iPerf latency",
        "text": "The latency reported by iPerf.  Not the histograms, just the single latency number."
    }
    myReport["Report"].append(item)    
    
    iperf = {"min":[], "mean":[], "max":[]}
    for hist in LatencyHists:
        iperf["min"].append({"x": int(hist["time"]), "y":hist["iperf2OWD"]["min"]})
        iperf["mean"].append({"x": int(hist["time"]), "y":hist["iperf2OWD"]["mean"]})
        iperf["max"].append({"x": int(hist["time"]), "y":hist["iperf2OWD"]["max"]})

    #print(iperf)
    allData = []
    idx = 0
    for plot in iperf:
        allData.append({
            "label": "iperf2 OWD, {}".format(plot),
            "color": colors[idx % len(colors)],
            "width": 1,
            "data": iperf[plot],
            "fill": -1,
            "style": "solid"
        })
        idx += 1
    #print(json.dumps(allData,indent=3))
    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "iPerf2 One-Way-Delay",
        "xaxis": {"string": "Time (msec)"},
        "yaxis": {"string": "Delay (msec)"},
        "tableStyle": {"font-size":"10px"},
        "data": allData
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Ping latency",
        "text": "The latency reported by Ping."
    }
    myReport["Report"].append(item)    

    pingData = []
    for hist in LatencyHists:
        pingData.append({"x": int(hist["time"]), "y":hist["pingAve"]})

    allData = []
    idx = 0
    allData.append({
        "label": "Ping Latency",
        "color": colors[idx % len(colors)],
        "width": 1,
        "data": pingData,
        "fill": -1,
        "style": "solid"
    })
    idx += 1
    #print(json.dumps(allData,indent=3))
    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Ping Delay",
        "xaxis": {"string": "Time (msec)"},
        "yaxis": {"string": "Delay (msec)"},
        "tableStyle": {"font-size":"10px"},
        "data": allData
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Compare latencies",
        "text": "Compare all latencies: histogram, reported, and ping."
    }
    myReport["Report"].append(item)

    allData = []
    idx = 0
    for item in percentiles[tp[0]]: item["y"] = float(item["y"])
    allData.append({
        "label": "Histogram {}% latency".format(tp[0]),
        "color": colors[idx % len(colors)],
        "width": 1,
        "data": percentiles[tp[0]],
        "fill": -1,
        "style": "solid"
    })
    idx += 1
    for item in iperf["mean"]: item["y"] = float(item["y"])
    allData.append({
        "label": "iPerf2 OWD Mean",
        "color": colors[idx % len(colors)],
        "width": 1,
        "data": iperf["mean"],
        "fill": -1,
        "style": "solid"
    })
    idx += 1
    for item in pingData:
        try: item["y"] = float(item["y"])
        except: item["y"] = -1
    allData.append({
        "label": "Ping latency",
        "color": colors[idx % len(colors)],
        "width": 1,
        "data": pingData,
        "fill": -1,
        "style": "solid"
    })
    #print(allData)
    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Latency Comparison",
        "xaxis": {"string": "Time (msec)"},
        "yaxis": {"string": "Latency (msec)"},
        "tableStyle": {"font-size":"10px"},
        "data": allData
    }
    myReport["Report"].append(item)
    

    
    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    print("{} JSON report is complete. {}".format(cGreen,cNormal))

    #Verify where scriptManager is running
    api_endpoint = "http://localhost:5678/exec?command=pwd"
    r = requests.get(url=api_endpoint)
    y = json.loads(r.text)
    scriptManagerLocation = y["stdout"]
    scriptManagerLocation = scriptManagerLocation.replace("\n","")
    storageLocation = scriptManagerLocation + "/" + "storage/"
    #print("storageLocation is {}".format(storageLocation))

    '''
    #Write out this json file
    f = open(storageLocation + "test.json", "w")
    f.write(json.dumps(myReport,indent=4))
    f.close()
    print("{} JSON report is written out to test.json as a test. {}".format(cGreen,cNormal))
    '''
    
    #Generate the proper html for this report
    api_endpoint = "http://localhost:5678/jsonToHtmlReport"
    data = {'json':json.dumps(myReport,indent=4)}
    r = requests.post(url=api_endpoint,data=data)
    y = json.loads(r.text)
    html = y["html"]    
    print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))
    
    fileName = theName + "_" + runNumber + ".html"
    fullPath = storageLocation + fileName
    #print("The full path for the saved file is {}".format(fullPath))
    
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
    f = open(directory_name+'TestReport.json', "w")
    f.write(json.dumps(jsonPlot,indent=4))
    f.close()
    
    print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

    #Write messages if you have any.  Here's an example.
    jsonMessages = {}
    alertMessage = "None"
    jsonMessages["alertMessage"] = {"val":{"_scriptMessage_":str(alertMessage)},"label":"Alerts"}
    jsonMessages["_editable"] = False
    f = open(directory_name+'TestMessages.json', "w")
    f.write(json.dumps(jsonMessages,indent=4))
    f.close()

    print("{} Test messages have been generated. {}".format(cGreen,cNormal))


#=============
'''
print("This is the debug part of createReport for the LatencyHistogramExample.  Comment it out if you don't expect to see it.")
json_path = "/home/octoscope/Documents/script-home/results/2023-08-25_22-25_asus_gtax11000/1_2023-08-25_22-25_LatencyHistogramExample/2023-08-25_22-29_asus_gtax11000_3.0.0.4.388_22525_LatencyHistogramExample.zip"
json_dir =  "/home/octoscope/Documents/script-home/results/2023-08-25_22-46_asus_gtax11000/1_2023-08-25_22-46_LatencyHistogramExample/"
ea_root = "http://localhost:8080/"

#retObj = extract(json_path,ea_root)
#print(retObj)

plot("./",json_dir)
'''
