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

    print ("throughput " + str(round(throughputMean,1)) + " ping " + str(round(pingAverage,1)) )

    #Get some iperf2 histogram information for testing
    tPairName = construct["trafficPairs"]["map"]["0"]
    binHeader = tPairName + " histogram_bins"
    countHeader = tPairName + " histogram_counts"
    bins = []
    counts = []
    for data in dataSet:
        Bins = unquote(data[binHeader])
        Counts = unquote(data[countHeader])
        if Bins == "#N/A":continue
        if Counts == "#N/A":continue
        bins = Bins.split(",")
        counts = Counts.split(",")
        for i in range(0,len(bins)): bins[i] = int(bins[i])
        for i in range(0,len(counts)): counts[i] = int(counts[i])
        
    #print(bins)
    #print(counts)
    LastHist = {"bins":bins, "counts":counts}
    #print(LastHist)

    CombinedHist = None
    if "histInfo" in analyzedDataPair1Atten1:
        #print(analyzedDataPair1Atten1["histInfo"][tpName]["perAttenuation"])
        bins = []
        counts = []
        if tpName in analyzedDataPair1Atten1["histInfo"]:
            for key in analyzedDataPair1Atten1["histInfo"][tpName]["perAttenuation"]:
                bins.append( int(key) )
                counts.append (int(analyzedDataPair1Atten1["histInfo"][tpName]["perAttenuation"][key]) )
            CombinedHist = {"bins":bins, "counts":counts}
        #print(CombinedHist)

    useHist = LastHist
    if CombinedHist != None: useHist = CombinedHist
    return {"throughput":round(throughputMean,1), "ping":round(pingAverage,1), "LatencyHist":useHist}

