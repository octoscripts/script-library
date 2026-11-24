import sys
import json
import os
import requests
import base64
from pathlib import Path
from datetime import datetime

#######################################################################
def info(text,another=None):
    now = datetime.now()
    if(another==None):
        print("[INFO]: " +"{"+str(now)+"}; "+ text)
    else:
        print("[INFO]: " +"{"+str(now)+"}; "+ text + " , " + str(another))
#######################################################################

def analyze(directory_name,json_file,ea_root):

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
        theTitle = "KafkaExample"
        theName = theTitle.replace(" ","_")
        runNumber = "0"

    #print("Command line part is " + CL)

    #Do the whole analysis part using the data in this zip file.
    fileName = json_file

    print('>>> createReport_main Using file %s.', fileName)

    with open(fileName, "rb") as f:
        bytes = f.read()
        encoded = base64.b64encode(bytes)
        #info(encoded)
        api_endpoint = ea_root + "zip2csv"
        data = {'zip':encoded}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        #info(theJson)

    csv = theJson["csv"]

    #Get basic test results information
    #api_endpoint = "http://localhost:8080/getStats"
    api_endpoint = ea_root + "getStats"
    data = {'csv':csv,'filter':'counts'}
    try:
        r = requests.post(url=api_endpoint, data=data, timeout=5)
    except requests.exceptions.RequestException as error:
        info("Error: ", error)
        sys.exit(44)

    y = json.loads(r.text)
    #info(json.dumps(y,indent=4))

    tpName = y["filteredData"]["trafficPairs"]["map"]["0"]
    #info(tpName)

    # Analyze the CSV file
    api_endpoint = ea_root + "objectify"
    data = {'csv':csv}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)

    headers = theJson["headers"]
    dataSet = theJson["dataSet"]
    if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

    api_endpoint = ea_root + "crunch"
    run = 1
    data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    if "error" in theJson: info("crunch: This data returned an error: {}".format(theJson["error"]))
    analyzedData = theJson["crunchedData"]
    theNotes = theJson["Notes"]
    #info(theNotes)
    #info(json.dumps(analyzedData,indent=4))

    #info("The number of pal Endpoints for which you have data is {}".format(len(analyzedData)))

    numberOfPalEndpoints = len(analyzedData)
    thisData = analyzedData[0]
    _analyzedData = thisData

    theThroughput = _analyzedData[0]["throughput"]["mean"]
    theRSSI = _analyzedData[0]["allRssi"]["combinedDataMeanMode"]

    #print(theThroughput)
    txRate = _analyzedData[0]["allRates"]["txRateModeMode"]
    txMCS = _analyzedData[0]["allMcs"]["txMcsModeMode"]
    txBW = _analyzedData[0]["allBW"]["txBwModeMode"]
    txStreams = _analyzedData[0]["allNss"]["txNssModeMode"]
    rxRate = _analyzedData[0]["allRates"]["rxRateModeMode"]
    rxMCS = _analyzedData[0]["allMcs"]["rxMcsModeMode"]
    rxBW = _analyzedData[0]["allBW"]["rxBwModeMode"]
    rxStreams = _analyzedData[0]["allNss"]["rxNssModeMode"]

    theReturn = {
        "throughput": theThroughput,
        "rssi": theRSSI,
        "rate": {"tx":txRate, "rx":rxRate},
        "mcs" : {"tx":txMCS, "rx":rxMCS},
        "bw"  : {"tx":txBW, "rx":rxBW},
        "nss" : {"tx":txStreams, "rx":rxStreams}
    }

    return theReturn

