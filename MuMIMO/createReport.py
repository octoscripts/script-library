import sys
import json
import requests
import base64
import os
from pathlib import Path

def createReport(directory_name,json_dir,ea_root,someData=None):

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
    except:
        CL = ""
    #print("Command line part is " + CL)

    if json_dir[len(json_dir)-1] != "/": json_dir += "/"
    print('>>> createReport_main json_dir', json_dir)
    #Get all of the zip files in the json directory
    theZips = []
    for x in os.listdir(json_dir):
        if ".zip" in x and "CSV" not in x and "taJSON" not in x:
            #print (x)
            theZips.append(json_dir + x)

    #Do the whole analysis part using the data in this zip file.
    theZips.sort(reverse=True)
    fileName = theZips[0]

    with open(fileName, "rb") as f:
        print("Grabbing the zip file from {}".format(fileName))
        bytes = f.read()
        encoded = base64.b64encode(bytes)
        #print(encoded)
        api_endpoint = ea_root + "zip2csv"
        data = {'zip':encoded}
        theResponse = requests.post(url=api_endpoint, data=data)
        #print(theResponse)
        theJson = json.loads(theResponse.text)
        #print(theJson)

    print("Write the CSV file out to {}".format(directory_name+'csv.csv'))
    f = open(directory_name+'csv.csv', 'w')
    f.write(theJson["csv"])
    f.close()

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
    print("Here is the basic structure of the data: {}".format(json.dumps(y,indent=4)))
    thePals = []
    for item in y["filteredData"]["palEndpoints"]["map"]:
        value = y["filteredData"]["palEndpoints"]["map"][item]
        if "iperf" not in value and "sn" not in value and "_" not in value: thePals.append(int(item)+1)

    print("Here are the Pals: {}".format(thePals))
    
    #Bit hard-coded right now, but find the "E" device which should be the roamer.
    peMap = y["filteredData"]["palEndpoints"]["map"]
    tpMap = y["filteredData"]["trafficPairs"]["map"]
    #print(tpMap)
        
    #Use EA to gather up some statistics, plots, etc.
    #Use the generic report generator to put these into a report.

    # Analyze the CSV file
    csv_path = directory_name+'csv.csv'
    #print(csv_path)
    csv = Path(csv_path).read_text()
    api_endpoint = ea_root + "objectify"
    data = {'csv':csv}
    #print("The endpoint is {}".format(api_endpoint))
    #print(data)
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)

    headers = theJson["headers"]
    dataSet = theJson["dataSet"]
    version = theJson["version"]
    #print(json.dumps(y,indent=4))
    #print("Returned with version {}".format(version))
    #print("Headers found has length {}".format(len(headers)))
    #print("Length of the dataset is {}".format(len(dataSet)))
    
    if "error" in theJson:
        print("objectify: This data returned an error: {}".format(theJson["error"]))
        sys.exit(13)

    api_endpoint = ea_root + "crunch"
    run = 1
    data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    if "error" in theJson:
        print("crunch: This data returned an error: {}".format(theJson["error"]))
        sys.exit(23)
    analyzedData = theJson["crunchedData"]
    theNotes = theJson["Notes"]
    #print(theNotes)

    #print("The number of traffic pairs for which you have data is {}".format(len(analyzedData)))

    #Write a report
    myReport = {}
    myReport["Title"] = "Multi-user MIMO"
    myReport["Report"] = []

    item = {
        "elementType": "section",
        "headingType": "h1",
        "headingContent":"Multi-userMIMO under SW 2.1"
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Overview",
        "text": "In this test run traffic between a STApal used as a client, and two Pal6s being used as APs."
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"Test configuration",
    }
    myReport["Report"].append(item)

    if someData:
        item = {
        "elementType": "table",
        "type": "table",
        "title": "Test Configuration Parameters, file: " + fileName,
        "tableWidth":"700px",
        "data": [
	    {
	        "label": "Item",
                "data": [
                    "Protocol","Bandwidth","Channel", "Traffic Direction","Streams"
                ]
            },
            {
                "label": "Value",
	        "data": [
                    "802."+someData["iface"],someData["bandwidth"],someData["channel"],someData["upOrDown"],someData["nss"]
	        ]
            },
            ]
        }
        myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"Throughput (Mbps)",
        "text": "Throughput time series."
    }
    myReport["Report"].append(item)

    timeSeries1 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisThroughput = float(data["Aggregated Throughput [Mbps]"])
        except:continue
        timeSeries1.append({"x":thisTime/1000,"y":round(thisThroughput,2)})

    allData = [{
	"label":"Aggregated Throughput",
	"color":"blue",
	"width":1,
	"radius":0,
	"data": timeSeries1,
	"fill": -1,
	"style": "solid"
    }]

    max30 = 0
    maxAll = 0
    for data in timeSeries1:
        if data["x"]<=30: max30 = max(data["y"],max30)
        maxAll = max(data["y"],maxAll)
    #print("Maximum throughput in the first 30 seconds is {}.".format(max30))
    #print("Maximum throughput overall is {}.".format(maxAll))

    idx = 0
    for pair in tpMap:
        moreSeries = []
        thisName = tpMap[pair]
        for data in dataSet:
            try:thisTime = float(data["Time [ms]"])
            except:continue
            try:thisThroughput = float(data[thisName + " Throughput [Mbps]"])
            except:continue
            moreSeries.append({"x":thisTime/1000,"y":round(thisThroughput,2)})
        idx += 1
        color = colors[idx % len(colors) + 6]
        allData.append({
	    "label":thisName,
	    "color":color,
	    "width":1,
	    "radius":0,
	    "data": moreSeries,
	    "fill": -1,
	    "style": "solid"
        })

    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "Throughput time plot",
        "xaxis":{"string":"Time (sec)"},
        "yaxis":{"string":"Throughput (Mbps)"},
        "showTable": False,
        "plotWidth":"800px",
        "data": allData
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"RSSI at the STA",
        "text": "RSSI time series (data and control), dBm."
    }
    myReport["Report"].append(item)

    timeSeries1 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:dataRSSI = float(data["Pal Endpoint 1 Data RSSI [dBm] Mean"])
        except:continue
        timeSeries1.append({"x":thisTime/1000,"y":round(dataRSSI,2)})
    timeSeries2 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:controlRSSI = float(data["Pal Endpoint 1 Control RSSI [dBm] Mean"])
        except:continue
        timeSeries2.append({"x":thisTime/1000,"y":round(controlRSSI,2)})
    timeSeries3 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:dataRSSI = float(data["Pal Endpoint 2 Data RSSI [dBm] Mean"])
        except:continue
        timeSeries3.append({"x":thisTime/1000,"y":round(dataRSSI,2)})
    timeSeries4 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:controlRSSI = float(data["Pal Endpoint 2 Control RSSI [dBm] Mean"])
        except:continue
        timeSeries4.append({"x":thisTime/1000,"y":round(controlRSSI,2)})
    timeSeries5 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:dataRSSI = float(data["Pal Endpoint 3 Data RSSI [dBm] Mean"])
        except:continue
        timeSeries5.append({"x":thisTime/1000,"y":round(dataRSSI,2)})
    timeSeries6 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:controlRSSI = float(data["Pal Endpoint 3 Control RSSI [dBm] Mean"])
        except:continue
        timeSeries6.append({"x":thisTime/1000,"y":round(controlRSSI,2)})
    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "RSSI time plot",
        "xaxis":{"string":"Time (sec)"},
        "yaxis":{"string":"RSSI (dBm)"},
        "showTable": False,
        "plotWidth":"800px",
        "data":[
	    {
	        "label":"Data RSSI 1",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": timeSeries1,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Control RSSI 1",
	        "color":"red",
	        "width":1,
	        "radius":0,
	        "data": timeSeries2,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Data RSSI 2",
	        "color":"green",
	        "width":1,
	        "radius":0,
	        "data": timeSeries3,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Control RSSI 2",
	        "color":"orange",
	        "width":1,
	        "radius":0,
	        "data": timeSeries4,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Data RSSI 3",
	        "color":"grey",
	        "width":1,
	        "radius":0,
	        "data": timeSeries5,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Control RSSI 3",
	        "color":"black",
	        "width":1,
	        "radius":0,
	        "data": timeSeries6,
	        "fill": -1,
	        "style": "solid"
	    }
        ]	    
    }
    myReport["Report"].append(item)
    
    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"Data rate time series",
        "text": "All measured PHY data rates."
    }
    myReport["Report"].append(item)
    

    timeSeries1 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        header = "Pal Endpoint {} RX Rate [Mbps] Mode".format(thePals[0])
        try:
            thisRateRx = float(data[header])
        except:continue
        timeSeries1.append({"x":thisTime/1000,"y":round(thisRateRx,2)})
    timeSeries2 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisRateTx = float(data["Pal Endpoint {} TX Rate [Mbps] Mode".format(thePals[0])])
        except:continue
        timeSeries2.append({"x":thisTime/1000,"y":round(thisRateTx,2)})
    timeSeries3 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisRateRx = float(data["Pal Endpoint {} RX Rate [Mbps] Mode".format(thePals[1])])
        except:continue
        timeSeries3.append({"x":thisTime/1000,"y":round(thisRateRx,2)})
    timeSeries4 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisRateTx = float(data["Pal Endpoint {} TX Rate [Mbps] Mode".format(thePals[1])])
        except:continue
        timeSeries4.append({"x":thisTime/1000,"y":round(thisRateTx,2)})
    timeSeries5 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisRateRx = float(data["Pal Endpoint {} RX Rate [Mbps] Mode".format(thePals[2])])
        except:continue
        timeSeries5.append({"x":thisTime/1000,"y":round(thisRateRx,2)})
    timeSeries6 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisRateTx = float(data["Pal Endpoint {} TX rate [Mbps] Mode".format(thePals[2])])
        except:continue
        timeSeries6.append({"x":thisTime/1000,"y":round(thisRateTx,2)})

    maxPhy = 0
    for data in timeSeries1: maxPhy = max(data["y"],maxPhy)
    for data in timeSeries2: maxPhy = max(data["y"],maxPhy)
    for data in timeSeries3: maxPhy = max(data["y"],maxPhy)
    for data in timeSeries4: maxPhy = max(data["y"],maxPhy)
    for data in timeSeries5: maxPhy = max(data["y"],maxPhy)
    for data in timeSeries6: maxPhy = max(data["y"],maxPhy)

    if maxAll > maxPhy*0.9:
        text = "It is evident from the throughput data that MU-MIMO is operational.<br/>"
        text += "In the first (and last) part of the data, with MU-MIMO not operational, the throughput is about {} Mbps.<br/>".format(round(max30,2))
        text += "In the middle section, however, the throughput is about {} Mbps.<br/>".format(round(maxAll,2))
        text += "Since the maximum PHY rate measured is only {} Mbps, the only way to get {} Mbps of throughput is via MU-MIMO.<br/>".format(round(maxPhy,2),round(maxAll,2))
        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Indication of MU-MIMO based on throughput",
            "text": text
        }
        myReport["Report"].append(item)
        
    

    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "Data rate time plot",
        "xaxis":{"string":"Time (sec)"},
        "yaxis":{"string":"PHY data rates (Mbps)"},
        "showTable": False,
        "plotWidth":"800px",
        "data":[
	    {
	        "label":"Rx data rate 1, mode (Mbps)",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": timeSeries1,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Tx data rate 1, mode (Mbps)",
	        "color":"red",
	        "width":1,
	        "radius":0,
	        "data": timeSeries2,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Rx data rate 2, mode (Mbps)",
	        "color":"green",
	        "width":1,
	        "radius":0,
	        "data": timeSeries3,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Tx data rate 2, mode (Mbps)",
	        "color":"orange",
	        "width":1,
	        "radius":0,
	        "data": timeSeries4,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Rx data rate 3, mode (Mbps)",
	        "color":"grey",
	        "width":1,
	        "radius":0,
	        "data": timeSeries5,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Tx data rate 3, mode (Mbps)",
	        "color":"black",
	        "width":1,
	        "radius":0,
	        "data": timeSeries6,
	        "fill": -1,
	        "style": "solid"
	    }
        ]	    
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"MCS time series",
        "text": "All measured MCS values."
    }
    myReport["Report"].append(item)

    timeSeries1 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisValRx = float(data["Pal Endpoint 1 RX MCS Mode"])
        except:continue
        timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
    timeSeries2 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisValTx = float(data["Pal Endpoint 1 TX MCS Mode"])
        except:continue
    timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})

    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "MCS time plot",
        "xaxis":{"string":"Time (sec)"},
        "yaxis":{"string":"MCS value"},
        "showTable": False,
        "plotWidth":"800px",
        "data":[
	    {
	        "label":"Rx MCS, mode",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": timeSeries1,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Tx MCS, mode",
	        "color":"green",
	        "width":1,
	        "radius":0,
	        "data": timeSeries2,
	        "fill": -1,
	        "style": "solid"
	    }
        ]	    
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"Stream time series",
        "text": "All measured spatial stream values."
    }
    myReport["Report"].append(item)

    timeSeries1 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisValRx = float(data["Pal Endpoint 1 RX Nss Mode"])
        except:continue
        timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
    timeSeries2 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisValTx = float(data["Pal Endpoint 1 TX Nss Mode"])
        except:continue
    timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})

    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "Spatial Stream time plot",
        "xaxis":{"string":"Time (sec)"},
        "yaxis":{"string":"Number of spatial streams"},
        "showTable": False,
        "plotWidth":"800px",
        "data":[
	    {
	        "label":"Rx spatial streams, mode",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": timeSeries1,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Tx spatial streams, mode",
	        "color":"green",
	        "width":1,
	        "radius":0,
	        "data": timeSeries2,
	        "fill": -1,
	        "style": "solid"
	    }
        ]	    
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h3",
        "headingContent":"Bandwidth time series",
        "text": "All measured bandwidth values."
    }
    myReport["Report"].append(item)

    timeSeries1 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisValRx = float(data["Pal Endpoint 1 RX Bandwidth [MHz] Mode"])
        except:continue
        timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
    timeSeries2 = []
    for data in dataSet:
        try:thisTime = float(data["Time [ms]"])
        except:continue
        try:thisValTx = float(data["Pal Endpoint 1 TX Bandwidth [MHz] Mode"])
        except:continue
        timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})

    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "Bandwidth time plot",
        "xaxis":{"string":"Time (sec)"},
        "yaxis":{"string":"Bandwidth [MHz]"},
        "showTable": False,
        "plotWidth":"800px",
        "data":[
	    {
	        "label":"Rx bandwidth (MHz), mode",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": timeSeries1,
	        "fill": -1,
	        "style": "solid"
	    },
	    {
	        "label":"Tx bandwidth (MHz), mode",
	        "color":"green",
	        "width":1,
	        "radius":0,
	        "data": timeSeries2,
	        "fill": -1,
	        "style": "solid"
	    }
        ]	    
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Alerts",
        "text": "List of any Alerts generated in the running of this test."
    }
    myReport["Report"].append(item)
    alerts = theNotes["Alerts"]
    if len(alerts) == 0:
        item = {
            "elementType": "text",
            "text": "\nThere are no Alerts to report."
        }
    myReport["Report"].append(item)

    ###########
    ## Do the PCAP analysis
    ###########

    base_endpoint = "http://localhost:8080/pcapAPI"    

    thePcaps = []
    for x in os.listdir(directory_name + "./"):
        #print(x)
        if ".pcap" in x and ".pcapng" not in x:
            thePcaps.append(x)
    thePCAP = thePcaps[0]
    if len(thePcaps)>0:
    
        #How many packets are there?
        baseURL = "http://localhost:8080/pcapAPI"
        api_endpoint = base_endpoint + "?fileName=" + thePCAP +"&pcapDir="+directory_name+"&action=getTotalPacketCount"
        #api_endpoint = base_endpoint + "?fileName=" + thePCAP +"&action=getTotalPacketCount"
        print("Running the captured file " + thePCAP + " through a PCAP analysis.  Get the packet count.")
        print("This is the API call: {}".format(api_endpoint))
        apiResponse = requests.get(api_endpoint)
        returnObject = json.loads(apiResponse.text)
        #print(returnObject)
        totalPacketCount = int(returnObject["result"])
        print("There are a total of {} packets in this capture.".format(totalPacketCount))

        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"PCAP Analysis of " + fileName,
            "text": "PCAP Analysis to look for evidence of MU-MIMO operation.<br/>"
        }
        myReport["Report"].append(item)

        item = {
            "elementType": "text",
            "text": "There are a total of {} packets in this capture.<br/>".format(totalPacketCount)
        }
        myReport["Report"].append(item)

        startAt = 0
        endAt = totalPacketCount
        endAt = 200000
        action = "getHeMuInfo"

        chunkSize = 20000
        thisStart = startAt
        thisEnd = thisStart + chunkSize
        quitWhenYouHave = 10
        HeMuPacketsSoFar = 0

        allResults = []
        muMIMO = []

        while thisEnd < endAt and HeMuPacketsSoFar < quitWhenYouHave:

            api_endpoint = base_endpoint + "?fileName=" + thePCAP +"&pcapDir="+directory_name+"&firstPacket=" + str(thisStart) + "&lastPacket=" + str(thisEnd);
            #api_endpoint = base_endpoint + "?fileName=" + thePCAP +"&firstPacket=" + str(thisStart) + "&lastPacket=" + str(thisEnd);
            api_endpoint += "&action=" + action

            print("The call is to:  " + api_endpoint)
            apiResponse = requests.get(url=api_endpoint)
            returnObject = json.loads(apiResponse.text)

            allResults.append(returnObject)
            thisStart = thisEnd + 1
            thisEnd = thisStart + chunkSize

            muMIMO = []
            data = returnObject["result"]["HeMuInfo"]                        
            for item in data:
                raw = item["raw"]
                if raw["SIGB_Compression"] == 1: muMIMO.append(item)
                HeMuPacketsSoFar += len(muMIMO)
            print("So far I have {} HE-MU packets out of {} needed.".format(HeMuPacketsSoFar,quitWhenYouHave))

        if len(muMIMO)>0:
            #print(muMIMO[0])

            item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Example MU-MIMO Packet",
                "text": "An example of an HE-MU packet showing MU-MIMO operation."
            }
            myReport["Report"].append(item)        

            thisOne = dict(muMIMO[0])
            remove = thisOne.pop("ruList")

            text = json.dumps(thisOne,indent=4)
            text += "<br/>"
            text += "When SIG-B compression is enabled, this is full-bandwidth MU-MIMO.  In this case, the number of symbols or users is the number of MU-MIMO users.<br/>"
            text += "In this case we have:<br/>"
            text += "Packet Number: " + str(thisOne["packetNumber"]) + "<br/>"
            text += "SIG-B Compression: " + str(thisOne["raw"]["SIGB_Compression"]) + "<br/>"
            text += "# MU-MIMO users: " + str(thisOne["raw"]["NumSymOrMU_MIMO"]) + "<br/>"

            item = {
                "elementType": "text",
                "text": text
            }
            myReport["Report"].append(item)

        else:
            item = {
                "elementType": "text",
                "text": "There is no evidence of MU-MIMO operation in this data."
            }
            myReport["Report"].append(item)
            
    else:
            item = {
                "elementType": "text",
                "text": "No packets captured to test the MU-MIMO operation."
            }
            myReport["Report"].append(item)
        
        
    
    #_________________________________________________________________________________________________________________________________
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
    fileName = "MU-MIMOv2.html"
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
        "label": "Test Report"
    }
    jsonPlot["_editable"] = False    
    f = open(directory_name+'TestReport.json', "w")
    f.write(json.dumps(jsonPlot,indent=4))
    f.close()

    print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

    #Write messages if you have any.  Here's an example.
    jsonMessages = {}
    alertMessage = "None"
    if len(alerts) != 0: alertMessage = "Alerts found! See report for details."
    jsonMessages["alertMessage"] = {"val":{"_scriptMessage_":alertMessage},"label":"Alerts"}
    jsonMessages["_editable"] = False
    f = open(directory_name+'TestMessages.json', "w")
    f.write(json.dumps(jsonMessages,indent=4))
    f.close()
	    
#===
#Use this for debugging.  Otherwise, comment it out.
'''
directory_name = "./"
json_path = "/home/octoscope/Documents/automationResults/2025-04-25_10-54_calix/1_2025-04-25_10-54_MuMIMO/"
ea_root = "http://localhost:8080/"
someData = {
    "iface":"iface",
    "bandwidth":"bw",
    "channel":"ch",
    "band":"band",
    "upOrDown":"upOrDown",
    "nss":"nss"
    }

createReport(directory_name,json_path,ea_root,someData)
'''
