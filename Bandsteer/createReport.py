import sys
import json
import os
import requests
import base64
from pathlib import Path
#import boto3
from datetime import datetime

#######################################################################
def info(text,another=None):
    now = datetime.now()
    if(another==None):
        print("[INFO]: " +"{"+str(now)+"}; "+ text)
    else:
        print("[INFO]: " +"{"+str(now)+"}; "+ text + " , " + str(another))

def formatMAC(mac):
    fMAC = mac
    fMAC = fMAC.replace(".",":")
    fMAC = fMAC.upper()
    if(fMAC[len(fMAC)-1]==":"): fMAC = fMAC[0:len(fMAC)-1]
    fMAC = fMAC.strip()
    return fMAC

def getCount(pcapFileName,json_dir,ea_root):
        api_endpoint = ea_root + "pcapAPI?action=getTotalPacketCount&fileName={}&pcapDir={}".format(pcapFileName,json_dir)
        print("Calling {}".format(api_endpoint))
        theResponse = requests.get(url=api_endpoint)
        theJson = json.loads(theResponse.text)
        totalCount = theJson["result"]
        return totalCount

def getPacketTypes(pcapFileName,json_dir,ea_root,typeArray,useMax):
        print('\n### Getting data of type(s): {}'.format(typeArray))
        filterList = ""
        for entry in typeArray: filterList += "{},".format(entry)
        filterList = filterList[:-1]
        api_endpoint = ea_root + "pcapAPI?action=getDataOfType&filters={}&fileName={}&pcapDir={}&lastPacket={}".format(filterList,pcapFileName,json_dir,useMax)
        print("Calling {}".format(api_endpoint))
        theResponse = requests.get(url=api_endpoint)
        theJson = json.loads(theResponse.text)
        return theJson["result"]

def getMainStream(pcapFileName,json_dir,ea_root,useMax):
        print('\n### Getting main streams')
        api_endpoint = ea_root + "pcapAPI?action=getMainStream&fileName={}&pcapDir={}&lastPacket={}".format(pcapFileName,json_dir,useMax)
        print("Calling {}".format(api_endpoint))
        theResponse = requests.get(url=api_endpoint)
        theJson = json.loads(theResponse.text)
        return theJson["result"]

def getAttenBreaks(dataSet,epIndex,stepSize):
    headerName = "Pal Endpoint {} Control RSSI [dBm] Mean".format(epIndex)

    rollingMedians = []
    size = 3
    nowAt = 0
    while nowAt < len(dataSet):
        goTo = min( len(dataSet), nowAt + (size-1) )
        points = []
        for i in range (nowAt,goTo):
            try: points.append(int(dataSet[i][headerName]))
            except: message = "Cannot use {}".format(dataSet[i][headerName])
        rollingMedians.append({"time":dataSet[i]["Time [ms]"]/1000, "median":getMedian(points)})
        nowAt = nowAt + 1
    #print(json.dumps(rollingMedians,indent=3))

    breaks = [rollingMedians[0]["time"]]
    setPoint = rollingMedians[0]["median"]
    #print("Set point {} at {}".format(setPoint,breaks[0]))
    for entry in rollingMedians:
        if abs(entry["median"]-setPoint) >= stepSize:
            breaks.append(entry["time"])
            setPoint = entry["median"]
            #print("Set point {} at {}".format(setPoint,breaks[len(breaks)-1]))            
    useBreaks = []
    for i in range (0,len(breaks)-1):
        if breaks[i+1]-breaks[i] > 1: useBreaks.append(int(breaks[i]))
    useBreaks.append(int(breaks[len(breaks)-1]))
    #print(breaks)
    #print(useBreaks)

    gapSize = 0
    for i in range (0,len(useBreaks)-1): gapSize += useBreaks[i+1]-useBreaks[i]
    gapSize /= (len(useBreaks)-1)
    #print(gapSize)

    estimatedBreaks = [useBreaks[0]]
    for entry in useBreaks: estimatedBreaks.append( int((estimatedBreaks[len(estimatedBreaks)-1] + gapSize)) )
    estimatedBreaks.append(int(dataSet[len(dataSet)-1]["Time [ms]"]/1000))
    #print(estimatedBreaks)
    for thisBreak in estimatedBreaks:
        found = False
        for thatBreak in useBreaks:
            if abs(thatBreak-thisBreak)<=10:
                found = True
                break
        if not found: useBreaks.append(thisBreak)
    useBreaks.sort()
    #print(useBreaks)

    return useBreaks

def getMedian(points):
    if len(points)==0: return 0
    sum = 0
    for point in points: sum += point
    return sum/len(points)
                                