def summarize(directory_name,json_dir,ea_root):

    sys.path.append(directory_name + '../')
    import sd2Utils
    
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
        theTitle = "KafkaExample"
        theName = theTitle.replace(" ","_")
        runNumber = "0"

    if directory_name[len(directory_name)-1] != "/": directory_name += "/"
    if json_dir[len(json_dir)-1] != "/": json_dir += "/"
    info('>>> createReport_main json_dir', json_dir)

    #Find the testlog file
    for x in os.listdir(json_dir):
        if "testresultlog" in x and "~" not in x:
            #print (x)
            logFile = json_dir + x
            print(logFile)
    try:
        f = open(logFile)
        logs = json.load(f)
    except:
        print("no logfile")
        sys.exit(55)

    #print(logs)
    theData = logs["perAttenData"]
    theConfiguration = logs["configuration"]

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
        "headingContent": "Path to data",
        "text": json_dir
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "vspace",
        "size": "30px",
    }
    myReport["Report"].append(item)

    item = {"elementType":"text", "text":"Date of analysis: {}".format(datetime.now())}
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Graphs of results"
    }
    myReport["Report"].append(item)

    #First simple plot, rate vs. attenuation.
    xyPlot = []
    for atten in theData:
        xyPlot.append({"x":atten,"y":theData[atten]["throughput"]})

    allData = []
    allData.append( {"label":"Rate vs. attenuation","color":"black","width":1,"radius":2,"data":xyPlot,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Throughput vs. Attenuation",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"Attenuation (dB)"},
        "yaxis":{"string":"Throughput (Mbps)","min":0},
        "tableWidth":"800px",
        "showTable": True,
        "tableStyle": {"font-size":"14px"},
        #"yaxisNames":[
        #    {"name":"left","location":"left","label":"Throughput (Mbps)","grid":True},
        #    {"name":"right","location":"right","label":"RSSI (dBm)","grid":False}
        #],            
        "data": allData
    }
    myReport["Report"].append(item)

    #First thing that stardust cannot do.  MCS vs. attenuation.
    xyPlotTx = []
    xyPlotRx = []
    for atten in theData:
        xyPlotTx.append({"x":atten,"y":theData[atten]["mcs"]["tx"]})
        xyPlotRx.append({"x":atten,"y":theData[atten]["mcs"]["rx"]})

    allData = []
    allData.append( {"label":"Tx MCS vs. attenuation","color":"red","width":1,"radius":2,"data":xyPlotTx,"fill":False,"style":"solid"} )
    allData.append( {"label":"Rx MCS vs. attenuation","color":"blue","width":1,"radius":2,"data":xyPlotRx,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "MCS vs. Attenuation",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"Attenuation (dB)"},
        "yaxis":{"string":"MCS value","min":0},
        "tableWidth":"800px",
        "showTable": False,
        "tableStyle": {"font-size":"14px"},
        #"yaxisNames":[
        #    {"name":"left","location":"left","label":"Throughput (Mbps)","grid":True},
        #    {"name":"right","location":"right","label":"RSSI (dBm)","grid":False}
        #],            
        "data": allData
    }
    myReport["Report"].append(item)

    #Something more analytical that stardust definitely cannot do.  Rate vs DISTANCE.
    xyPlot = []
    TxPower = 25 #dBm.  Let's just say.
    bpM = 1 #Breakpoint pathloss in meters
    bpExp = 3.5 #Breakpoint exponent compared to 2 which would be free space.
    freq = float( theConfiguration["band"].replace("g","") )
    for atten in theData:
        theRSSI = theData[atten]["rssi"]
        theLoss = TxPower - theRSSI
        #Convert to distance using a breakpoint path loss model
        theDistance = sd2Utils.BPPL2m(freq,theLoss,bpM,bpExp)
        xyPlot.append({"x":theDistance,"y":theData[atten]["throughput"]})

    allData = []
    allData.append( {"label":"Rate vs. distance","color":"black","width":1,"radius":2,"data":xyPlot,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Throughput vs. Distance, Breakpoint path loss model with 1 meter breakpoint, and exponent of 3.5",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"Distance (meters)"},
        "yaxis":{"string":"Throughput (Mbps)","min":0},
        "tableWidth":"800px",
        "showTable": True,
        "tableStyle": {"font-size":"14px"},
        #"yaxisNames":[
        #    {"name":"left","location":"left","label":"Throughput (Mbps)","grid":True},
        #    {"name":"right","location":"right","label":"RSSI (dBm)","grid":False}
        #],            
        "data": allData
    }
    myReport["Report"].append(item)

    #Now something really crazy.  Let's look at all of the data and do scatter plots of Bytes vs. Throughput for all of them.
    theZips = []
    for x in os.listdir(json_dir):
        if ".zip" in x and "CSV" not in x:
            #print (x)
            theZips.append(json_dir + x)
            #print(theZips)

    allData = []
    idx = 3
    for fileName in theZips:
        idx += 1
        with open(fileName, "rb") as f:
            bytes = f.read()
            encoded = base64.b64encode(bytes)
            api_endpoint = ea_root + "zip2csv"
            data = {'zip':encoded}
            theResponse = requests.post(url=api_endpoint, data=data)
            theJson = json.loads(theResponse.text)

        csv = theJson["csv"]

        #Get basic test results information
        api_endpoint = ea_root + "getStats"
        data = {'csv':csv,'filter':'counts'}
        try:
            r = requests.post(url=api_endpoint, data=data, timeout=25)
        except requests.exceptions.RequestException as error:
            info("Error: ", error)
            sys.exit(44)            
        y = json.loads(r.text)
        tpName = y["filteredData"]["trafficPairs"]["map"]["0"]
        epName = y["filteredData"]["palEndpoints"]["map"]["0"]
        ppName = None
        if y["filteredData"]["pingPairs"]["length"] > 0:
            ppName = y["filteredData"]["pingPairs"]["map"]["0"]
        #print("EP: {}, TP: {}, PP: {}".format(epName,tpName,ppName))

        # Analyze the CSV file
        api_endpoint = ea_root + "objectify"
        data = {'csv':csv}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)

        headers = theJson["headers"]
        dataSet = theJson["dataSet"]
        if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

        xyPlot = []
        for thisData in dataSet:
            thisThroughput = thisData[tpName + " Throughput [Mbps]"]
            thisBytes = thisData[tpName + " Bytes"]
            if "N/A" in thisThroughput or "N/A" in thisBytes: continue
            xyPlot.append({"x":thisBytes,"y":thisThroughput})
        allData.append( {"label":fileName,"color":colors[idx % len(colors)],"width":0,"radius":5,"data":xyPlot,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Throughput vs. Bytes",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"Bytes"},
        "yaxis":{"string":"Throughput (Mbps)"},
        "tableWidth":"800px",
        "showTable": False,
        "tableStyle": {"font-size":"14px"},
        #"yaxisNames":[
        #    {"name":"left","location":"left","label":"Throughput (Mbps)","grid":True},
        #    {"name":"right","location":"right","label":"RSSI (dBm)","grid":False}
        #],            
        "data": allData
    }
    myReport["Report"].append(item)


    '''
    #Play with a box and whisker plot
    allData = []
    labels = []
    idx = 3
    for fileName in theZips:
        idx += 1
        with open(fileName, "rb") as f:
            bytes = f.read()
            encoded = base64.b64encode(bytes)
            api_endpoint = ea_root + "zip2csv"
            data = {'zip':encoded}
            theResponse = requests.post(url=api_endpoint, data=data)
            theJson = json.loads(theResponse.text)

        csv = theJson["csv"]

        api_endpoint = ea_root + "getStats"
        data = {'csv':csv,'filter':'throughput','trafficPair':0}
        try:
            r = requests.post(url=api_endpoint, data=data, timeout=25)
        except requests.exceptions.RequestException as error:
            info("Error: ", error)
            sys.exit(44)            
        y = json.loads(r.text)
        #print(y)
        theThroughput = y[0]["filteredData"]["raw"]
        theAttenuation = y[0]["attenuation"]["attenuation"]
        #print("For file {}, at {}, the raw throughput data is {}".format(fileName, theAttenuation,theThroughput))
        split = fileName.split("/")
        file = split[len(split)-1]
        atten = file.replace("KafkaExample_","").replace("dB.zip","")
        labels.append(atten)
        print(atten)
        print(colors[idx % len(colors)])
        print(theThroughput)
        allData.append({"label":atten,"color":colors[idx % len(colors)],"width":1,"padding":10,"data":theThroughput})
        
    item = {
        "elementType": "plot",
        "type": "boxplot",
        "labels": labels,
        "title": "Throughput vs. Attenuation",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"Attenuation (dB)"},
        "yaxis":{"string":"Throughput (Mbps)"},
        "tableWidth":"800px",
        "showTable": False,
        "tableStyle": {"font-size":"14px"},
        "data": allData
    }
    myReport["Report"].append(item)
    '''

    #First thing that stardust cannot do.  BW vs. RSSI
    xyPlotTx = []
    xyPlotRx = []
    for atten in theData:
        xyPlotTx.append({"x":theData[atten]["rssi"],"y":theData[atten]["bw"]["tx"]})
        xyPlotRx.append({"x":theData[atten]["rssi"],"y":theData[atten]["bw"]["rx"]})

    allData = []
    allData.append( {"label":"Tx BW vs. Rssi","color":"red","width":1,"radius":2,"data":xyPlotTx,"fill":False,"style":"solid"} )
    allData.append( {"label":"Rx BW vs. Rssi","color":"blue","width":1,"radius":2,"data":xyPlotRx,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "BW vs. RSSI",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"RSSI (dBm)"},
        "yaxis":{"string":"BW [MHz]","min":0},
        "tableWidth":"800px",
        "showTable": False,
        "tableStyle": {"font-size":"14px"},
        #"yaxisNames":[
        #    {"name":"left","location":"left","label":"Throughput (Mbps)","grid":True},
        #    {"name":"right","location":"right","label":"RSSI (dBm)","grid":False}
        #],            
        "data": allData
    }
    myReport["Report"].append(item)

    #RSSI vs. Attenuation
    staRSSI = []
    dutRSSI = []
    for atten in theData:
        try:
            staRSSI.append({"x":atten,"y":theData[atten]["rssi"]})
            dutRSSI.append({"x":atten,"y":theData[atten]["aveDutRssi"]})
        except:
            continue

    allData = []
    allData.append( {"label":"Pal Rssi","color":"red","width":1,"radius":2,"data":staRSSI,"fill":False,"style":"solid"} )
    allData.append( {"label":"DUT Rssi","color":"blue","width":1,"radius":2,"data":dutRSSI,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "RSSI from both ends",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"Attenuation (dB)"},
        "yaxis":{"string":"RSSI (dBm)"},
        "tableWidth":"800px",
        "showTable": False,
        "tableStyle": {"font-size":"14px"},
        "data": allData
    }
    myReport["Report"].append(item)

    #Throughput vs. DUT RSSI
    xyPlot = []
    for atten in theData:
        try:
            dutRSSI = theData[atten]["aveDutRssi"]
            xyPlot.append({"x":dutRSSI,"y":theData[atten]["throughput"]})
        except:
            continue

    allData = []
    allData.append( {"label":"Rate vs. distance","color":"black","width":1,"radius":2,"data":xyPlot,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Throughput vs. DUT RSSI",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"DUT RSSI (dBm)","reverse":True},
        "yaxis":{"string":"Throughput (Mbps)","min":0},
        "tableWidth":"800px",
        "showTable": False,
        "tableStyle": {"font-size":"14px"},
        "data": allData
    }
    myReport["Report"].append(item)
    
    #######################

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

        #Store the JSON formatted plot, and put a link to it in ReportList.json.
        jsonName = theName + ".json"
        plotPath = storageLocation + jsonName
        f = open(plotPath, "w")
        f.write(json.dumps(myReport,indent=3))
        f.close()

        #Put one in the script folder, too, in case you want to read it (more easily) using script manager in the display.
        f = open(directory_name+jsonName, "w")
        f.write(json.dumps(myReport,indent=3))
        f.close()

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

'''
#DEBUG lines
print("This is the debug section of createReport for KafkaExample.  Comment it out if you don't expect to see it.")
directory_name = "./"
ea_root = "http://localhost:8080/"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-05_15-18_calix/1_2026-10-05_15-18_KafkaExample/"
json_file = json_dir + "KafkaExample_0.0dB.zip"

#theData = analyze(directory_name,json_file,ea_root)
#print(theData)

theData = summarize(directory_name,json_dir,ea_root)
#print(theData)
'''
