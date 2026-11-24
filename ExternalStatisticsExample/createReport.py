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

    #===================================================================================================
    # Per-row (per-CSV-row, i.e. "vs Time") column names for the standard metrics added below.
    #
    # MCS, NSS, data rate, and bandwidth columns are always named the same way, per Pal Endpoint:
    #     "Pal Endpoint 1 Tx MCS Mode", "Pal Endpoint 1 Rx MCS Mode", etc.
    #
    # Throughput is NOT a fixed name -- it's named after the traffic pair itself, e.g.
    #     "ServerTopalBox-L2-STApal7 Throughput [Mbps] Mean"
    # so it has to be built from the traffic pair's own name rather than hardcoded. That name is
    # already available as `tpName`, pulled from getStats() earlier in this same function.
    #===================================================================================================
    ROW_COLUMN_NAMES = {
        "throughput": "{} Throughput [Mbps]".format(tpName),
        "mcs_tx":     "Pal Endpoint 1 TX MCS Mode",
        "mcs_rx":     "Pal Endpoint 1 RX MCS Mode",
        "nss_tx":     "Pal Endpoint 1 TX Nss Mode",
        "nss_rx":     "Pal Endpoint 1 RX Nss Mode",
        "rate_tx":    "Pal Endpoint 1 TX Rate [Mbps] Mode",
        "rate_rx":    "Pal Endpoint 1 RX Rate [Mbps] Mode",
        "bw_tx":      "Pal Endpoint 1 TX Bandwidth [MHz] Mode",
        "bw_rx":      "Pal Endpoint 1 RX Bandwidth [MHz] Mode",
    }

    PalVsAtten = []
    ExtVsAtten = []
    for dataPerAtten in _analyzedData:
        theAttenuation = dataPerAtten["attenuation"]
        theThroughput = dataPerAtten["throughput"]["mean"]
        theRSSI = dataPerAtten["allRssi"]["combinedDataMeanMode"]
        theExternalRSSI = dataPerAtten["externalStatistic_RSSI"]["externalStatistic_RSSILogMean"]
        #print(theThroughput,theRSSI,theExternalRSSI)
        PalVsAtten.append({"x":theAttenuation, "y":theRSSI})
        ExtVsAtten.append({"x":theAttenuation, "y":theExternalRSSI})

    #print(theThroughput)
    txRate = _analyzedData[0]["allRates"]["txRateModeMode"]
    txMCS = _analyzedData[0]["allMcs"]["txMcsModeMode"]
    txBW = _analyzedData[0]["allBW"]["txBwModeMode"]
    txStreams = _analyzedData[0]["allNss"]["txNssModeMode"]
    rxRate = _analyzedData[0]["allRates"]["rxRateModeMode"]
    rxMCS = _analyzedData[0]["allMcs"]["rxMcsModeMode"]
    rxBW = _analyzedData[0]["allBW"]["rxBwModeMode"]
    rxStreams = _analyzedData[0]["allNss"]["rxNssModeMode"]

    PalRSSI = []
    ExternalRSSI = []
    ThroughputVsTime = []
    McsTxVsTime = []
    McsRxVsTime = []
    NssTxVsTime = []
    NssRxVsTime = []
    RateTxVsTime = []
    RateRxVsTime = []
    BwTxVsTime = []
    BwRxVsTime = []
    for data in dataSet:        
        try: thisTime = data["Time [ms]"]
        except: continue
        try: palRSSI = data["Pal Endpoint 1 Data RSSI [dBm] Mean"]
        except: palRSSI = "#N/A"
        try: externalRSSI = data["externalStatistic_RSSI"]
        except: externalRSSI = "#N/A" 
        PalRSSI.append({"x":thisTime,"y":palRSSI})
        ExternalRSSI.append({"x":thisTime,"y":externalRSSI})

        #--- The five new standard metrics (see ROW_COLUMN_NAMES note above) ---
        try: thisThroughput = data[ROW_COLUMN_NAMES["throughput"]]
        except: thisThroughput = "#N/A"
        ThroughputVsTime.append({"x":thisTime,"y":thisThroughput})

        try: thisMcsTx = data[ROW_COLUMN_NAMES["mcs_tx"]]
        except: thisMcsTx = "#N/A"
        McsTxVsTime.append({"x":thisTime,"y":thisMcsTx})

        try: thisMcsRx = data[ROW_COLUMN_NAMES["mcs_rx"]]
        except: thisMcsRx = "#N/A"
        McsRxVsTime.append({"x":thisTime,"y":thisMcsRx})

        try: thisNssTx = data[ROW_COLUMN_NAMES["nss_tx"]]
        except: thisNssTx = "#N/A"
        NssTxVsTime.append({"x":thisTime,"y":thisNssTx})

        try: thisNssRx = data[ROW_COLUMN_NAMES["nss_rx"]]
        except: thisNssRx = "#N/A"
        NssRxVsTime.append({"x":thisTime,"y":thisNssRx})

        try: thisRateTx = data[ROW_COLUMN_NAMES["rate_tx"]]
        except: thisRateTx = "#N/A"
        RateTxVsTime.append({"x":thisTime,"y":thisRateTx})

        try: thisRateRx = data[ROW_COLUMN_NAMES["rate_rx"]]
        except: thisRateRx = "#N/A"
        RateRxVsTime.append({"x":thisTime,"y":thisRateRx})

        try: thisBwTx = data[ROW_COLUMN_NAMES["bw_tx"]]
        except: thisBwTx = "#N/A"
        BwTxVsTime.append({"x":thisTime,"y":thisBwTx})

        try: thisBwRx = data[ROW_COLUMN_NAMES["bw_rx"]]
        except: thisBwRx = "#N/A"
        BwRxVsTime.append({"x":thisTime,"y":thisBwRx})

    theReturn = {
        "PalVsTime": PalRSSI,
        "ExtVsTime": ExternalRSSI,
        "PalVsAtten": PalVsAtten,
        "ExtVsAtten": ExtVsAtten,
        "ThroughputVsTime": ThroughputVsTime,
        "McsTxVsTime": McsTxVsTime,
        "McsRxVsTime": McsRxVsTime,
        "NssTxVsTime": NssTxVsTime,
        "NssRxVsTime": NssRxVsTime,
        "RateTxVsTime": RateTxVsTime,
        "RateRxVsTime": RateRxVsTime,
        "BwTxVsTime": BwTxVsTime,
        "BwRxVsTime": BwRxVsTime,
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
        theTitle = "ExternalStatisticsExample"
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

    #==========================================================
    #First simple plot. Time plots for RSSI
    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"RSSI Time Plot"
    }
    myReport["Report"].append(item)
    
    PalVsTime = logs["PalVsTime"]
    ExtVsTime = logs["ExtVsTime"]

    allData = []
    allData.append( {"label":"Pal RSSI","color":"black","width":1,"radius":2,"data":PalVsTime,"fill":False,"style":"solid"} )
    allData.append( {"label":"External Data RSSI","color":"red","width":1,"radius":2,"data":ExtVsTime,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "RSSI vs. Time",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"Time (sec)"},
        "yaxis":{"string":"RSSI (dBm)"},
        "tableWidth":"800px",
        "showTable": True,
        "tableStyle": {"font-size":"14px"},
        "data": allData
    }
    myReport["Report"].append(item)

    #==========================================================
    #RSSI as a function of attenuation
    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"RSSI Attenuation Plot"
    }
    myReport["Report"].append(item)
    
    PalVsAtten = logs["PalVsAtten"]
    ExtVsAtten = logs["ExtVsAtten"]

    allData = []
    allData.append( {"label":"Pal RSSI","color":"black","width":1,"radius":2,"data":PalVsAtten,"fill":False,"style":"solid"} )
    allData.append( {"label":"External Data RSSI","color":"red","width":1,"radius":2,"data":ExtVsAtten,"fill":False,"style":"solid"} )

    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "RSSI vs. Attenuation",
        "showDataValues":{"show":False,"color":"green","align":"bottom","offset":"12","fontSize":"30"},
        "xaxis":{"string":"Attenuation (dB)"},
        "yaxis":{"string":"RSSI (dBm)"},
        "tableWidth":"800px",
        "showTable": True,
        "tableStyle": {"font-size":"14px"},
        "data": allData
    }
    myReport["Report"].append(item)

    #==========================================================
    # Standard plots, following the same External Data Interface pattern as RSSI above.
    # Throughput is a single, standalone, full-width plot. MCS/NSS/Data Rate/Bandwidth
    # each show Tx and Rx as two lines in one plot, laid out as a 2x2 grid at half the
    # standalone plot's width (so four of them wrap into two rows of two).
    STANDALONE_PLOT_WIDTH = "800px"
    GRID_PLOT_WIDTH = "400px"

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent": "Standard Plots"
    }
    myReport["Report"].append(item)

    #--- Throughput vs Time (standalone) ---
    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent": "Throughput vs. Time"
    }
    myReport["Report"].append(item)

    ThroughputVsTime = logs["ThroughputVsTime"]
    allData = [
        {"label":"Throughput","color":"black","width":1,"radius":2,"data":ThroughputVsTime,"fill":False,"style":"solid"},
    ]
    item = {
        "elementType": "plot",
        "type": "scatter",
        "title": "Throughput vs. Time",
        "xaxis":{"string":"Time (sec)"},
        "yaxis":{"string":"Throughput (Mbps)"},
        "plotWidth": STANDALONE_PLOT_WIDTH,
        "showTable": False,
        "data": allData
    }
    myReport["Report"].append(item)

    #--- MCS / NSS / Data Rate / Bandwidth (Tx vs Rx), 2x2 grid at half width ---
    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent": "MCS, NSS, Data Rate, and Bandwidth (Tx vs. Rx)"
    }
    myReport["Report"].append(item)

    # These four are laid out as an actual 2x2 grid using scriptManager's "gridFormatting"
    # elementType (a borderless HTML table built cell-by-cell: start -> [newItem ... endItem]*,
    # with a newRow every 2 items -> end). A plain sequence of "plot" items always renders one
    # per row regardless of plotWidth, so reducing the width alone would not actually wrap these
    # into rows of two -- the explicit grid wrapper is what makes that happen.
    GRID_COLUMNS = 2
    gridPlots = [
        ("MCS vs. Time",       "MCS (index)",   logs["McsTxVsTime"],  logs["McsRxVsTime"]),
        ("NSS vs. Time",       "NSS (streams)", logs["NssTxVsTime"],  logs["NssRxVsTime"]),
        ("Data Rate vs. Time", "Rate (Mbps)",   logs["RateTxVsTime"], logs["RateRxVsTime"]),
        ("Bandwidth vs. Time", "Bandwidth (MHz)", logs["BwTxVsTime"], logs["BwRxVsTime"]),
    ]

    myReport["Report"].append({"elementType": "gridFormatting", "action": "start"})
    for i, (title, yLabel, txSeries, rxSeries) in enumerate(gridPlots):
        if i > 0 and i % GRID_COLUMNS == 0:
            myReport["Report"].append({"elementType": "gridFormatting", "action": "newRow"})
        myReport["Report"].append({"elementType": "gridFormatting", "action": "newItem", "padding-left": 5, "padding-right": 5})

        allData = [
            {"label":"Tx","color":"blue","width":1,"radius":2,"data":txSeries,"fill":False,"style":"solid"},
            {"label":"Rx","color":"orange","width":1,"radius":2,"data":rxSeries,"fill":False,"style":"solid"},
        ]
        item = {
            "elementType": "plot",
            "type": "scatter",
            "title": title,
            "xaxis":{"string":"Time (sec)"},
            "yaxis":{"string":yLabel},
            "plotWidth": GRID_PLOT_WIDTH,
            "showTable": False,
            "data": allData
        }
        myReport["Report"].append(item)
        myReport["Report"].append({"elementType": "gridFormatting", "action": "endItem"})
    myReport["Report"].append({"elementType": "gridFormatting", "action": "end"})

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
json_dir = "/home/octoscope/Documents/automationResults/2024-12-04_18-19_calix/1_2024-12-04_18-19_ExternalStatisticsExample/"
fileName = "ExternalStatisticsExample.zip"
json_file = json_dir + fileName

theData = analyze(directory_name,json_file,ea_root)
print(theData)

#theData = summarize(directory_name,json_dir,ea_root)
'''