def main(directory_name,json_dir,ea_root):

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
                theTitle = "No Name Found"
                theName = theTitle.replace(" ","_")
                runNumber = "0"

        #print("Command line part is " + CL)

        # Find the Script Manager hostname. Need this if remotely logged into SM
        if directoriesJson:
                if "scriptManagerLocation" in directoriesJson:
                        hostIpAddress = directoriesJson["scriptManagerLocation"]["hostname"]
                        print('>>> hostIpAddress: ', hostIpAddress)
                else:
                        hostIpAddress = 'localhost'
                        message = 'Cannot find scriptManagerLocation in directories.json. Setting hostIpAddress = localhost.'
                        failHandler('Mainscript',message, errCode=0)

        if directory_name[len(directory_name)-1] != "/": directory_name += "/"
        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        info('>>> createReport_main json_dir', json_dir)
        #Get all of the zip files in the json directory
        theZips = []
        for x in os.listdir(json_dir):
                if ".zip" in x:
                        #info(x)
                        if "CSV" in x: continue
                        if "JSON" in x: continue
                        theZips.append(json_dir + x)
                        #if "CSV" not in x: theZips.append(json_dir + x)

        print(">>> theZips: ", theZips)

        #theTitle = "Simple Automation Example"
        #if len(CL) > 0: theTitle += " (" + CL + ")"        

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

        theText = "In this test run traffic between the device under test (DUT) and a STApal used as a station (STA).<br>"
        theText += "Ramp the attenuator(s) between the two in an attempt to force the STA to move from one band to another, possibly with steering.<br/>"
        theText += "Make some plots of time series data with overlays of the BSSID information, so you can see what happens to the various metrics as the band changes."

        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Overview",
                "text": theText
        }
        myReport["Report"].append(item)

        #Do the whole analysis part using the data in this zip file.
        #fileName = theZips[0]
        for fileName in theZips:
                print('>>> createReport_main Using file %s.' % fileName)
                parts = fileName.split("/")
                item = {
                    "elementType": "section",
                    "headingType": "h2",
                    "headingContent":"File: " + parts[len(parts)-1]
                }
                myReport["Report"].append(item)

                with open(fileName, "rb") as f:
                        bytes = f.read()
                        encoded = base64.b64encode(bytes)
                        #info(encoded)
                        #api_endpoint = "http://"+hostIpAddress+":8080/zip2csv"
                        api_endpoint = ea_root + "zip2csv"
                        print('\n>>> api_endpoint: ', api_endpoint)
                        data = {'zip':encoded}
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)
                        #print('\n>>> theJson: ', theJson)

                f = open(directory_name+'csv.csv', 'w')
                f.write(theJson["csv"])
                f.close()

                # Analyze the CSV file
                print('\n### Analyzing CSV file')
                csv_path = directory_name+'csv.csv'
                csv = Path(csv_path).read_text()
                #location = "local"
                api_endpoint = ea_root + "objectify"
                data = {'csv':csv}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)
                #print('\n>>> theJson: ', theJson)
                headers = theJson["headers"]
                dataSet = theJson["dataSet"]
                if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

                print('\n### Running crunch')
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
                if numberOfPalEndpoints == 0:
                    info("No pal Endpoints found")
                    sys.exit(24)
                else:
                    thisData = analyzedData[0]
                    numTraffic = thisData[0]["tpaircount"]
                    if numTraffic == 1:
                        _analyzedData = thisData
                    else:
                        info("Why do you have {} traffic pairs?".format(numTraffic))
                        sys.exit(25)

                print('\n### Running getStats')
                #Get basic test results information
                #api_endpoint = "http://"+hostIpAddress+":8080/getStats"
                api_endpoint = ea_root + "getStats"
                data = {
                    'csv':csv,
                    'filter':'counts',
                    #'subFilter':'mean',
                    #'endpoint':-1,
                    #'pingPair':1,
                    #'trafficPair':-1,
                    #'attenuation':1,
                    #'position':-1,
                    #'customPercent':5
                }

                try:
                    r = requests.post(url=api_endpoint, data=data, timeout=5)
                except requests.exceptions.RequestException as error:
                    info("Error: ", error)
                    sys.exit(44)

                y = json.loads(r.text)
                print('\n>>> y: ', y)
                #info(json.dumps(y,indent=4))
                tpName = y["filteredData"]["trafficPairs"]["map"]["0"]
                #info(tpName)
                if y["filteredData"]["pingPairs"]["length"] > 0:
                    ppName = y["filteredData"]["pingPairs"]["map"]["0"]
                    #info(ppName)
                epMap = y["filteredData"]["palEndpoints"]["map"]
                for index in epMap:
                    epName = epMap[index]
                    if "sn" not in epName: break                        
                epIndex = str( int(index)+1 )
                
                f = open(directory_name + "params_test.json")
                paramsDict = json.load(f)
                f.close()
                qaStart = paramsDict["quadAttenStart"]["val"]
                qaStop = paramsDict["quadAttenStop"]["val"]
                qaStep = paramsDict["step"]["val"]
                qaDirection = 1
                if qaStop < qaStart: qaDirection = -1
                low = min(qaStart,qaStop)
                hi = max(qaStart,qaStop)
                val = low
                qaValues = []
                while val <= hi:
                    qaValues.append(val)
                    val += qaStep
                if qaValues[len(qaValues)-1] != hi: qaValues.append(hi)
                if qaDirection < 0: qaValues.reverse()
                #print("Quad-attens to be stepped using these values: {}".format(qaValues))
                print("There should be {} attenuation regions.".format(len(qaValues)))
                
                keepGoing = True
                smooth = 0
                while keepGoing:   #Why +1?  Because there are N+1 borders on N regions.
                    smooth += 1
                    breaks = getAttenBreaks(dataSet,epIndex,smooth)
                    print("Smoothing with size {} gave {} breaks".format(smooth,len(breaks)))
                    keepGoing = len(breaks) > len(qaValues)+1
                if len(breaks) < len(qaValues)+1:
                    smooth -= 1
                    breaks = getAttenBreaks(dataSet,epIndex,smooth)
                    print("Smoothing with size {} gave {} breaks".format(smooth,len(breaks)))
                #print("Ended up smoothing at size of {}".format(smooth))
                #print(breaks)
                
                attenuationRegions = {}
                for i in range (0,len(qaValues)):
                    attenuationRegions[qaValues[i]] = {"start":breaks[i],"end":breaks[i+1]}
                print(attenuationRegions)

                direction = "dl"
                getThe = "RX"
                if "ToServer" in tpName:
                    direction = "ul"
                    getThe = "TX"
                
                for ar in attenuationRegions:
                    throughputs = []
                    ctrlRSSIs = []
                    streams = []
                    MCSs = []
                    BWs = []
                    for data in dataSet:
                        thisTime = data["Time [ms]"]/1000
                        if thisTime >= attenuationRegions[ar]["start"] and thisTime<= attenuationRegions[ar]["end"]:
                            try: thisValue = float(data["{} Throughput [Mbps]".format(tpName)])
                            except: thisValue = None
                            if thisValue: throughputs.append(thisValue)
                            
                            try: thisValue = float(data["Pal Endpoint {} Control RSSI [dBm] Mean".format(epIndex)])
                            except: thisValue = None
                            if thisValue: ctrlRSSIs.append(thisValue)
                            
                            try: thisValue = int(data["Pal Endpoint {} {} Nss Mode".format(epIndex,getThe)])
                            except: thisValue = None
                            if thisValue: streams.append(thisValue)
                            
                            try: thisValue = int(data["Pal Endpoint {} {} MCS Mode".format(epIndex,getThe)])
                            except: thisValue = None
                            if thisValue: MCSs.append(thisValue)
                            
                            try: thisValue = int(data["Pal Endpoint {} {} Bandwidth [MHz] Mode".format(epIndex,getThe)])
                            except: thisValue = None
                            if thisValue: BWs.append(thisValue)

                    if len(throughputs)==0: continue
                    avg = 0
                    for val in throughputs: avg += val
                    avg /= len(throughputs)
                    attenuationRegions[ar]["throughput"] = avg
                    avg = 0
                    for val in ctrlRSSIs: avg += val
                    avg /= len(ctrlRSSIs)
                    attenuationRegions[ar]["ctrlRSSI"] = avg
                    counts = {}
                    for val in streams:
                        if val not in counts: counts[val] = 1
                        else: counts[val] += 1
                    sorted_items = sorted(counts.items(), key=lambda kv: (kv[1],kv[0]))
                    attenuationRegions[ar]["streams"] = sorted_items[0][0]
                    counts = {}
                    for val in MCSs:
                        if val not in counts: counts[val] = 1
                        else: counts[val] += 1
                    sorted_items = sorted(counts.items(), key=lambda kv: (kv[1],kv[0]))
                    attenuationRegions[ar]["MCS"] = sorted_items[0][0]
                    counts = {}
                    for val in BWs:
                        if val not in counts: counts[val] = 1
                        else: counts[val] += 1
                    sorted_items = sorted(counts.items(), key=lambda kv: (kv[1],kv[0]))
                    attenuationRegions[ar]["BW"] = sorted_items[0][0]
                    
                #print(attenuationRegions)
                
                item = {
                    "elementType": "section",
                    "headingType": "h3",
                    "headingContent":"Throughput vs Attenuation",
                    "text": "Throughput vs. attenuation, where each attenuation step is the throughput averaged over the duration time."
                }
                myReport["Report"].append(item)

                rvrPlot = []
                for atten in attenuationRegions:
                    try:thisAttenuation = atten
                    except:continue
                    try:thisThroughput = attenuationRegions[atten]["throughput"]
                    except:continue
                    try:rvrPlot.append({"x":thisAttenuation,"y":round(thisThroughput,2)})
                    except: rvrPlot.append({"x":thisAttenuation,"y":round(0,2)})

                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "Rate vs. Attenuation plot",
                    "xaxis":{"string":"Attenuation (dB)"},
                    "yaxis":{"string":"Throughput (Mbps)"},
                    "showTable": True,
                    "plotWidth":"800px",
                    "data":[
                    {
                        "label":"Throughput",
                        "color":"blue",
                        "width":1,
                        "radius":0,
                        "data": rvrPlot,
                        "fill": -1,
                        "style": "solid"
                    }
                    ]	    
                }
                #print('\n>>> rvrPlot: ', rvrPlot)
                myReport["Report"].append(item)

                #iperf2 data if you have any
                iHaveIperf2 = False
                iperf2Plot = []
                for data in _analyzedData:
                    try:thisAttenuation = data["attenuation"]
                    except:continue
                    try:thisLatency = data["iPerf2Latency"]["Mean"]["mean"]
                    except:continue
                    try:
                        iperf2Plot.append({"x":thisAttenuation,"y":round(thisLatency,2)})
                        iHaveIperf2=True
                    except: iperf2Plot.append({"x":thisAttenuation,"y":round(0,2)})
                if iHaveIperf2:
                    item = {
                        "elementType": "section",
                        "headingType": "h3",
                        "headingContent":"iPerf2 Latency vs Attenuation",
                        "text": "Iperf2 latency vs. attenuation, where each attenuation step is the iperf2 Mean latency averaged over the duration time."
                    }
                    myReport["Report"].append(item)

                    item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "iPerf2 Latency vs. Attenuation plot",
                        "xaxis":{"string":"Attenuation (dB)"},
                        "yaxis":{"string":"iPerf2 Mean Latency (msec)"},
                        "showTable": True,
                        "plotWidth":"800px",
                        "data":[
                        {
                            "label":"Latency",
                            "color":"blue",
                            "width":1,
                            "radius":0,
                            "data": iperf2Plot,
                            "fill": -1,
                            "style": "solid"
                        }
                        ]	    
                    }
                    myReport["Report"].append(item)


                #Ping data, if you've got any.
                iHavePing = False
                pingPlot = []
                for data in _analyzedData:
                    try:thisAttenuation = data["attenuation"]
                    except:continue
                    try:thisLatency = data["pingLatency"]["mean"]
                    except:continue
                    try:
                        pingPlot.append({"x":thisAttenuation,"y":round(thisLatency,2)})
                        iHavePing=True
                    except: pingPlot.append({"x":thisAttenuation,"y":round(0,2)})

                if iHavePing:
                    item = {
                        "elementType": "section",
                        "headingType": "h3",
                        "headingContent":"Ping Latency vs Attenuation",
                        "text": "Ping latency vs. attenuation, where each attenuation step is the ping latency averaged over the duration time."
                    }
                    myReport["Report"].append(item)

                    item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "Ping Latency vs. Attenuation plot",
                        "xaxis":{"string":"Attenuation (dB)"},
                        "yaxis":{"string":"Ping Latency (msec)"},
                        "showTable": True,
                        "plotWidth":"800px",
                        "data":[
                        {
                            "label":"Latency",
                            "color":"blue",
                            "width":1,
                            "radius":0,
                            "data": pingPlot,
                            "fill": -1,
                            "style": "solid"
                        }
                        ]	    
                    }
                    myReport["Report"].append(item)


                item = {
                    "elementType": "section",
                    "headingType": "h3",
                    "headingContent":"Throughput vs Control RSSI",
                    "text": "Throughput vs. control RSSI, where each attenuation step is the throughput averaged over the duration time, and the RSSI of the control packets linearly averaged."
                }
                myReport["Report"].append(item)

                rvrPlot = []
                for atten in attenuationRegions:
                    try:thisRSSI = attenuationRegions[atten]["ctrlRSSI"]
                    except:continue
                    try:thisThroughput = attenuationRegions[atten]["throughput"]
                    except:continue
                    try:rvrPlot.append({"x":thisRSSI,"y":round(thisThroughput,2)})
                    except: rvrPlot.append({"x":thisRSSI,"y":round(0,2)})

                tolPrvr = []
                for i in range(len(rvrPlot),0,-1): tolPrvr.append(rvrPlot[i-1])

                plotData = [
                {
                    "label":"Throughput",
                    "color":"green",
                    "width":1,
                    "radius":0,
                    "data": rvrPlot,
                    "fill": -1,
                    "style": "solid"
                }
                ]

                #Let's do an analysis of the "expected" throughput at each point.
                expected = []
                standards = ["11ax", "11ac", "11n"]
                for standard in standards:
                    thisObject = {"standard":standard}
                    thisData = []
                    if standard == "11ax":
                        GI="800"
                        scale=0.75
                    if standard == "11ac":
                        GI="400"
                        scale=0.70
                    if standard == "11n":
                        GI="400"
                        scale=0.60
                    thisObject["scale"] = scale
                    for atten in attenuationRegions:
                        try:thisRSSI = attenuationRegions[atten]["ctrlRSSI"]
                        except:continue
                        try:thisBW = attenuationRegions[atten]["BW"]
                        except:continue
                        try:thisNSS = attenuationRegions[atten]["streams"]
                        except:continue
                        api_endpoint = ea_root + "getMCS" + "?standard="+standard + "&BW="+str(thisBW) + "&streams="+str(thisNSS) + "&RSSI="+str(thisRSSI)
                        theResponse = requests.get(url=api_endpoint)
                        theJson = json.loads(theResponse.text)
                        thisMCS = theJson["MCS"]
                        api_endpoint = ea_root + "getDRate" + "?standard="+standard + "&BW="+str(thisBW) + "&streams="+str(thisNSS) + "&MCS="+str(thisMCS) + "&GI="+GI
                        theResponse = requests.get(url=api_endpoint)
                        theJson = json.loads(theResponse.text)
                        thisRate = theJson["rate"]
                        if thisRate>=0: thisThroughput = thisRate*scale
                        else: thisThroughput = -1
                        thisItem = {"rssi":thisRSSI, "BW":thisBW, "NSS":thisNSS, "MCS":thisMCS, "rate":thisRate, "throughput":thisThroughput}
                        #if thisRate>=0: thisData.append(thisItem)
                        thisData.append(thisItem)
                    thisObject["data"]=thisData
                    expected.append(thisObject)
                #info(json.dumps(expected,indent=3))

                idx = -1
                for item in expected:
                    if len(item["data"])==0: continue
                    idx += 1
                    label = "Expected throughput for 802." + item["standard"] + " at " + str(item["scale"]*100) + "% of the data rate"
                    color = colors[idx % len(colors) + 6]
                    thisData = []
                    for result in item["data"]:
                        thisData.append({"x":result["rssi"],"y":round(result["throughput"],2)})
                    plotData.append({"label":label,"color":color,"width":1,"radius":0,"data":thisData,"fill": -1,"style": "short-dash"})

                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "Rate vs. Control RSSI plot",
                    "xaxis":{"string":"Control RSSI (dBm)","reverse":True},
                    "yaxis":{"string":"Throughput (Mbps)"},
                    "showTable": True,
                    "plotWidth":"800px",
                    "data": plotData
                }
                myReport["Report"].append(item)

                if iHavePing:
                    item = {
                        "elementType": "section",
                        "headingType": "h3",
                        "headingContent":"Ping Latency vs Control RSSI",
                        "text": "Ping latency vs. control RSSI, where each attenuation step is the ping latency averaged over the duration time, and the RSSI of the control packets linearly averaged."
                    }
                    myReport["Report"].append(item)

                    pingPlot = []
                    for data in _analyzedData:
                        try:thisRSSI = data["rssi"]["controlMean"]
                        except:continue
                        try:thisLatency = data["pingLatency"]["mean"]
                        except:continue
                        try:pingPlot.append({"x":thisRSSI,"y":round(thisLatency,2)})
                        except: rvrPlot.append({"x":thisRSSI,"y":round(0,2)})

                    plotData = [
                    {
                        "label":"Throughput",
                        "color":"green",
                        "width":1,
                        "radius":0,
                        "data": pingPlot,
                        "fill": -1,
                        "style": "solid"
                    }
                    ]	   
                    item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "Ping Latency vs. Control RSSI plot",
                        "xaxis":{"string":"Control RSSI (dBm)","reverse":True},
                        "yaxis":{"string":"Ping Latency (msec)"},
                        "showTable": True,
                        "plotWidth":"800px",
                        "data": plotData
                    }
                    myReport["Report"].append(item)

                #### A bunch of time series plots

                item = {
                    "elementType": "section",
                    "headingType": "h3",
                    "headingContent":"BSSID time series",
                    "text": "BSSID per reporting interval."
                }
                myReport["Report"].append(item)

                BSSID_map = {}
                index = 0
                for data in dataSet:
                    thisVal = data["Pal Endpoint 1 BSSID"]
                    if len(thisVal)>10 and thisVal not in BSSID_map:
                        BSSID_map[thisVal] = index
                        index += 1
                print (BSSID_map)
                maxBssidIndex = index-1
                if maxBssidIndex==0: maxBssidIndex = 1

                bssidSeries = []
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisVal = data["Pal Endpoint 1 BSSID"]
                    except:continue
                    try: useVal = BSSID_map[thisVal]
                    except:continue
                    bssidSeries.append({"x":thisTime/1000,"y":useVal})

                scaledBSSID = []
                for i in range(0,len(bssidSeries)): scaledBSSID.append({"x":bssidSeries[i]["x"],"y":bssidSeries[i]["y"]/maxBssidIndex})
                #print(scaledBSSID)

                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "BSSID time plot, mapping=={}".format(BSSID_map),
                    "xaxis":{"string":"Time (sec)"},
                    "yaxis":{"string":"BSSID index"},
                    "showTable": False,
                    "plotWidth":"800px",
                    "data":[
                    {
                        "label":"BSSID",
                        "color":"blue",
                        "width":1,
                        "radius":5,
                        "data": bssidSeries,
                        "fill": -1,
                        "style": "solid"
                    }
                    ]
                }
                myReport["Report"].append(item)

                item = {
                    "elementType": "section",
                    "headingType": "h3",
                    "headingContent":"Throughput time series",
                    "text": "All measured throughput values."
                }
                myReport["Report"].append(item)

                timeSeries = []
                theMin = None
                theMax = None
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisThroughput = float(data[tpName + " Throughput [Mbps]"])
                    except:continue
                    timeSeries.append({"x":thisTime/1000,"y":round(thisThroughput,2)})
                    if theMin==None: theMin=thisThroughput
                    if thisThroughput<theMin: theMin=thisThroughput
                    if theMax==None: theMax=thisThroughput
                    if thisThroughput>theMax: theMax=thisThroughput

                useBSSID = []
                for i in range(0,len(scaledBSSID)): useBSSID.append({"x":scaledBSSID[i]["x"], "y": scaledBSSID[i]["y"]*(theMax-theMin)+theMin})
                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "Throughput time plot",
                    "xaxis":{"string":"Time (sec)"},
                    "yaxis":{"string":"Throughput (Mbps)"},
                    "showTable": False,
                    "plotWidth":"800px",
                    "data":[
                    {
                        "label":"Throughput",
                        "color":"blue",
                        "width":1,
                        "radius":5,
                        "data": timeSeries,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"BSSID",
                        "color":"green",
                        "width":1,
                        "radius":0,
                        "data": useBSSID,
                        "fill": -1,
                        "style": "solid"
                    }
                    ]	    
                }
                myReport["Report"].append(item)

                if iHaveIperf2:
                    item = {
                        "elementType": "section",
                        "headingType": "h3",
                        "headingContent":"iperf2 Latency time series",
                        "text": "All measured iperf2 latency values."
                    }
                    myReport["Report"].append(item)

                    timeSeries = []
                    theMin = None
                    theMax = None
                    for data in dataSet:
                        try:thisTime = float(data["Time [ms]"])
                        except:continue
                        try:thisLatency = float(data[tpName + " iPerf2 Latency Mean [ms]"])
                        except:continue
                        timeSeries.append({"x":thisTime/1000,"y":round(thisLatency,2)})
                        if theMin==None: theMin=thisLatency
                        if thisLatency<theMin: theMin=thisLatency
                        if theMax==None: theMax=thisLatency
                        if thisLatency>theMax: theMax=thisLatency

                        useBSSID = []
                        for i in range(0,len(scaledBSSID)): useBSSID.append({"x":scaledBSSID[i]["x"], "y": scaledBSSID[i]["y"]*(theMax-theMin)+theMin})
                    item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "iperf2 Latency time plot",
                        "xaxis":{"string":"Time (sec)"},
                        "yaxis":{"string":"Latency (ms)"},
                        "showTable": False,
                        "plotWidth":"800px",
                        "data":[
                        {
                            "label":"Latency",
                            "color":"blue",
                            "width":1,
                            "radius":5,
                            "data": timeSeries,
                            "fill": -1,
                            "style": "solid"
                        },
                        {
                            "label":"BSSID",
                            "color":"green",
                            "width":1,
                            "radius":0,
                            "data": useBSSID,
                            "fill": -1,
                            "style": "solid"
                        }
                        ]	    
                    }
                    myReport["Report"].append(item)

                if iHavePing:
                    item = {
                        "elementType": "section",
                        "headingType": "h3",
                        "headingContent":"Ping Latency time series",
                        "text": "All measured ping latency values."
                    }
                    myReport["Report"].append(item)

                    timeSeries = []
                    theMin = None
                    theMax = None
                    for data in dataSet:
                        try:thisTime = float(data["Time [ms]"])
                        except:continue
                        try:thisLatency = float(data[ppName + " Ping Latency (ms)"])
                        except:continue
                        timeSeries.append({"x":thisTime/1000,"y":round(thisLatency,2)})
                        if theMin==None: theMin=thisLatency
                        if thisLatency<theMin: theMin=thisLatency
                        if theMax==None: theMax=thisLatency
                        if thisLatency>theMax: theMax=thisLatency

                    useBSSID = []
                    for i in range(0,len(scaledBSSID)): useBSSID.append({"x":scaledBSSID[i]["x"], "y": scaledBSSID[i]["y"]*(theMax-theMin)+theMin})

                    item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "Latency time plot",
                        "xaxis":{"string":"Time (sec)"},
                        "yaxis":{"string":"Latency (ms)"},
                        "showTable": False,
                        "plotWidth":"800px",
                        "data":[
                        {
                            "label":"Latency",
                            "color":"blue",
                            "width":1,
                            "radius":5,
                            "data": timeSeries,
                            "fill": -1,
                            "style": "solid"
                        },
                        {
                            "label":"BSSID",
                            "color":"green",
                            "width":1,
                            "radius":0,
                            "data": useBSSID,
                            "fill": -1,
                            "style": "solid"
                        }                        
                        ]	    
                    }
                    myReport["Report"].append(item)


                item = {
                    "elementType": "section",
                    "headingType": "h3",
                    "headingContent":"RSSI time series",
                    "text": "All measured RSSI values."
                }
                myReport["Report"].append(item)

                timeSeries1 = []
                theMin = None
                theMax = None
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisVal = float(data["Pal Endpoint 1 Control RSSI [dBm] Mean"])
                    except:continue
                    timeSeries1.append({"x":thisTime/1000,"y":thisVal})
                    if theMin==None: theMin=thisVal
                    if thisVal<theMin: theMin=thisVal
                    if theMax==None: theMax=thisVal
                    if thisVal>theMax: theMax=thisVal
                timeSeries2 = []
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisVal = float(data["Pal Endpoint 1 Data RSSI [dBm] Mean"])
                    except:continue
                    timeSeries2.append({"x":thisTime/1000,"y":thisVal})
                    if theMin==None: theMin=thisVal
                    if thisVal<theMin: theMin=thisVal
                    if theMax==None: theMax=thisRateTx
                    if thisVal>theMax: theMax=thisVal

                useBSSID = []
                for i in range(0,len(scaledBSSID)): useBSSID.append({"x":scaledBSSID[i]["x"], "y": scaledBSSID[i]["y"]*(theMax-theMin)+theMin})



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
                        "label":"Control RSSI, mean (dBm)",
                        "color":"blue",
                        "width":1,
                        "radius":5,
                        "data": timeSeries1,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"Data RSSI, mean (dBm)",
                        "color":"red",
                        "width":1,
                        "radius":5,
                        "data": timeSeries2,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"BSSID",
                        "color":"green",
                        "width":1,
                        "radius":0,
                        "data": useBSSID,
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
                theMin = None
                theMax = None
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisRateRx = float(data["Pal Endpoint 1 RX Rate [Mbps] Mode"])
                    except:continue
                    timeSeries1.append({"x":thisTime/1000,"y":round(thisRateRx,2)})
                    if theMin==None: theMin=thisRateRx
                    if thisRateRx<theMin: theMin=thisRateRx
                    if theMax==None: theMax=thisRateRx
                    if thisRateRx>theMax: theMax=thisRateRx
                timeSeries2 = []
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisRateTx = float(data["Pal Endpoint 1 TX Rate [Mbps] Mode"])
                    except:continue
                    timeSeries2.append({"x":thisTime/1000,"y":round(thisRateTx,2)})
                    if theMin==None: theMin=thisRateTx
                    if thisRateTx<theMin: theMin=thisRateTx
                    if theMax==None: theMax=thisRateTx
                    if thisRateTx>theMax: theMax=thisRateTx

                useBSSID = []
                for i in range(0,len(scaledBSSID)): useBSSID.append({"x":scaledBSSID[i]["x"], "y": scaledBSSID[i]["y"]*(theMax-theMin)+theMin})



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
                        "label":"Rx data rate, mode (Mbps)",
                        "color":"blue",
                        "width":1,
                        "radius":5,
                        "data": timeSeries1,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"Tx data rate, mode (Mbps)",
                        "color":"red",
                        "width":1,
                        "radius":5,
                        "data": timeSeries2,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"BSSID",
                        "color":"green",
                        "width":1,
                        "radius":0,
                        "data": useBSSID,
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
                theMin = None
                theMax = None
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisValRx = float(data["Pal Endpoint 1 RX MCS Mode"])
                    except:continue
                    timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
                    if theMin==None: theMin=thisValRx
                    if thisValRx<theMin: theMin=thisValRx
                    if theMax==None: theMax=thisValRx
                    if thisValRx>theMax: theMax=thisValRx
                timeSeries2 = []
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisValTx = float(data["Pal Endpoint 1 TX MCS Mode"])
                    except:continue
                    timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})
                    if theMin==None: theMin=thisValTx
                    if thisValTx<theMin: theMin=thisValTx
                    if theMax==None: theMax=thisValTx
                    if thisValTx>theMax: theMax=thisValTx

                useBSSID = []
                for i in range(0,len(scaledBSSID)): useBSSID.append({"x":scaledBSSID[i]["x"], "y": scaledBSSID[i]["y"]*(theMax-theMin)+theMin})


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
                        "radius":5,
                        "data": timeSeries1,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"Tx MCS, mode",
                        "color":"red",
                        "width":1,
                        "radius":5,
                        "data": timeSeries2,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"BSSID",
                        "color":"green",
                        "width":1,
                        "radius":0,
                        "data": useBSSID,
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
                theMin = None
                theMax = None
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisValRx = float(data["Pal Endpoint 1 RX Nss Mode"])
                    except:continue
                    timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
                    if theMin==None: theMin=thisValRx
                    if thisValRx<theMin: theMin=thisValRx
                    if theMax==None: theMax=thisValRx
                    if thisValRx>theMax: theMax=thisValRx
                timeSeries2 = []
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisValTx = float(data["Pal Endpoint 1 TX Nss Mode"])
                    except:continue
                    timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})
                    if theMin==None: theMin=thisValTx
                    if thisValTx<theMin: theMin=thisValTx
                    if theMax==None: theMax=thisValTx
                    if thisValTx>theMax: theMax=thisValTx

                print("Scaling from {} to {}".format(theMin,theMax))
                useBSSID = []
                for i in range(0,len(scaledBSSID)): useBSSID.append({"x":scaledBSSID[i]["x"], "y": scaledBSSID[i]["y"]*(theMax-theMin)+theMin})                    

                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "Spatial Stream time plot",
                    "xaxis":{"string":"Time (sec)"},
                    "yaxis":{"string":"Number of spatial streams","step":1},
                    "showTable": False,
                    "plotWidth":"800px",
                    "data":[
                    {
                        "label":"Rx spatial streams, mode",
                        "color":"blue",
                        "width":1,
                        "radius":5,
                        "data": timeSeries1,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"Tx spatial streams, mode",
                        "color":"red",
                        "width":1,
                        "radius":5,
                        "data": timeSeries2,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"BSSID",
                        "color":"green",
                        "width":1,
                        "radius":0,
                        "data": useBSSID,
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
                theMin = None
                theMax = None
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisValRx = float(data["Pal Endpoint 1 RX Bandwidth [MHz] Mode"])
                    except:continue
                    timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
                    if theMin==None: theMin=thisValRx
                    if thisValRx<theMin: theMin=thisValRx
                    if theMax==None: theMax=thisValRx
                    if thisValRx>theMax: theMax=thisValRx
                timeSeries2 = []
                for data in dataSet:
                    try:thisTime = float(data["Time [ms]"])
                    except:continue
                    try:thisValTx = float(data["Pal Endpoint 1 TX Bandwidth [MHz] Mode"])
                    except:continue
                    timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})
                    if theMin==None: theMin=thisValTx
                    if thisValTx<theMin: theMin=thisValTx
                    if theMax==None: theMax=thisValTx
                    if thisValTx>theMax: theMax=thisValTx

                useBSSID = []
                for i in range(0,len(scaledBSSID)): useBSSID.append({"x":scaledBSSID[i]["x"], "y": scaledBSSID[i]["y"]*(theMax-theMin)+theMin})

                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "Bandwidth time plot",
                    "xaxis":{"string":"Time (sec)"},
                    "yaxis":{"string":"Bandwidth [MHz]","step":20},
                    "showTable": False,
                    "plotWidth":"800px",
                    "data":[
                    {
                        "label":"Rx bandwidth (MHz), mode",
                        "color":"blue",
                        "width":1,
                        "radius":5,
                        "data": timeSeries1,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"Tx bandwidth (MHz), mode",
                        "color":"red",
                        "width":1,
                        "radius":5,
                        "data": timeSeries2,
                        "fill": -1,
                        "style": "solid"
                    },
                    {
                        "label":"BSSID",
                        "color":"green",
                        "width":1,
                        "radius":0,
                        "data": useBSSID,
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

                alerts = []
                if len(alerts) == 0:
                    item = {
                        "elementType": "text",
                        "text": "\nThere are no Alerts to report."
                    }
                else:
                    html = "<ul>";
                    for alert in alerts: html += "<li>" + alert + "</li>"
                    html += "</ul>";
                    item = {
                        "elementType": "text",
                        "text": html
                    }
                myReport["Report"].append(item)

        #####  PCAP ANALYSIS

        thePcaps = []
        for x in os.listdir(json_dir):
                if ".pcap" in x:
                        thePcaps.append(json_dir + x)

        if len(thePcaps)>0:
            print(">>> thePcaps: ", thePcaps)

            pcapFile = thePcaps[0]
            parts = pcapFile.split("/")
            pcapFile = parts[len(parts)-1]
            jsonFile = theZips[0]
            pcapDir = json_dir

            totalCount = getCount(pcapFile,json_dir,ea_root)
            #print("The number of packets for {} is {}".format(pcapFile,totalCount))
            useMax = min(10000,totalCount)
            beaconObj = getPacketTypes(pcapFile,json_dir,ea_root,["Beacon"],useMax)
            beaconData = {}
            for item in beaconObj["perStreamStats"]:
                beaconData[item["transmitterAddress"]] = {"count":item["count"],"channel":item["rssiPlot"][0]["channel"],"RSSI":item["rssiPlot"][0]["RSSI"]}
            #print(beaconData)
            allBeacons = []
            for key in beaconData: allBeacons.append(key)

            streamObj = getMainStream(pcapFile,json_dir,ea_root,useMax)
            streamData = streamObj["perChannelResults"]
            #print(json.dumps(streamData,indent=3))
            rxAddr = streamData["all"]["to"]
            txAddr = streamData["all"]["from"]
            apAddr = None
            staAddr = None
            direction = None
            if rxAddr in allBeacons:
                apAddr = rxAddr
                staAddr = txAddr
                direction = "ul"
            elif txAddr in allBeacons:
                apAddr = txAddr
                staAddr = rxAddr
                direction = "dl"
            print("AP is {}, STA is {}, and the traffic direction is {}".format(apAddr,staAddr,direction))

            #Find the testlog file
            logFile = None
            for x in os.listdir(pcapDir):
                if "testresultlog" in x:
                    logFile = pcapDir + x
            #print(logFile)
            #If there is a log file, put these addresses into it.  If there is not one, make one with these addresses in it.
            if logFile==None:
                logFile = pcapDir + "testresultlog.json"
            try:
                f = open(logFile)
                logs = json.load(f)
                logs["palMAC"] = formatMAC(staAddr)
                f.close()
            except:
                logs = {"palMAC":formatMAC(staAddr)}

            with open(logFile,"w",encoding="utf-8") as f:
                json.dump(logs,f,ensure_ascii=False,indent=3)                          

            endpointTag = tpName.replace("-STApal7ToServer","").replace("-ServerToSTApal7","")
            parts = endpointTag.split("-")
            for part in parts:
                if "L" in part: endpointTag = part
            print("The endpointTag you are using is {}".format(endpointTag))

            countRoams = 1
            import doRoamingAnalysis2
            etc = {"endpointTag":endpointTag,"countRoams":countRoams,"roamSet":0,"upOrDown":"dn"}
            roamReport,roamTimes,allFTtimes,appGap,EAPOL_groups,throughputs = doRoamingAnalysis2.main(pcapDir,directory_name,pcapFile,jsonFile,etc)
            #print(roamTimes)
            #print(allFTtimes)
            #print(appGap)
            #print(EAPOL_groups)
            #print(throughputs)

            item = {
                "elementType":"separator",
                "color":"green",
                "width":"14px"
            }
            myReport["Report"].append(item)

            item = {
                "elementType":"pagebreak"
            }
            myReport["Report"].append(item)

            item = {
                    "elementType": "section",
                    "headingType": "h1",
                    "headingContent": "PCAP Analysis"
            }
            myReport["Report"].append(item)

            roamItems = roamReport["Report"]
            for item in roamItems:
                myReport["Report"].append(item)

            item = {
                    "elementType": "section",
                    "headingType": "h2",
                    "headingContent": "Gap based on packet analysis",
                    "text": "The gap based on packet analysis is {:.2f} msec".format(appGap["applicationGap"])                
            }
            myReport["Report"].append(item)

            thisText = "The gap based on the lost packet plot, coupled with the found per-second packet rate, is {:.2f} msec.".format(appGap["iperfGap"])
            thisText += "<br/>"
            thisText += "This is based on a steady-state packet rate of {:.1f} PPS, and a lost packet count of {} packets.".format(appGap["steadyStateRate"],appGap["lostPackets"])
            item = {
                    "elementType": "section",
                    "headingType": "h2",
                    "headingContent": "Gap based on lost packets",
                    "text": thisText
            }
            myReport["Report"].append(item)

            for group in EAPOL_groups:
                item = {
                    "elementType": "section",
                    "headingType": "h2",
                    "headingContent": "EAPOL Timing",
                    "text": "The time spent doing EAPOL is {:.2f} msec, see packets {}".format(group["timeSpentMsec"],group["packets"])
                }
                myReport["Report"].append(item)
        


########################################################################################################################

        info("{} JSON report is complete. {}".format(cGreen,cNormal))

        #Put the local link anyway.

        # Let's see if we can find script manager running here.  If so, put some local copies
        try:
                #Verify where scriptManager is running
                localSM = True
                api_endpoint = "http://"+hostIpAddress+":5678/exec?command=pwd"
                r = requests.get(url=api_endpoint)
        except requests.exceptions.RequestException as error:
                print(">>> initializeAutotest: Unable to find a local copy of script manager.  So not going to do anything here.")
                print("initializeAutotest: Error: ", error)
                localSM = False

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
                api_endpoint = "http://"+hostIpAddress+":5678/jsonToHtmlReport"
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
                    "val": {"htmlLink": "http://"+hostIpAddress+":5678/storage/"+fileName},
                    "label": "Report for " + theName,
                    "withTitle": theTitle            
                }
                jsonPlot["_editable"] = False
                f = open(directory_name+'TestReportLocal.json', "w")
                f.write(json.dumps(jsonPlot,indent=4))
                f.close()

                print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

#===
#Use this for debugging.  Otherwise, comment it out.
'''
ea_root = "http://localhost:8080/"
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-02_17-35_calix/1_2026-10-02_17-35_Bandsteer/"

main(directory_name,json_dir,ea_root)
'''