#-------------------------------------------------------------------------------------------------------------------------
def plot(directory_name,json_dir,useIperfHistograms):

    # Set up some text coloring
    cRed=   '\033[33m'
    cGreen= '\033[32m'
    cNormal='\033[m'

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
    
    #Pull delayVsRate out of the log file.
    delayVsRate = testResultLogJson["delayVsRate"]
    
    allPlots = []
    colors = ["red","blue","green","orange","black","grey","purple"]

    thisPlot = {}
    thisPlot["type"] = "scatter"
    thisPlot["title"] = "Ping latency vs. Throughput"
    thisPlot["xaxis"] = {"string":"Throughput (Mbps)"}
    thisPlot["yaxis"] = {"string": "Ping Latency (msec)"}
    dataArray = []
    data = []
    maxLatency = 0    
    for key in delayVsRate:
        offered = key
        measured = delayVsRate[key]["throughput"]
        latency = delayVsRate[key]["ping"]
        data.append({"x":measured, "y":latency})
        maxLatency = max(maxLatency,latency)
    thisSet = {}
    thisSet["label"] = ""
    colorId = 0 % len(colors)
    thisSet["color"] = colors[colorId]
    thisSet["width"] = 1
    thisSet["data"] = data
    thisSet["fill"] = -1
    thisSet["style"] = "solid"
    dataArray.append(thisSet)
    thisPlot["data"] = dataArray

    allPlots.append(thisPlot)

    #-------------------------------------
    jsonFile = {}
    jsonFile["Plots"] = allPlots

    with open(directory_name + 'jsonPlots.json', 'w') as outfile:
        json.dump(jsonFile, outfile, indent=4)

    print("Plots are available in " + directory_name + 'jsonPlots.json')
        
    #print("The number of traffic pairs for which you have data is {}".format(len(analyzedData)))

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
        "headingContent":"Overview",
        "text": testResultLogJson["testInfo"]["description"]
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"Test configuration",
    }
    myReport["Report"].append(item)

    html = "<ul>"
    html +="<li>" + "Band = " + testResultLogJson["testInfo"]["band"] + "</li>"
    html +="<li>" + "Channel = " + str(testResultLogJson["testInfo"]["primaryChannel"]) + "<lil>"
    html +="<li>" + "Bandwidth = " + testResultLogJson["testInfo"]["bandwidth"] + "</li>"
    html +="<li>" + "Streams = " + str(testResultLogJson["testInfo"]["streams"]) + "</li>"
    html +="<li>" + "Direction = " + testResultLogJson["testInfo"]["upOrDown"] + "</li>"
    html += "</ul>"
    item = {
        "elementType": "text",
        "text": html
    }
    myReport["Report"].append(item)
    
    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"Plot to test for buffer bloat",
        "text": "If the plot rises significantly with traffic, the buffers may be bloated."
    }
    myReport["Report"].append(item)
    item = json.loads(json.dumps(allPlots[0]))
    item["elementType"] = "plot"
    myReport["Report"].append(item)

    if maxLatency < 50: resultText = "Since the average latency is not above 50 msec ({} msec), this buffer is not considered bloated.".format(maxLatency)
    else: resultText = "Since the average latency is above 50 msec ({} msec), this buffer is considered bloated.".format(maxLatency)
    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Result",
        "text": resultText
    }
    myReport["Report"].append(item)

    if useIperfHistograms:
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"iPerf2 Histograms",
            "text": "The last valid histogram captured for each throughput."
        }
        myReport["Report"].append(item)

        histInfo = testResultLogJson["histInfo"]
        binWidth = histInfo["binWidth"]
        binWidth = int(binWidth)

        array95CI = []

        for key in delayVsRate:
            offered = key
            bins = delayVsRate[key]["LatencyHist"]["bins"]
            counts = delayVsRate[key]["LatencyHist"]["counts"]
            if len(bins)<1: continue
            item = {
                "elementType": "section",
                "headingType": "h3",
                "headingContent":"Rate: " + offered
            }
            myReport["Report"].append(item)

            data = []
            for i in range(0,len(bins)): data.append({"x":binWidth*bins[i]/1000, "y":counts[i]})
            thisPlot = {}
            thisPlot["elementType"] = "plot"
            thisPlot["type"] = "scatter"
            thisPlot["title"] = "Latency Histogram for rate: " + offered
            thisPlot["xaxis"] = {"string":"Latency (msec)"}
            thisPlot["yaxis"] = {"string": "Counts"}
            thisPlot["showTable"] = False
            dataArray = []
            thisSet["label"] = "Latency histogram for rate " + offered
            colorId = 0 % len(colors)
            thisSet["color"] = colors[colorId]
            thisSet["width"] = 1
            thisSet["data"] = data
            thisSet["fill"] = -1
            thisSet["style"] = "solid"
            dataArray.append(thisSet)
            thisPlot["data"] = dataArray
            myReport["Report"].append(json.loads(json.dumps(thisPlot)))

            totalCounts = 0
            for count in counts: totalCounts += count
            CIcount = 0.95*totalCounts
            currentCount = 0
            for i in range (0,len(counts)):
                currentCount += counts[i]
                if currentCount > CIcount: break
            array95CI.append( {"load":int(offered.replace("M","")), "value":binWidth*int(bins[i])/1000} )

        #print(array95CI)
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"Plot of 95% iPerf2 histogram values"
        }
        myReport["Report"].append(item)

        data = []
        for item in array95CI: data.append({"x":item["load"], "y":item["value"]})
        thisPlot = {}
        thisPlot["elementType"] = "plot"
        thisPlot["type"] = "scatter"
        thisPlot["title"] = "95% confidence interval from iPerf2 histograms"
        thisPlot["xaxis"] = {"string":"Offered load (Mbps)"}
        thisPlot["yaxis"] = {"string": "95% confidence interval latency value (msec)"}
        thisPlot["showTable"] = True
        dataArray = []
        thisSet["label"] = ""
        colorId = 0 % len(colors)
        thisSet["color"] = colors[colorId]
        thisSet["width"] = 1
        thisSet["data"] = data
        thisSet["fill"] = -1
        thisSet["style"] = "solid"
        dataArray.append(thisSet)
        thisPlot["data"] = dataArray
        myReport["Report"].append(json.loads(json.dumps(thisPlot)))
    
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
json_path = "/home/octoscope/Documents/script-home/results/2023-03-15_18-24_netgear_mk63/1_2023-03-15_18-24_BufferBloat/2023-03-15_18-29_netgear_mk63_V1.0.6.116_2.0.54_BufferBloat.zip"
json_dir =  "/home/octoscope/Documents/script-home/results/2023-03-16_08-45_netgear_mk63/1_2023-03-16_08-45_BufferBloat/"
ea_root = "http://localhost:8080/"

#extract(json_path,ea_root)
plot("./",json_dir)
'''
