import sys
import json
import os
import requests
import base64
import math
import time
from pathlib import Path
from datetime import datetime

#------------------------------------------------------------------------
def createHistogramFrom(data,bins,minVal,maxVal):

  histogram = []

  if len(data)<=0: return histogram

  binWidth = (maxVal-minVal)/bins

  for i in range(0,bins):
      binLabel = minVal + i*binWidth + binWidth/2
      histogram.append({"binLabel":binLabel, "binCount":0})

  for i in range(0,len(data)):
      binValue = math.floor((data[i]-minVal)/binWidth)
      if data[i]==maxVal: binValue=bins-1
      if data[i]==minVal: binValue=0
      if binValue>=0 and binValue<bins: histogram[binValue]["binCount"] +=1

  return histogram;

#------------------------------------------------------------------------
def main(directory_name,json_archive,ea_root,pcapName,ssid_decode,pwd_decode):

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

        print("Directory for this script: {}{}{}".format(cGreen,directory_name,cNormal))
        print("JSON zip file: {}{}{}".format(cGreen,json_archive,cNormal))
        print("Expert analysis location: {}{}{}".format(cGreen,ea_root,cNormal))
        print("PCAP file name: {}{}{}".format(cGreen,pcapName,cNormal))

        parts = pcapName.split("/")
        pcapFile = parts[len(parts)-1]
        theLast = parts.pop()
        pcapPath = ""
        for part in parts: pcapPath = pcapPath + part + "/"
        print("The PCAP file name is {}{}{}".format(cGreen,pcapFile,cNormal))
        print("The path to the PCAP file is {}{}{}".format(cGreen,pcapPath,cNormal))

        #Grab the directory information as created by SM.
        if directory_name[len(directory_name)-1] != "/": directory_name += "/"
        if ea_root[len(ea_root)-1] != "/": ea_root += "/"
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
                theTitle = "TWT"
                theName = theTitle.replace(" ","_")
                runNumber = "0"

        json_dir = pcapPath
        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        print('>>> createReport_main json_dir', json_dir)

        #For this test, pull the JSON information created.
        for x in os.listdir(json_dir):
                if "testresultlog" in x:
                        #print (x)
                        jsonFile = json_dir + x

        if os.path.exists(jsonFile):
          f = open(jsonFile)
          testResultLogJson = json.load(f)
          f.close
        else: testResultLogJson = {}

        timingEvents = testResultLogJson["timingEvents"]
        snifferStartTime = None
        for event in timingEvents:
          if "Sniffer Start" in event["event"]: snifferStartTime = event["time"]
        trafficStartTime = None
        for event in timingEvents:
          if "Traffic Start" in event["event"]: trafficStartTime = event["time"]
        for event in timingEvents:
          if "TWT" in event["event"]:
            firstTwtTime = event["time"]
            break
        finalTwtTime = timingEvents[len(timingEvents)-1]["time"]
        firstPacketTime = trafficStartTime - snifferStartTime
        lastPacketTime  = finalTwtTime - snifferStartTime

        #Use EA to find TWT packets
        fName = pcapFile

        #Find the total number of packets.
        baseURL = "http://localhost:8080/pcapAPI"
        api_endpoint = baseURL + "?fileName="+fName
        api_endpoint += "&pcapDir="+pcapPath
        api_endpoint += "&action=getTotalPacketCount"
        if ssid_decode and pwd_decode: api_endpoint += "&ssid={}&password={}".format(ssid_decode,pwd_decode)
        api_endpoint += "&preferTshark=false"
        print("To get total number of packets: " + api_endpoint)
        apiResponse = requests.get(api_endpoint)
        returnObject = json.loads(apiResponse.text)
        #print(returnObject)
        totalPackets = returnObject["result"]
        print('')
        print('#######################################################')	
        print("{}Total packets to analyze: {} {}".format(cGreen,totalPackets,cNormal))

        #Find the main stream
        api_endpoint = baseURL + "?fileName="+fName
        api_endpoint += "&pcapDir="+pcapPath
        api_endpoint += "&firstPacket=0"
        api_endpoint += "&lastPacket=20000"
        api_endpoint += "&action=getMainStream"
        api_endpoint += "&preferTshark=false"
        print("To get the main stream: " + api_endpoint)
        apiResponse = requests.get(api_endpoint)
        returnObject = json.loads(apiResponse.text)
        #print(returnObject)
        mainFrom = returnObject["result"]["from"]
        mainTo = returnObject["result"]["to"]
        print("{}The main data stream is from {} to {}{}".format(cGreen,mainFrom,mainTo,cNormal))

        #Grab all of the packet information
        baseURL = "http://localhost:8080/parsePCAP"
        more = True
        thePackets = []
        theStart = 0
        while more: #and len(thePackets)<100000:
                api_endpoint = baseURL + "?fileName="+fName
                api_endpoint += "&pcapDir="+pcapPath
                api_endpoint += "&preferTshark=false"
                api_endpoint += "&allowEarlyEnd=true"
                if ssid_decode and pwd_decode: api_endpoint += "&ssid={}&password={}".format(ssid_decode,pwd_decode)                
                api_endpoint += "&startAt=" + str(theStart)
                api_endpoint += "&endAt=-1"
                print('')
                print('#######################################################')
                print("Running the captured file through a PCAP analysis.  Get the packet list.")
                print("This is the API call: {}".format(api_endpoint))
                apiResponse = requests.get(api_endpoint,timeout=150)
                returnObject = json.loads(apiResponse.text)
                #print(returnObject)
                totalPackets = returnObject["totalPackets"]
                fields = returnObject["fields"]
                more = returnObject["more"]
                maxPacketProcessed = returnObject["maxPacketProcessed"]
                print("Total packets to analyze: {} ".format(totalPackets))
                print("field length: {} ".format(len(fields)))
                print("more: {} ".format(more))
                print("maxPacketProcessed: {} ".format(maxPacketProcessed))
                thePackets = thePackets + fields
                theStart = int(maxPacketProcessed) + 1

        print("There are {} packets in the packet list. ".format(len(thePackets)))

        #Verify where scriptManager is running
        api_endpoint = "http://localhost:5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        storageLocation = scriptManagerLocation + "/" + "storage/"
        fileName = theName+".html"
        fullPath = storageLocation + fileName
        #print("The full path for the saved file is {}".format(fullPath))

        #Write a report
        myReport = {}
        myReport["Title"] = theTitle
        myReport["Report"] = []

        now = datetime.now()
        item = {
          "elementType": "text",
          "text": "Report created on: {}".format(now),
        }
        myReport["Report"].append(item)

        item = {
          "elementType":"separator",
          "color":"green",
          "width":"6px"
        }
        myReport["Report"].append(item)               

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

        testname = testResultLogJson["testInfo"]["name"]
        new_testname = testname.replace("_", " ")
        #from datetime import datetime
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
                                fwString = fwString + "PAL Version :<br>" + key + " :" + palFw[key] + "<br>"
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

        ############## Location of data
        item = {
          "elementType": "section",
          "headingType": "h2",
          "headingContent":"Path to stored data",
          "text": json_dir
        }
        myReport["Report"].append(item)

        item = {
          "elementType": "section",
          "headingType": "h2",
          "headingContent":"Test Description",
          "text": testResultLogJson["testInfo"]["description"]
        }
        myReport["Report"].append(item)

        item = {"elementType": "pagebreak"}
        myReport["Report"].append(item)

        found = False
        twtFrames = []
        firstArrivalTime = thePackets[0]["arrivalTimeSeconds"]

        firstPacketNumber = None
        lastPacketNumber = None

        tableData = {"Packet Number":[],
                         "Timestamp (sec)":[],
                         "Time since traffic start (sec)":[],
                         "Transmitter Address":[],
                         "Receiver Address":[],
                         "Packet Type":[],
                         "Packet Category":[],
                         "Packet Action":[],
                         "Channel":[],
                         "MCS":[],
                         "Streams":[],
                         "Bandwidth":[],
                         "GI":[],
                         "Data Rate":[],
                         "RSSI":[],
                         "Minimum Duration":[],
                         "Minimum Duration (usec)":[],
                         "Mantissa":[],
                         "Exponent":[],
                         "Interval (usec)":[],
                         "TWT Setup Type":[]
                         }                 

        for packet in thePackets:

                if firstPacketNumber == None:
                    if (packet["arrivalTimeSeconds"] - firstArrivalTime) >= firstPacketTime: firstPacketNumber = packet["packetNumber"]
                if lastPacketNumber == None:
                    if (packet["arrivalTimeSeconds"] - firstArrivalTime) >= lastPacketTime: lastPacketNumber = packet["packetNumber"]

                if packet["packetType"] != "Action frames": continue
                if packet["packetCategory"] != "TWT": continue

                found = True
                twtFrames.append(packet)
                print("Packet Number: {}, Timestamp (sec): {}, Time since traffic start (sec): {}, Tx: {}, Rx: {}, Type: {}, Category: {}, Action: {}, Channel: {}, MCS: {}, NSS: {}, BW: {}, GI: {}, Rate: {}, RSSI: {}"
                      .format(
                          packet["packetNumber"],
                          packet["arrivalTimeSeconds"],
                          1*packet["arrivalTimeSeconds"] - trafficStartTime,
                          packet["transmitterAddress"],
                          packet["receiverAddress"],
                          packet["packetType"],
                          packet["packetCategory"],
                          packet["packetAction"],
                          packet["Channel"],
                          packet["MCS"],
                          packet["NSS"],
                          packet["BW"],
                          packet["GI"],
                          packet["dataRate"],
                          packet["RSSI"]
                      ))
                tableData["Packet Number"].append(packet["packetNumber"])
                tableData["Timestamp (sec)"].append(packet["arrivalTimeSeconds"])
                tableData["Time since traffic start (sec)"].append( round(1*packet["arrivalTimeSeconds"]-trafficStartTime,1))
                tableData["Transmitter Address"].append(packet["transmitterAddress"])
                tableData["Receiver Address"].append(packet["receiverAddress"])
                tableData["Packet Type"].append(packet["packetType"])
                tableData["Packet Category"].append(packet["packetCategory"])
                tableData["Packet Action"].append(packet["packetAction"])
                tableData["Channel"].append(packet["Channel"])
                tableData["MCS"].append(packet["MCS"])
                tableData["Streams"].append(packet["NSS"])
                tableData["Bandwidth"].append(packet["BW"])
                tableData["GI"].append(packet["GI"])
                tableData["Data Rate"].append(packet["dataRate"])
                tableData["RSSI"].append(packet["RSSI"])
                if "twt" in packet:
                    print("        Min Duration: {}, Min Duration (usec): {}, mantissa: {}, exponent: {}, Interval (usec): {}"
                          .format(
                              packet["twt"]["minDuration"],
                              packet["twt"]["minDuration"]*256,
                              packet["twt"]["mantissa"],
                              packet["twt"]["exponent"],
                              packet["twt"]["interval_usec"]
                          ))
                    tableData["Minimum Duration"].append(packet["twt"]["minDuration"])            
                    tableData["Minimum Duration (usec)"].append(packet["twt"]["minDuration"]*256)            
                    tableData["Mantissa"].append(packet["twt"]["mantissa"])            
                    tableData["Exponent"].append(packet["twt"]["exponent"])            
                    tableData["Interval (usec)"].append(packet["twt"]["interval_usec"])
                    tableData["TWT Setup Type"].append(packet["twt"]["setupType"])
                else:
                    tableData["Minimum Duration"].append("N/A")            
                    tableData["Minimum Duration (usec)"].append("N/A")            
                    tableData["Mantissa"].append("N/A")            
                    tableData["Exponent"].append("N/A")            
                    tableData["Interval (usec)"].append("N/A")
                    tableData["TWT Setup Type"].append("N/A")


        item = {
          "elementType": "section",
          "headingType": "h2",
          "headingContent":"TWT signaling information"
        }
        myReport["Report"].append(item)

        if found:
          print("{}TWT signaling found.{}".format(cGreen,cNormal))
          item = {
                "elementType": "text",
                "text": "\nTWT signaling found."
          }        
        else:
          print("{}No TWT signaling messages found.{}".format(cRed,cNormal))
          item = {
                "elementType": "text",
                "text": "\nNo TWT signaling messages found."
          }
        myReport["Report"].append(item)

        item = {
          "elementType": "section",
          "headingType": "h3",
          "headingContent":"TWT-related signaling messages"
        }
        myReport["Report"].append(item)

        allData = []
        for td in tableData:
          thisObject = {}
          thisObject["label"] = td
          thisObject["units"] = ""
          thisObject["justification"] = ""
          thisData = []
          for entry in tableData[td]: thisData.append(entry)
          thisObject["data"] = thisData
          allData.append(thisObject)
        item = {
          "elementType": "table",
          "type": "table",
          "title": "",
          #"tableWidth": "700px",
          "data": allData
        }
        myReport["Report"].append(item)

        if found or True:

                if found:
                    lowTime = twtFrames[0]["arrivalTimeSeconds"]
                    hiTime  = twtFrames[len(twtFrames)-1]["arrivalTimeSeconds"]
                    lowNum  = twtFrames[0]["packetNumber"]
                    hiNum   = twtFrames[len(twtFrames)-1]["packetNumber"]
                    if firstPacketNumber != None:
                        if firstPacketNumber < lowNum: lowNum = firstPacketNumber
                    if lastPacketNumber != None:
                        if lastPacketNumber > hiNum:  hiNum  = lastPacketNumber
                        
                else:  #No TWT packets found, but allow the code to make some plots anyway.
                    #Find the first packet after the packets start
                    for i in range(0,len(thePackets)):
                        if thePackets[i]["arrivalTimeSeconds"]>trafficStartTime: break
                    trafficStartPacket = i
                    for i in range(trafficStartPacket,len(thePackets)):
                        if thePackets[i]["arrivalTimeSeconds"]>firstTwtTime: break
                    firstTwtPacket = i
                    for i in range(firstTwtPacket,len(thePackets)):
                        if thePackets[i]["arrivalTimeSeconds"]>finalTwtTime: break
                    finalTwtPacket = i

                    print("Traffic Start Packet is {}, and First TWT packet is {} and Last TWT packet is {}, out of {}".format(trafficStartPacket,firstTwtPacket,finalTwtPacket,len(thePackets)))
                    
                    #lowTime = thePackets[trafficStartPacket]["arrivalTimeSeconds"]
                    lowTime = thePackets[firstTwtPacket]["arrivalTimeSeconds"]
                    hiTime  = thePackets[finalTwtPacket]["arrivalTimeSeconds"]
                    #lowNum  = thePackets[trafficStartPacket]["packetNumber"]
                    lowNum  = thePackets[firstTwtPacket]["packetNumber"]
                    hiNum   = thePackets[finalTwtPacket]["packetNumber"]

                print("Analyzing packet arrivals from packet {} to packet {}".format(lowNum,hiNum))

                dataTimes = []
                for p in range(lowNum,hiNum):
                    packet = thePackets[p]
                    if "transmitterAddress" not in packet: continue
                    if packet["transmitterAddress"] != mainFrom: continue
                    if "receiverAddress" not in packet: continue
                    if packet["receiverAddress"] != mainTo: continue
                    if "packetType" not in packet: continue
                    isData = False
                    if "data" in packet["packetType"].lower(): isData = True
                    if "tcp" in packet["packetType"].lower(): isData = True
                    if "udp" in packet["packetType"].lower(): isData = True
                    if not isData: continue
                    #dataTimes.append(packet["arrivalTimeSeconds"] - firstArrivalTime)
                    dataTimes.append(packet["arrivalTimeSeconds"] - trafficStartTime)

                item = {
                  "elementType": "section",
                  "headingType": "h2",
                  "headingContent":"Packet Arrival per Unit Time"
                }
                myReport["Report"].append(item)

                #print(dataTimes)
                print("Between packet {} and packet {} I have found {} to use for the timing plot.".format(lowNum,hiNum,len(dataTimes)))
                if len(dataTimes) > 0:
                  minVal = dataTimes[0]
                  maxVal = dataTimes[len(dataTimes)-1]

                  timeInSeconds = maxVal - minVal
                  #bins = int(timeInSeconds * 1000) + 1
                  bins = 1000

                  print("Creating the histogram from {} data points.".format(len(dataTimes)))
                  histogram = createHistogramFrom(dataTimes,bins,minVal,maxVal)

                  #print(histogram)

                  labels = []
                  for item in histogram: labels.append(str(format(item["binLabel"],".2f")))
                  theData = []
                  for item in histogram: theData.append(item["binCount"])

                  thisPlot = {}
                  thisPlot["elementType"] = "plot"
                  thisPlot["type"] = "bar"
                  thisPlot["title"] = "Packet arrival per unit time"
                  thisPlot["labels"] = labels
                  thisPlot["xaxis"] = {"string":"Time"}
                  thisPlot["yaxis"] = {"string":"Packet count"}
                  thisPlot["showTable"] = False
                  thisPlot["data"] = [{
                      "label": "Packet arrival rate vs. Time",
                      "color": "blue",
                      "width": 1,
                      "data": theData,
                      "fill": -1
                  }]
                  myReport["Report"].append(thisPlot)

        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"File: " + json_archive
        }
        myReport["Report"].append(item)

        print("Opening data json data from {}".format(json_archive))
        with open(json_archive, "rb") as f:
            bytes = f.read()
            encoded = base64.b64encode(bytes)
            api_endpoint = ea_root + "zip2csv"
            data = {'zip':encoded}
            theResponse = requests.post(url=api_endpoint, data=data)
            theJson = json.loads(theResponse.text)

        csv = theJson["csv"]

        #Get basic test results information
        api_endpoint = ea_root + "getStats"
        data = {
            'csv':csv,
            'filter':'counts',
        }
        try:
            r = requests.post(url=api_endpoint, data=data, timeout=5)
        except requests.exceptions.RequestException as error:
            info("Error: ", error)
            sys.exit(44)

        y = json.loads(r.text)
        print("Basic JSON stats: {}".format(json.dumps(y["filteredData"])))                              
        tpName = y["filteredData"]["trafficPairs"]["map"]["0"]
        #print(tpName)
        if y["filteredData"]["pingPairs"]["length"] > 0:
            ppName = y["filteredData"]["pingPairs"]["map"]["0"]
            #print(ppName)        

        # Analyze the CSV file
        print("Objectifying...")
        api_endpoint = ea_root + "objectify"
        data = {'csv':csv}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)

        headers = theJson["headers"]
        dataSet = theJson["dataSet"]
        if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

        print("Crunching...")
        api_endpoint = ea_root + "crunch"
        run = 1
        data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        if "error" in theJson: info("crunch: This data returned an error: {}".format(theJson["error"]))
        analyzedData = theJson["crunchedData"]
        theNotes = theJson["Notes"]

        numberOfPalEndpoints = len(analyzedData)
        if numberOfPalEndpoints == 0:
            info("No pal Endpoints found")
            sys.exit(24)
        else:
            thisData = analyzedData[0]
            numTraffic = thisData[0]["tpaircount"]
            _analyzedData = thisData        

        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Throughput time series",
            "text": "All measured throughput values."
        }
        myReport["Report"].append(item)

        timeSeries = []
        maxY = None
        for data in dataSet:
            try:thisTime = float(data["Time [ms]"])
            except:continue
            try:thisThroughput = float(data[tpName + " Throughput [Mbps]"])
            except:continue
            timeSeries.append({"x":thisTime/1000,"y":round(thisThroughput,2)})
            if(maxY==None): maxY = thisThroughput
            maxY = max(maxY,thisThroughput)

        allData = []
        allData.append({
          "label":"Throughput",
          "color":"blue",
          "width":1,
          "radius":0,
          "data": timeSeries,
          "fill": -1,
          "style": "solid"
        })
        for event in timingEvents:
          if event["event"] == "TWT Command":
            aLine = {"label": "TWT command",
                     "color": "red",
                     "width": 1,
                     "radius": 0,
                     "data": [{"x":event["time"]-trafficStartTime,"y":0},{"x":event["time"]-trafficStartTime,"y":maxY}],
                     "fill": -1,
                     "style": "solid"
                     }
            allData.append(aLine)

        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "Throughput time plot",
            "xaxis":{"string":"Time (sec)"},
            "yaxis":{"string":"Throughput (Mbps)"},
            "showTable": False,
            "plotWidth":"800px",
            "data":allData
        }
        myReport["Report"].append(item)

        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"Specific TWT messages sent"
        }
        myReport["Report"].append(item)

        teData = {"time":[], "cmd":[]}
        for event in timingEvents:
          if event["event"] == "TWT Command":
            t = event["time"]-trafficStartTime
            teData["time"].append(round(t,1))
            cmd = event["command"]
            loc = cmd.find("sudo -S")
            loc +=7
            substr = cmd[0:loc]
            show = cmd.replace(substr,"")
            teData["cmd"].append(show)

        allData = []
        for te in teData:
          thisObject = {}
          if te=="time": thisObject["label"] = "Time since traffic start (sec)"
          if te=="cmd": thisObject["label"] = "TWT command"                                   
          thisObject["units"] = ""
          thisObject["justification"] = ""
          thisData = []
          for entry in teData[te]: thisData.append(entry)
          thisObject["data"] = thisData
          allData.append(thisObject)
        item = {
          "elementType": "table",
          "type": "table",
          "title": "",
          "tableWidth": "700px",
          "data": allData
        }
        myReport["Report"].append(item)


        #==============================================================
        #==============================================================
        #==============================================================

        #Store the JSON formatted plot, and put a link to it in ReportList.json.
        jsonName = theName+".json"
        plotPath = storageLocation + jsonName
        f = open(plotPath, "w")
        f.write(json.dumps(myReport,indent=3))
        f.close()
        #.........
        jsonPath = storageLocation + "ReportList.json"
        f = open(jsonPath, "r")
        try:    currentList = json.load(f)
        except: currentList = {}
        f.close()
        currentList[fileName] = plotPath
        f = open(jsonPath, "w")
        f.write(json.dumps(currentList,indent=3))
        f.close()
        #print("Updated the current list to {}".format(currentList))

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
                    "label": "Report for " + theTitle,
                    "withTitle": theTitle
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'TestReport-'+theName+'.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

#For debugging only
'''
print("This is the debug code in TWT's createReport.  Comment it out if you don't expect to see it.")
directory_name = "./"
ea_root = "http://localhost:8080"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-16_20-49_calix/1_2026-10-16_20-49_TWT/"
json_archive = json_dir + "2026-10-16_20-52_calix_calix_TWT.zip"
pcapName =     json_dir + "2026-10-16_20-52_calix_calix_TWT_capture.pcap"
main(directory_name,json_archive,ea_root,pcapName,"Calix_AP","octoscope")
'''
