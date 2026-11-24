import os
import sys
import json
import requests
import time
import datetime
import base64

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

    print("We have Pal data from {} endpoints.".format(len(analyzedData)))

    #Let's find out who has congestion data.
    for aD in analyzedData:
        #print(aD[0]["txPower"])
        if aD[0]["txPower"]["txMean"] == None: continue   #Means it is no an endpoint acting as an AP
        #print("Load statistics for this data set:")
        #print(aD[0]["loadStats"])
        useAD = aD[0]

    throughputMean = useAD["tpairData"][0]["throughput"]["mean"]
    if not throughputMean: throughputMean = 0
    #print(throughputMean)

    loading = {"total":round(useAD["loadStats"]["totalMean"],1), "WiFi":round(useAD["loadStats"]["WiFiMean"],1), "notMyWiFi":round(useAD["loadStats"]["notMyWiFiMean"],1), "airlink":round(useAD["loadStats"]["airlinkMean"],1)}
    

    return {"throughput":round(throughputMean,1), "load":loading}

#
#----
#

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
        CL = ""
        for i in range(2,len(splits)):CL += splits[i] + "_"
        CL = CL[0:len(CL)-1]
        theTitle = directoriesJson["title"]
        theName = theTitle.replace(" ","_")
    except:
        CL = ""
        theTitle = "Congestion"
        theName = theTitle.replace(" ","_")
        runNumber = "0"    
    
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


    congestion = logs["congestion"]
    #print(congestion)

    
    #Write a report
    myReport = {}
    myReport["Title"] = theTitle
    myReport["Report"] = []

    # HEADING
    item = {
        "elementType": "section",
        "headingType": "h1",
        "headingContent": theTitle
    }
    myReport["Report"].append(item)
    ####

    # Congestion vs. Rate plot
    data = []
    for item in congestion: data.append({"x":item["rate"],"y":item["congestion"]})
    thisCurve = {}
    thisCurve["label"] = "Congestion vs. Offered Rate"
    thisCurve["color"] = "blue"
    thisCurve["width"] = 3
    thisCurve["data"] = data
    thisCurve["fill"] = -1
    curves = []
    curves.append(thisCurve)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent": "Congestion vs. Offered Rate"
    }
    myReport["Report"].append(item)
    
    item = {
    	"elementType":"plot",
	"type": "scatter",
	"title": "Congestion vs. Offered Rate",
	"xaxis":{"string":"Offered Rate (Mbps)"},
	"yaxis":{"string":"Congestion (%)"},
        "data": curves
    }
    myReport["Report"].append(item)
    ####
    
    print("Report Creation Complete")

    # Let's see if we can find script manager running here.  If so, put some local copies
    try:
        #Verify where scriptManager is running
        localSM = True
        api_endpoint = "http://localhost:5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
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
        r = requests.post(url=api_endpoint,data=data)
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

#=============
'''
print("This is the debug part of createReport for the Congestion automation.  Comment it out if you don't expect to see it.")
json_dir =  "/home/octoscope/Documents/automationResults/2024-09-04_12-49_calix/1_2024-09-04_12-49_congestion/"
fileName = "iperf2_udp_NSS2_MCS7.zip"
json_path = json_dir + fileName
ea_root = "http://localhost:8080/"
directory_name = "./"

#retObj = extract(json_path,ea_root)
#print(retObj)

plot(directory_name,json_dir)
'''

