import sys
import json
import os
import requests
import base64
import pprint
import time
pp = pprint.PrettyPrinter(indent=4)

from pathlib import Path

def main(directory_name,json_dir,pcapFile,ea_root):

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
    haveLogFile = False
    for x in os.listdir(json_dir):
        #print (x)
        if "testresultlog" in x:
            jsonFile = json_dir + x
            haveLogFile = True

    if haveLogFile:
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


    #Write a report
    myReport = {}
    myReport["Title"] = theTitle
    myReport["Report"] = []
    
    #Use EA to find DFS packets

    parts = pcapFile.split("/")
    fileName = parts[len(parts)-1]
    pcapDir = pcapFile.replace(fileName,"")
    #for p in range(0,len(parts)-1): pcapDir += parts[p] + "/"
    
    fName = fileName
    baseURL = ea_root + "parsePCAP"
    api_endpoint = baseURL + "?fileName="+fName  + "&pcapDir="+pcapDir 
    print("Running the captured file through a PCAP analysis.  Get the packet list.")
    print("This is the API call: {}".format(api_endpoint))
    apiResponse = requests.get(api_endpoint)
    returnObject = json.loads(apiResponse.text)
    #print(returnObject)
    totalPackets = returnObject["totalPackets"]
    print("Total packets to analyze: {} ".format(totalPackets))
    item = {
	"elementType": "section",
	"headingType": "h2",
	"headingContent":"Total Packets to Analyze = {}".format(totalPackets),
	"text": ""
    }
    myReport["Report"].append(item)
    
    thePackets = returnObject["fields"]

    rowPN = []
    rowTS = []
    rowTx = []
    rowRx = []
    rowInitialChannel = []
    rowFinalChannel = []
    rowCount = []
    rowChannel = []
    rowMCS = []
    rowNSS = []
    rowBW = []
    rowGI = []
    rowRate = []
    rowRSSI = []

    found = False
    for packet in thePackets:
        if packet["csa"]["tagID"] == -1: continue

        found = True
        print("Packet Number: {}, Timestamp (sec): {}, Tx: {}, Rx: {}, Start channel: {}, End channel: {}, Count: {}, Channel: {}, MCS: {}, NSS: {}, BW: {}, GI: {}, Rate: {}, RSSI: {}"
              .format(
                  packet["packetNumber"],
                  packet["arrivalTimeSeconds"],
                  packet["transmitterAddress"],
                  packet["receiverAddress"],
                  packet["csa"]["from"],
                  packet["csa"]["to"],
                  packet["csa"]["count"],
                  packet["Channel"],
                  packet["MCS"],
                  packet["NSS"],
                  packet["BW"],
                  packet["GI"],
                  packet["dataRate"],
                  packet["RSSI"]))
        rowPN.append(packet["packetNumber"])
        rowTS.append(packet["arrivalTimeSeconds"])
        rowTx.append(packet["transmitterAddress"])
        rowRx.append(packet["receiverAddress"])
        rowInitialChannel.append(packet["csa"]["from"])
        rowFinalChannel.append(packet["csa"]["to"])
        rowCount.append(packet["csa"]["count"])
        rowChannel.append(packet["Channel"])
        rowMCS.append(packet["MCS"])
        rowNSS.append(packet["NSS"])
        rowBW.append(packet["BW"])
        rowGI.append(packet["GI"])
        rowRate.append(packet["dataRate"])
        rowRSSI.append(packet["RSSI"])

    allRows = []
    allRows.append({"label":"Packet Number","units":"","justification":"","data":rowPN,"formatting":""})
    allRows.append({"label":"Arrival time","units":"","justification":"","data":rowTS,"formatting":""})
    allRows.append({"label":"Transmitter Address","units":"","justification":"","data":rowTx,"formatting":""})
    allRows.append({"label":"Receiver Address","units":"","justification":"","data":rowRx,"formatting":""})
    allRows.append({"label":"CSA From","units":"","justification":"","data":rowInitialChannel,"formatting":""})
    allRows.append({"label":"CSA To","units":"","justification":"","data":rowFinalChannel,"formatting":""})
    allRows.append({"label":"CSA count","units":"","justification":"","data":rowCount,"formatting":""})
    allRows.append({"label":"Frequency","units":"","justification":"","data":rowChannel,"formatting":""})
    allRows.append({"label":"MCS","units":"","justification":"","data":rowMCS,"formatting":""})
    allRows.append({"label":"Streams","units":"","justification":"","data":rowNSS,"formatting":""})
    allRows.append({"label":"Bandwidth","units":"","justification":"","data":rowBW,"formatting":""})
    allRows.append({"label":"Guard Interval","units":"","justification":"","data":rowGI,"formatting":""})
    allRows.append({"label":"Data Rate","units":"","justification":"","data":rowRate,"formatting":""})
    allRows.append({"label":"RSSI","units":"","justification":"","data":rowRSSI,"formatting":""})

    if found:
        print("{}DFS Channel Switch Announcement messages found.{}".format(cGreen,cNormal))
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"DFS Channel Switch Announcement messages found.",
            "text": ""
        }
        myReport["Report"].append(item)
        item = {
            "elementType": "table",
            "type": "table",
            "title": "",
            #"tableWidth": "700px",
            "data": allRows
        }
        myReport["Report"].append(item)

    else:
        print("{}No DFS Channel Switch Announcement messages found.{}".format(cRed,cNormal))
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"No DFS Channel Switch Announcement messages found.",
            "text": ""
        }
        myReport["Report"].append(item)

    #Use the built-in DFS analysis
    baseURL = ea_root + "pcapAPI"
    api_endpoint = baseURL + "?fileName="+fName + "&pcapDir="+pcapDir 
    api_endpoint += "&action=getDFS"
    print("Running the captured file through another PCAP analysis.  Get the DFS information only.")
    print("This is the API call: {}".format(api_endpoint))
    apiResponse = requests.get(api_endpoint)
    returnObject = json.loads(apiResponse.text)
    #print(returnObject)
    action = returnObject["action"]
    result = returnObject["result"]
    print("Action taken: {} ".format(action))
    print("Result returned: {} ".format(result))

    item = {
	"elementType": "section",
	"headingType": "h2",
	"headingContent":"Use the built-in EA DFS analysis",
	"text": api_endpoint
    }
    myReport["Report"].append(item)

    if "csa" in result:
        csa = result["csa"]
        rowPN = []
        rowTag = []
        rowFrom = []
        rowTo = []
        rowCount = []
        for item in csa:
            rowPN.append(item["PN"])
            rowTag.append(item["csa"]["tagID"])
            rowFrom.append(item["csa"]["from"])
            rowTo.append(item["csa"]["to"])
            rowCount.append(item["csa"]["count"])
        allRows = []
        allRows.append({"label":"Packet Number","units":"","justification":"","data":rowPN,"formatting":""})
        allRows.append({"label":"Tag ID","units":"","justification":"","data":rowTag,"formatting":""})
        allRows.append({"label":"CSA From Channel","units":"","justification":"","data":rowFrom,"formatting":""})
        allRows.append({"label":"CSA To Channel","units":"","justification":"","data":rowTo,"formatting":""})
        allRows.append({"label":"CSA Count","units":"","justification":"","data":rowCount,"formatting":""}) 
        item = {
            "elementType": "table",
            "type": "table",
            "title": "",
            #"tableWidth": "700px",
            "data": allRows
        }
        myReport["Report"].append(item)
   


#=================================================================================================================

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

print("This is the debug section of createReport for DFS.  Comment it out if you don't expect to see it.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2024-03-12_17-03_calix/1_2024-03-12_17-03_DFS/"
pcapFileName = json_dir + "2024-03-12_17-06_calix_calix_DFS.pcap"
ea_root = "http://localhost:8080/"
main(directory_name,json_dir,pcapFileName,ea_root)

