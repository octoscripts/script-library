import sys
import json
import os
import requests
import base64
from pathlib import Path
from datetime import datetime

def analyze(directory_name,json_dir,ea_root):

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
        theTitle = "No Name Found"
        theName = theTitle.replace(" ","_")
        runNumber = "0"

    # Find the Script Manager hostname. Need this if remotely logged into SM
    if directoriesJson:
        if "scriptManagerLocation" in directoriesJson:
            hostIpAddress = directoriesJson["scriptManagerLocation"]["hostname"]
            #print('>>> hostIpAddress: ', hostIpAddress)
        else:
            hostIpAddress = 'localhost'
            message = 'Cannot find scriptManagerLocation in directories.json. Setting hostIpAddress = localhost.'
            failHandler('Mainscript',message, errCode=0)

    if json_dir[len(json_dir)-1] != "/": json_dir += "/"

    #Get all of the zip files in the json directory
    theZips = []
    for x in os.listdir(json_dir):
        if ".zip" in x:
            if "CSV" in x: continue
            if "JSON" in x: continue
            theZips.append(json_dir + x)

    #print(">>> theZips: ", theZips)

    fileName = theZips[0]

    with open(fileName, "rb") as f:
        bytes = f.read()
        encoded = base64.b64encode(bytes)
        api_endpoint = ea_root + "zip2csv"
        #print('\n>>> api_endpoint: ', api_endpoint)
        data = {'zip':encoded}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)

    csv = theJson["csv"]

    #print('\n### Running getStats')
    #Get basic test results information
    api_endpoint = ea_root + "getStats"
    data = {'csv':csv,'filter':'counts'}

    try:
        r = requests.post(url=api_endpoint, data=data, timeout=5)
    except requests.exceptions.RequestException as error:
        info("Error: ", error)
        sys.exit(44)

    y = json.loads(r.text)
    #print(y)
    nPalEndpoints = y["filteredData"]["palEndpoints"]["length"]
    nTrafficPairs = y["filteredData"]["trafficPairs"]["length"]
    nAttenuations = y["filteredData"]["attenuations"]["steps"]
    tpName = y["filteredData"]["trafficPairs"]["map"]["0"]
    #print("The traffic pair name is {}".format(tpName))

    # Analyze the CSV file
    #print('\n### Analyzing CSV file')
    api_endpoint = ea_root + "objectify"
    data = {'csv':csv}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    #print('\n>>> theJson: ', theJson)
    headers = theJson["headers"]
    dataSet = theJson["dataSet"]
    if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

    #print('\n### Running crunch')
    api_endpoint = ea_root + "crunch"
    run = 1
    data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    if "error" in theJson: info("crunch: This data returned an error: {}".format(theJson["error"]))
    analyzedData = theJson["crunchedData"]
    theNotes = theJson["Notes"]

    #Which traffic pair has data
    index = 0
    for pair in analyzedData[nPalEndpoints-1][nAttenuations-1]["tpairData"]:
        print("{},{}".format(index,pair["throughput"]["mean"]))
        if pair["throughput"]["mean"] != None:
            break
        else: index += 1

    trafficIndex = index
    meanThroughput = analyzedData[nPalEndpoints-1][nAttenuations-1]["tpairData"][trafficIndex]["throughput"]["mean"]
    #print(meanThroughput)

    retObj = {}
    retObj["meanThroughput"] = meanThroughput

    return retObj

def report(directory_name,json_dir,ea_root):
    
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
        theTitle = "Throughput Scan"
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

    testData = logs["testData"]


    myReport = {}
    myReport["Title"] = theTitle
    myReport["Report"] = []    

    print("Total tests = {}".format(len(testData)))
    protocols = []
    for test in testData:
        if test["config"]["interface"] not in protocols: protocols.append(test["config"]["interface"])
    print("Protocols tested are {}".format(protocols))
    for protocol in protocols:
        protoTests = []
        for test in testData:
            if test["config"]["interface"] == protocol: protoTests.append(test)
        print("The total number of {} tests is {}".format(protocol,len(protoTests)))
        bands = []
        for test in protoTests:
            if test["config"]["band"] not in bands: bands.append(test["config"]["band"])
        print("Bands used are {}".format(bands))
        for band in bands:
            bandTests = []
            for test in protoTests:
                if test["config"]["band"]==band: bandTests.append(test)
            print("The total number of {} tests at {} GHz is {}".format(protocol,band,len(bandTests)))
            channels = []
            BWs = []
            packetSizes = []
            directions = []
            loads = []
            for test in bandTests:
                if test["config"]["channel"] not in channels:       channels.append(test["config"]["channel"])
                if test["config"]["BW"] not in BWs:                 BWs.append(test["config"]["BW"])
                if test["config"]["packetSize"] not in packetSizes: packetSizes.append(test["config"]["packetSize"])
                if test["config"]["direction"] not in directions:   directions.append(test["config"]["direction"])
                if test["config"]["load"] not in loads:             loads.append(test["config"]["load"])
            print("Channels used are {}".format(channels))
            print("BWs used are {}".format(BWs))
            print("Packet sizes used are {}".format(packetSizes))
            print("Loads used are {}".format(loads))

            for channel in channels:
                for BW in BWs:
                    for packetSize in packetSizes:
                        for direction in directions:
                            plotTests = []
                            for test in bandTests:
                                if test["config"]["channel"]==channel and test["config"]["BW"]==BW and test["config"]["packetSize"]==packetSize and test["config"]["direction"]==direction:
                                    plotTests.append(test)
                            #print("Plotting these tests: {}".format(plotTests))
                            labels = []
                            for test in plotTests: labels.append(test["config"]["load"])
                            measured = []
                            for test in plotTests: measured.append("{:.1f}".format(test["data"]["meanThroughput"]))
                            theory = []
                            for test in plotTests: theory.append(test["config"]["theory"]["rate"])
                            offer = []
                            for test in plotTests: offer.append(test["config"]["offer"])
                            plotData = []
                            plotData.append({"type":"bar","label":"Throughput (Mbps)","color":"green","data":measured})
                            plotData.append({"type":"line","label":"Theoretical Rate (Mbps)","color":"red","data":theory})
                            plotData.append({"type":"line","label":"Offered Rate (Mbps)","color":"blue","data":offer})
                            item = {
                                "elementType":"plot",
                                "type":"bar",
                                "title":"{}, {} GHz, Channel {}, {} MHz, {} bytes, {}".format(protocol,band,channel,BW,packetSize,direction),
                                "labels": labels,
                                "showDataValues":{"show":True,"color":"black","fontSize":'20',"offset":'50'},
                                "xaxis":{"string":"Loading level in %"},
                                "yaxis":{"string":"Throughput (Mbps)"},
                                "showTable":False,
                                "data":plotData
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
print("This is the debugging section of createReport for throughputScan.  Comment it out if you don't expect to see it.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2025-04-01_15-16_calix/1_2025-04-01_15-16_throughputScan_params_short/"
ea_root = "http://localhost:8080/"

#retObj = analyze(directory_name,json_dir,ea_root)
retObj = report(directory_name,json_dir,ea_root)

print(retObj)
'''

