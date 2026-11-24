import sys
import json
import os
import requests
import base64
import pprint
import time
import math
pp = pprint.PrettyPrinter(indent=4)

from pathlib import Path

def formatMAC(mac):
    fMAC = mac
    fMAC = fMAC.replace(".",":")
    fMAC = fMAC.upper()
    if(fMAC[len(fMAC)-1]==":"): fMAC = fMAC[0:len(fMAC)-1]
    fMAC = fMAC.strip()
    return fMAC

def _findHeader(headers, mustContainAll):
        """Return the first header string containing every substring in mustContainAll, or None."""
        for h in headers:
                if all(sub in h for sub in mustContainAll):
                        return h
        return None

def _extractSeries(dataSet, timeHeader, valueHeader, t0):
        """Pull {x,y} points for one column, skipping non-numeric and non-finite (nan/inf) values."""
        points = []
        if not valueHeader:
                return points
        for row in dataSet:
                tVal = row.get(timeHeader)
                yVal = row.get(valueHeader)
                try:
                        tVal = float(tVal)
                        yVal = float(yVal)
                except (TypeError, ValueError):
                        continue  # skips "#N/A" and similar non-numeric entries
                if not math.isfinite(tVal) or not math.isfinite(yVal):
                        continue  # skips "nan"/"inf"/"-inf" strings -- float() parses these without error
                points.append({"x": round(tVal - t0, 3), "y": yVal})
        return points

def _addTimeSeriesPlot(myReport, sectionTitle, yAxisLabel, series):
        """series: list of (label, points, color) tuples. Skips empty series; skips the whole
        plot (with a log message) if none of the series have any data."""
        plotData = []
        for label, points, color in series:
                if len(points) == 0:
                        print(">>> No data for series '{}' in plot '{}'; leaving it out.".format(label, sectionTitle))
                        continue
                plotData.append({
                        "label": label,
                        "color": color,
                        "width": 1,
                        "radius": 0,
                        "data": points,
                        "fill": -1,
                        "style": "solid"
                })
        if len(plotData) == 0:
                print(">>> No data available at all for plot: {}; skipping it entirely.".format(sectionTitle))
                return

        item = {
                        "elementType": "section",
                        "headingType": "h2",
                        "headingContent": sectionTitle,
                        "text": ""
        }
        myReport["Report"].append(item)

        item = {
                        "elementType": "plot",
                        "type": "scatter",
                        "title": "",
                        "xaxis": {"string": "Elapsed Time (s)"},
                        "yaxis": {"string": yAxisLabel},
                        "showTable": False,
                        "plotWidth": "800px",
                        "data": plotData
        }
        myReport["Report"].append(item)

def main(directory_name,json_dir,ea_root,ssid,pwd):

    start_time = time.time()

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

    #Verify where scriptManager is running
    api_endpoint = "http://localhost:5678/exec?command=pwd"
    r = requests.get(url=api_endpoint)
    y = json.loads(r.text)
    scriptManagerLocation = y["stdout"]
    scriptManagerLocation = scriptManagerLocation.replace("\n","")
    storageLocation = scriptManagerLocation + "/" + "storage/"
    #print("storageLocation is {}".format(storageLocation))    

    #Write a report
    myReport = {}
    myReport["Title"] = "TCP RTT Analysis"
    myReport["Report"] = []    

    # PAL STATS ANALYSIS PART #################################################################################

    theZips = []
    for x in os.listdir(json_dir):
        if ".zip" in x and "CSV" not in x and "-TAJ" not in x and "taJSON" not in x:
            #print (x)
            theZips.append(json_dir + x)
    #print(theZips)
    #Most recent first (filenames are timestamp-prefixed).
    theZips.sort(reverse=True)

    item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"System Diagram",
                "text": ""
    }
    myReport["Report"].append(item)

    imageStorage = 'reportImages/'
    pathToImages = storageLocation+imageStorage
    print(">>> createReport: Copy report image(s) to ", pathToImages)
    if not os.path.exists(pathToImages):
                os.makedirs(pathToImages)
    #print(directory_name)
    for file in os.listdir(directory_name):
            #print('>>> createReport file: ', file)
            if ".png" in file or ".jpg" in file:
                    #print('>>> createReport copying ', file)
                    command = 'cp ' + directory_name + file + ' ' + pathToImages + file
                    #print('>>> command ', command)
                    os.popen(command)
                    time.sleep(1)

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

    #For this test, pull the JSON information created.
    jsonFile = None
    for x in os.listdir(json_dir):
        #print (x)
        if "testresultlog" in x:
            jsonFile = json_dir + x

    if jsonFile:
        f = open(jsonFile)
        testResultLogJson = json.load(f)
        f.close

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
                    fwString = fwString + "STApal Version :<br>" + new + " :" + palFw[key] + "<br>"
                else :
                    fwString = fwString + new + " :" + palFw[key] + "<br>"
                i = i + 1
            if "Pal-" in key:
                if j == 0 :
                    #fwString = fwString + "PAL Version :<br>" + key + " :" + palFw[key] + "<br>"
                    fwString = "{} PAL Version :<br/> {} : {} <br/>".format(fwString,key, palFw[key])
                else :
                    fwString = fwString + key + " :" + palFw[key] + "<br>"
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
                            "Spirent OCTOBOX Software Version",
                            "DUT Model Name",
                            "DUT Firmware Version",
                            "Pal/STApal Version",
                            "Total Run Time (HH:MM:SS)",
                            "Date and Time",
                            "Test Name"
                            ]
                        },
                        {
                            "data": [
                                testResultLogJson["testInfo"]["starDustVersion"],
                                testResultLogJson["testInfo"]["model"],
                                testResultLogJson["testInfo"]["revision"],
                                fwString,
                                testResultLogJson["testRunTime"],
                                dt_string,
                                new_testname
                            ]
                        }
                    ]
        }
        myReport["Report"].append(item)

        item = {
                    "elementType": "section",
                    "headingType": "h2",
                    "headingContent":"Test Description",
                    "text": testResultLogJson["testInfo"]["description"]
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

    item = {"elementType": "pagebreak"}
    myReport["Report"].append(item)

    # #################### EXPERT ANALYSIS ON THE RAW JSON ARCHIVE #######################
    # Take the zipped archive of per-endpoint JSONs that the automation script produced,
    # and run it through the Expert Analysis service's archive pipeline:
    #   zip -> zip2csv -> CSV -> objectify -> headers/dataSet -> crunch -> crunchedData/Notes
    # crunchedData/Notes are then available for whatever custom plots/tables you want to add below.

    crunchedData = None
    eaNotes = {}
    headers = None
    dataSet = None

    if len(theZips) == 0:
            print(">>> No result archive zip found in {}; skipping Expert Analysis.".format(json_dir))
    else:
            archiveFile = theZips[0]
            print(">>> Running Expert Analysis on archive: {}".format(archiveFile))

            try:
                    with open(archiveFile, "rb") as f:
                            encoded = base64.b64encode(f.read())

                    api_endpoint = ea_root + "zip2csv"
                    theResponse = requests.post(url=api_endpoint, data={'zip': encoded})
                    theJson = json.loads(theResponse.text)
                    if "error" in theJson:
                            print(">>> zip2csv returned an error: {}".format(theJson["error"]))
                    csv = theJson["csv"]

                    api_endpoint = ea_root + "objectify"
                    theResponse = requests.post(url=api_endpoint, data={'csv': csv})
                    theJson = json.loads(theResponse.text)
                    if "error" in theJson:
                            print(">>> objectify returned an error: {}".format(theJson["error"]))
                    headers = theJson["headers"]
                    dataSet = theJson["dataSet"]

                    api_endpoint = ea_root + "crunch"
                    theResponse = requests.post(url=api_endpoint, data={'headers': headers, 'dataSet': json.dumps(dataSet), 'run': 1})
                    theJson = json.loads(theResponse.text)
                    if "error" in theJson:
                            print(">>> crunch returned an error: {}".format(theJson["error"]))
                    crunchedData = theJson["crunchedData"]
                    eaNotes = theJson.get("Notes", {})

                    print(">>> Expert Analysis crunch complete. {} endpoint(s) of crunched data available.".format(len(crunchedData) if crunchedData else 0))
                    #Uncomment to inspect the actual shape of crunchedData/headers/dataSet while building a new custom plot:
                    #pp.pprint(headers)
                    #pp.pprint(crunchedData)

            except Exception as err:
                    print(">>> Expert Analysis pipeline failed: {}".format(err))
                    crunchedData = None

    #Surface any Alerts Expert Analysis found, same convention used elsewhere (e.g. OFDMA-Decode's createReport).
    alerts = eaNotes["Alerts"] if eaNotes and "Alerts" in eaNotes else []
    item = {
                    "elementType": "section",
                    "headingType": "h2",
                    "headingContent": "Expert Analysis Alerts",
                    "text": "\n".join(alerts) if alerts else "There are no Alerts to report."
    }
    myReport["Report"].append(item)

    # -------------------------------------------------------------------------------------
    # CUSTOM TIME-SERIES PLOTS (built from the objectified `dataSet` -- a row-per-second time
    # series -- not from `crunchedData`, which is bucketed by attenuation step instead of time).
    #
    # For PHY-layer stats (rate/MCS/bandwidth/streams), "RX" at the STA endpoint corresponds to
    # downlink (AP -> STA) and "TX" corresponds to uplink (STA -> AP), regardless of which
    # direction the iperf traffic itself was run in. We use the per-second "Mode" statistic
    # (the single most-represented value in that second) as the representative instantaneous
    # value, rather than Min/Max, since that's the natural choice for a plain time-series line.
    # These all currently assume a single Pal Endpoint (endpoint 1); if a test has more than
    # one STA/endpoint, this would need to loop over endpoints and add a series per endpoint.
    # -------------------------------------------------------------------------------------
    if headers and dataSet:
            try:
                    # Find the aggregate throughput column. objectify() recomputes this column itself
                    # as the sum of all per-traffic-pair throughputs, so it's reliable even though the
                    # raw CSV often shows "#N/A" in that column before objectify runs.
                    throughputHeader = None
                    for h in headers:
                            if "Throughput [Mbps]" in h and "Aggregate" in h and "calc" not in h.lower():
                                    throughputHeader = h
                                    break
                    if not throughputHeader:
                            # Fall back to any single throughput column if there's no aggregate one.
                            for h in headers:
                                    if "Throughput [Mbps]" in h and "calc" not in h.lower():
                                            throughputHeader = h
                                            break

                    # Find a time column. Prefer a wall-clock timestamp ("Server timestamp", in
                    # seconds) over the synthetic "Time [ms]" filler objectify() adds when there's
                    # no better time column, since the real timestamp gives an evenly-scaled x-axis.
                    timeHeader = None
                    for h in headers:
                            if h == "Server timestamp" or (h.startswith("Server timestamp") and "MS" not in h):
                                    timeHeader = h
                                    break
                    if not timeHeader:
                            for h in headers:
                                    if "Time" in h:
                                            timeHeader = h
                                            break

                    if not timeHeader:
                            print(">>> Could not find a time column; skipping all time-series plots.")
                    else:
                            # Anchor all plots to the same t0 (first parseable time value) so their x-axes line up.
                            t0 = None
                            for row in dataSet:
                                    try:
                                            t0 = float(row.get(timeHeader))
                                            if math.isfinite(t0):
                                                    break
                                    except (TypeError, ValueError):
                                            continue
                            if t0 is None:
                                    print(">>> Could not find a usable starting time value; skipping all time-series plots.")
                            else:

                                    rttHeaders = []
                                    for header in headers:
                                        if "iPerf2 RTT [us]" in header: rttHeaders.append(header)
                                    #print(rttHeaders)
                                    rttPoints = []
                                    for header in rttHeaders:
                                        rttPoints.append( _extractSeries(dataSet,timeHeader,header,t0))
                                    #print(rttPoints)
                                    iPerf2Plots = []
                                    for i in range(0,len(rttHeaders)):
                                        iPerf2Plots.append( (rttHeaders[i],rttPoints[i],colors[i % len(colors)]) )
                                    #print(iPerf2Plots)

                                    # --- PHY Rate (UL/DL) vs. Time ---
                                    _addTimeSeriesPlot(myReport, "iPerf2 RTT (usec) vs. Time", "iPerf2 RTT (microsec)",iPerf2Plots)

            except Exception as err:
                    print(">>> Could not build time-series plots: {}".format(err))
    
    

    # PCAP ANALYSIS PART #################################################################################
    #For this test, pull the PCAP file
    file = None
    while not file:
        time.sleep(1)
        print("Looking for the pcap file.  Current name is {}".format(file))
        for x in os.listdir(json_dir):
            #print (x)
            if ".pcap" in x and ".pcapng" not in x:
                file = x
                pcapDir = json_dir

    base_endpoint = "http://localhost:8080/pcapAPI/"

    #Get the total number of packets.
    api_endpoint = base_endpoint + "?action=getTotalPacketCount"
    api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
    if ssid and pwd: api_endpoint += "&ssid={}&password={}".format(ssid,pwd)
    print("The call is to:  " + api_endpoint)
    apiResponse = requests.get(url=api_endpoint)
    returnObject = json.loads(apiResponse.text)
    totalPackets = returnObject["result"]
    print("The total number of packets in this file is {}".format(totalPackets))

    #Get data from the file
    allTCPpackets = []
    stepSize = 9999
    firstPacket = 1
    lastPacket = firstPacket+stepSize
    countAll = 0
    labels = []
    rttData = []
    msduLen = []
    frame2ackDelta = []
    rawSN2AN = []
    tcpOrAck = []
    tcpPackets = []
    ackPackets = []
    ipStream = []    
    while firstPacket < min(totalPackets,500000):
        lastPacket = min(firstPacket+stepSize,totalPackets)
        api_endpoint = base_endpoint + "?action=getPacketList"
        api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
        api_endpoint += "&firstPacket=" + str(firstPacket) + "&lastPacket=" + str(lastPacket)
        api_endpoint += "&filters=TCP"
        api_endpoint += "&preferTshark=false"
        if ssid and pwd: api_endpoint += "&ssid={}&password={}".format(ssid,pwd)        
        print("The call is to:  " + api_endpoint)
        apiResponse = requests.get(url=api_endpoint)
        returnObject = json.loads(apiResponse.text)
        #print("{}".format(returnObject["result"]))
        theResult = returnObject["result"]
        print ("Number of packets gathered is {}".format(len(theResult)))
        countAll += len(theResult)
        for packet in theResult:
            allTCPpackets.append(packet)
            if "tcpSegments" in packet:
                ipStream.append(packet)
                for segment in packet["tcpSegments"]:
                    isACK = False
                    if "acksFrame" in segment:
                        isACK = True
                        rttData.append( 1000*float(segment["ackRtt"]) )
                        labels.append(packet["packetNumber"])
                        f2a = int(packet["packetNumber"]) - int(segment["acksFrame"])
                        frame2ackDelta.append( f2a )
                        ackPackets.append(packet)
                    #print ("This many packets {}".format(len(segment)))
                    if not isACK:
                        tcpPackets.append(packet)
                        msduLen.append(segment["msduLength"])
                    tcpOrAck.append({"x":packet["packetNumber"],"y":1})
                    rawACK = int(segment["tcpAcknowledgementNumber"])
                    rawSEQ = int(segment["tcpSequenceNumber"])
                    if rawACK < rawSEQ: rawACK += 4294967295  #4 bytes of FF,  FFFFFFFF = 4,294,967,295
                    rawSN2AN.append( rawACK - rawSEQ  )
        firstPacket = lastPacket + 1
        if firstPacket >= totalPackets: break

    print("There are {} TCP packets, and {} associated ACK packets".format(len(tcpPackets),len(ackPackets)))

    #Find associated TCP and ACK packets, and timing.
    timing1 = []
    rttData2 = []
    timing2 = []
    for packet in allTCPpackets:
        for segment in packet["tcpSegments"]:
            if "acksFrame" in segment:
                ackedFrameNumber = segment["acksFrame"]
                ackedFrame = None
                for frame in allTCPpackets:
                    if frame["packetNumber"]==ackedFrameNumber:
                        ackedFrame = frame
                        break
                if ackedFrame:
                    ackedFrameTime = ackedFrame["arrivalTimeSeconds"]
                    ackTime = packet["arrivalTimeSeconds"]
                    timeDifference = (ackTime-ackedFrameTime) * 1000
                    timing1.append( {"x":packet["arrivalTimeSeconds"]-ipStream[0]["arrivalTimeSeconds"], "y":timeDifference} )
                    rttData2.append( {"x":packet["packetNumber"], "y":timeDifference} )

                    #print("Frame {} acks frame {}.".format(packet["packetNumber"],ackedFrameNumber))
                    #print("Frame time is {}, and the acked frame time is {}, for a time difference of {}".format(packet["arrivalTimeSeconds"],ackedFrameTime,timeDifference))
                    #sys.exit()
            if "iRtt" in segment:
                timing2.append( {"x":packet["arrivalTimeSeconds"]-ipStream[0]["arrivalTimeSeconds"], "y":segment["iRtt"]*1000} )

    print("-------------------------------------------------------------------------------------------------------------")

    item = {
        "elementType":"section",
        "headingType":"h1",
        "headingContent":"RTT Analysis based on Wireshark Analysis of TCP packets: "
    }
    myReport["Report"].append(item)

    item = {
        "elementType":"section",
        "headingType":"h2",
        "headingContent":"File being analyzed: " + pcapDir + file,
        "text": "Date and time of test start: " + directoriesJson["dateOfStart"] + " at " + directoriesJson["timeOfStart"].replace("-",":")
    }
    myReport["Report"].append(item)

    item = {
        "elementType":"section",
        "headingType":"h3",
        "headingContent":"Packet analysis information",
        "text": "The last API call was {}, and the total number of packets gathered by this analysis is {}".format(api_endpoint,countAll)
    }
    myReport["Report"].append(item)


    item = {
        "elementType":"plot",
        "type": "line",
        "title": "RTT Line Plot",
        "labels": labels,
        "showDataValues":{"show":False,"color":"red","align":"top","offset":"7","fontSize":"7"},
        "xaxis":{"string":"Packet Number","min":0,"grid":True},
        "yaxis":{"string":"RTT (msec)","min":0,"grid":True},
        #"tableWidth":"1500px",
        #"tableHeight":"100px",
        #"tableStyle":{"font-size":"8px"},
        #"plotHeight":"400px",
        #"plotWidth":"500px",
        "showTable":False,
        "justification":"left",
        "data":[
            {
                "label":"RTT values from Wireshark (msec)",
                "color":"red",
                "width":1,
                "radius":0,
                "data":rttData,
                "fill": False,
                "style": "solid"
            },
            {
                "label":"RTT values from native calculation #1 (msec)",
                "color":"blue",
                "width":1,
                "radius":0,
                "data":rttData2,
                "fill": False,
                "style": "solid"
            },
        ]
    }
    myReport["Report"].append(item)

    minRTT = None
    maxRTT = None
    sumRTT = 0
    for rtt in rttData:
        if minRTT == None: minRTT = rtt
        if rtt < minRTT: minRTT = rtt
        if maxRTT == None: maxRTT = rtt
        if rtt > maxRTT: maxRTT = rtt
        sumRTT += rtt
    try:
        aveRTT = sumRTT/len(rttData)
    except:
        aveRTT = -1

    ea_root = "http://localhost:8080/"
    api_endpoint = ea_root + "createHistogramFrom"
    data = {'data':rttData,'bins':100,'minVal':minRTT,'maxVal':maxRTT}
    print("The call is to:  " + api_endpoint)
    try:
        r = requests.post(url=api_endpoint, data=data, timeout=180)
    except requests.exceptions.RequestException as error:
        print("Error: ", error)
        sys.exit(78)

    theHist = json.loads(r.text)
    #print(theHist)

    item = {
        "elementType":"section",
        "headingType":"h2",
        "headingContent":"Histogram of RTT timing based on TCP"
    }
    myReport["Report"].append(item)

    histData = theHist["histogram"]
    labels = []
    for x in histData: labels.append("{:.1f}".format(x["binLabel"]))
    data = []
    for x in histData: data.append(x["binCount"])
    item = {
        "elementType":"plot",
        "type": "bar",
        "labels": labels,
        "title": "RTT based on TCP analysis, Ave={:.2f} msec".format(aveRTT),
        "xaxis":{"string":"RTT (msec)"},
        "yaxis":{"string":"Counts"},
        "showTable": False,
        #"plotWidth":"800px",
        "data": [{
            "label": "RTT based on TCP analysis (msec)",
            "color": "blue",
            "width": 1,
            "data": data,
            "fill": -1
        }]
    }
    myReport["Report"].append(item)

    ea_root = "http://localhost:8080/"
    api_endpoint = ea_root + "createCdfFrom"
    data = {'data':rttData,'dir':1}
    print("The call is to:  " + api_endpoint)
    try:
        r = requests.post(url=api_endpoint, data=data, timeout=180)
    except requests.exceptions.RequestException as error:
        print("Error: ", error)
        sys.exit(79)

    theCdf = json.loads(r.text)
    #print(theCdf)

    item = {
        "elementType":"section",
        "headingType":"h2",
        "headingContent":"CDF of RTT timing based on TCP"
    }
    myReport["Report"].append(item)

    cdfData = theCdf["cdf"]
    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "RTT based on TCP analysis, Ave={:.2f} msec".format(aveRTT),
        "xaxis":{"string":"RTT (msec)"},
        "yaxis":{"string":"Percent"},
        "showTable": False,
        #"plotWidth":"800px",
        "data": [{
            "label": "RTT based on TCP analysis (msec)",
            "color": "green",
            "width": 1,
            "data": cdfData,
            "fill": -1
        }]
    }
    myReport["Report"].append(item)

    minMSDU = None
    maxMSDU = None
    sumMSDU = 0
    for msdu in msduLen:
        if minMSDU == None: minMSDU = msdu
        if msdu < minMSDU: minMSDU = msdu
        if maxMSDU == None: maxMSDU = msdu
        if msdu > maxMSDU: maxMSDU = msdu
        sumMSDU += msdu
    aveMSDU = sumMSDU/len(msduLen)
    if minMSDU==maxMSDU:
        minMSDU = max(1,minMSDU-5)
        maxMSDU = minMSDU + 9
    if maxMSDU-minMSDU < 9:
        maxMSDU = minMSDU + 9

    ea_root = "http://localhost:8080/"
    api_endpoint = ea_root + "createHistogramFrom"
    data = {'data':msduLen,'bins':10,'minVal':minMSDU,'maxVal':maxMSDU}
    print("The call is to:  " + api_endpoint)
    try:
        r = requests.post(url=api_endpoint, data=data, timeout=180)
    except requests.exceptions.RequestException as error:
        print("Error: ", error)
        sys.exit(78)

    theHist = json.loads(r.text)
    #print(theHist)

    item = {
        "elementType":"section",
        "headingType":"h2",
        "headingContent":"Histogram of MSDU sizes for the TCP packets"
    }
    myReport["Report"].append(item)

    histData = theHist["histogram"]
    labels = []
    for x in histData: labels.append("{:.1f}".format(x["binLabel"]))
    data = []
    for x in histData: data.append(x["binCount"])
    item = {
        "elementType":"plot",
        "type": "bar",
        "labels": labels,
        "title": "TCP packet MSDU size, Ave={:.2f} msec".format(aveMSDU),
        "xaxis":{"string":"MSDU size"},
        "yaxis":{"string":"Counts"},
        "showTable": False,
        #"plotWidth":"800px",
        "data": [{
            "label": "MSDU count for TCP packets",
            "color": "orange",
            "width": 1,
            "data": data,
            "fill": -1
        }]
    }
    myReport["Report"].append(item)

    minF2A = None
    maxF2A = None
    for f2a in frame2ackDelta:
        if minF2A == None: minF2A = f2a
        if f2a < minF2A: minF2A = f2a
        if maxF2A == None: maxF2A = f2a
        if f2a > maxF2A: maxF2A = f2a

    ea_root = "http://localhost:8080/"
    api_endpoint = ea_root + "createHistogramFrom"
    data = {'data':frame2ackDelta,'bins':100,'minVal':minF2A,'maxVal':maxF2A}
    print("The call is to:  " + api_endpoint)
    try:
        r = requests.post(url=api_endpoint, data=data, timeout=180)
    except requests.exceptions.RequestException as error:
        print("Error: ", error)
        sys.exit(78)

    theHist = json.loads(r.text)
    #print(theHist)

    item = {
        "elementType":"section",
        "headingType":"h2",
        "headingContent":"Histogram of Frame-to-ACK delta for the TCP packets"
    }
    myReport["Report"].append(item)

    histData = theHist["histogram"]
    labels = []
    for x in histData: labels.append("{:.1f}".format(x["binLabel"]))
    data = []
    for x in histData: data.append(x["binCount"])
    item = {
        "elementType":"plot",
        "type": "bar",
        "labels": labels,
        "title": "TCP frame-to-ACK delta",
        "xaxis":{"string":"Frame-to-ACK delta"},
        "yaxis":{"string":"Counts"},
        "showTable": False,
        #"plotWidth":"800px",
        "data": [{
            "label": "Frame-to-ACK delta for TCP packets",
            "color": "black",
            "width": 1,
            "data": data,
            "fill": -1
        }]
    }
    myReport["Report"].append(item)


    minS2A = None
    maxS2A = None
    for s2a in rawSN2AN:
        if minS2A == None: minS2A = s2a
        if msdu < minS2A: minS2A = s2a
        if maxS2A == None: maxS2A = s2a
        if msdu > maxS2A: maxS2A = s2a

    ea_root = "http://localhost:8080/"
    api_endpoint = ea_root + "createHistogramFrom"
    data = {'data':rawSN2AN,'bins':100,'minVal':minS2A,'maxVal':maxS2A}
    print("The call is to:  " + api_endpoint)
    try:
        r = requests.post(url=api_endpoint, data=data, timeout=180)
    except requests.exceptions.RequestException as error:
        print("Error: ", error)
        sys.exit(78)

    theHist = json.loads(r.text)
    #print(theHist)

    item = {
        "elementType":"section",
        "headingType":"h2",
        "headingContent":"Histogram of Raw sequence number to ack number for the TCP packets"
    }
    myReport["Report"].append(item)

    histData = theHist["histogram"]
    labels = []
    for x in histData: labels.append("{:.1f}".format(x["binLabel"]))
    data = []
    for x in histData: data.append(x["binCount"])
    item = {
        "elementType":"plot",
        "type": "bar",
        "labels": labels,
        "title": "TCP sequence number to ACK number delta",
        "xaxis":{"string":"Sequence Number to ACK delta"},
        "yaxis":{"string":"Counts"},
        "showTable": False,
        #"plotWidth":"800px",
        "data": [{
            "label": "Sequence Number to ACK delta for TCP packets",
            "color": "grey",
            "width": 1,
            "data": data,
            "fill": -1
        }]
    }
    myReport["Report"].append(item)

    item = {
        "elementType":"section",
        "headingType":"h2",
        "headingContent":"Location of TCP and ACK packets"
    }
    myReport["Report"].append(item)

    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "Location of TCP and ACK packets",
        "xaxis":{"string":"Packet number"},
        "yaxis":{"string":"0=ACK, 1=TCP"},
        "showTable": False,
        #"plotWidth":"800px",
        "data": [{
            "label": "Location of TCP and ACK packets",
            "color": "violet",
            "width": 0,
            "data": tcpOrAck,
            "fill": -1
        }]
    }
    myReport["Report"].append(item)

    item = {
        "elementType":"section",
        "headingType":"h2",
        "headingContent":"Compare RTT calculations, from iPerf and from PCAP"
    }
    myReport["Report"].append(item)

    allData = []
    allData.append({
        "label": "TCP/ACK time gap",
        "color": "red",
        "width": 1,
        "data": timing1,
        "fill": -1
    })
    allData.append({
        "label": "Initial RTT time",
        "color": "blue",
        "width": 1,
        "data": timing2,
        "fill": -1
    })
    if iPerf2Plots:
        for entry in iPerf2Plots:
            name,points,color = entry
            thisData = []
            for entry in points: thisData.append({"x":entry["x"]/1000,"y":entry["y"]/1000})
            allData.append({
                "label": name.replace("us","ms"),
                "color": color,
                "width": 1,
                "data": thisData,
                "fill": -1
            })

    item = {
        "elementType":"plot",
        "type": "scatter",
        "title": "Compare RTT timing values",
        "xaxis":{"string":"ACK arrival time(sec)"},
        "yaxis":{"string":"RTT (msec)"},
        "showTable": False,
        #"plotWidth":"800px",
        "data": allData
    }
    myReport["Report"].append(item)

    #======================================================

    #Also, store the JSON formatted plot, and put a link to it in ReportList.json.
    jsonName = theName + ".json"
    plotPath = storageLocation + jsonName
    f = open(plotPath, "w")
    f.write(json.dumps(myReport,indent=3))
    f.close()

    #Generate the proper html for this report    
    api_endpoint = "http://localhost:5678/jsonToHtmlReport"
    data = {'json':json.dumps(myReport,indent=4)}
    r = requests.post(url=api_endpoint,data=data)
    y = json.loads(r.text)
    html = y["html"]
    print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))

    fileName = theName + ".html"
    fullPath = storageLocation + fileName
    #print("The full path for the saved file is {}".format(fullPath))
    #Write out this html file
    f = open(fullPath, "w")
    f.write(html)
    f.close()
    print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

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

    end_time = time.time()
    print("The total execution time is {} seconds.".format(end_time-start_time))

#===
'''
#Use this for debugging.  Otherwise, comment it out.
print("This is the debugging section of createReport for TCP-RTT.  Comment it out if you are not expecting to see it.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-14_20-14_calix/1_2026-10-14_20-14_TCP-RTT/"
ea_root = "http://localhost:8080/"
pwd = "octoscope"
ssid = "Calix_AP"
main(directory_name,json_dir,ea_root,ssid,pwd)
'''
