import sys
import json
import os
import requests
import base64
from pathlib import Path

def extract(directory_name,fileName,ea_root,useTPairs,bitrate):
    
    with open(fileName, "rb") as f:
        print("Grabbing the zip file from {}".format(fileName))
        bytes = f.read()
        encoded = base64.b64encode(bytes)
        #print(encoded)
        api_endpoint = ea_root + "zip2csv"
        data = {'zip':encoded}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        #print(theJson)

    '''
    print("Write the CSV file out to {}".format(directory_name+'csv.csv'))
    f = open(directory_name+'csv.csv', 'w')
    f.write(theJson["csv"])
    f.close()

    csv_path = directory_name + "csv.csv"
    '''

    # Analyze the CSV file
    #csv = Path(csv_path).read_text()
    csv = theJson["csv"]
    api_endpoint = ea_root + "objectify"
    data = {'csv':csv}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    #print(theJson)

    print("Calling extract(), with useTPairs={}, and a bit rate of {}".format(useTPairs,bitrate))


    print('\n### Running getStats')
    #Get basic test results information
    api_endpoint = ea_root + "getStats"
    data = {'csv':csv,'filter':'counts'}
    try:
        r = requests.post(url=api_endpoint, data=data, timeout=5)
    except requests.exceptions.RequestException as error:
        info("Error: ", error)
        sys.exit(44)	
    theStats = json.loads(r.text)
    print('\n>>> Stats are:\n {}:'.format(theStats))
    theTrafficPairs = theStats['filteredData']['trafficPairs']['map']
    
    headers = theJson["headers"]
    dataSet = theJson["dataSet"]
    topLines = theJson["topLines"]
    summaryData = theJson["summaryData"]
    if "error" in theJson: print("objectify: This data returned an error: {}".format(theJson["error"]))
    #print("The length of the data set is {}".format(len(dataSet)))
    
    api_endpoint = ea_root + "crunch"
    run = 1
    data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'topLines':topLines, 'run':run}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    if "error" in theJson: print("crunch: This data returned an error: {}".format(theJson["error"]))
    analyzedData = theJson["crunchedData"]
    print("The number of endpoints is {}".format(len(analyzedData)))

    print("The traffic pairs are {}".format(theTrafficPairs))
    print("The useTPairs is {}".format(useTPairs))

    for a in range (0,len(analyzedData)):  #Per Endpoint
        _analyzedData = analyzedData[a]
        for atten in range(0,len(_analyzedData)):  #Per Attenuation
            lostPacketArray = []
            throughputArray = []
            derivedLostPacketArray = []
            latencyArray = []
            '''
            for tag in range(0,len(useTPairs)):   #Per Traffic Pairs in use
                if not useTPairs[tag]: continue
                thisTag = "_"+str(tag)
                thisTag = theTrafficPairs["{}".format(tag)]
                print("Looking for tag {}".format(thisTag))
                #Find the right data.
                for t in range(0,len(_analyzedData[atten]["tpairData"])):
                    #print("Comparing to {}".format(_analyzedData[atten]["tpairData"][t]["tpMap"]))
                    if thisTag in _analyzedData[atten]["tpairData"][t]["tpMap"]:
                        try: lostPacketArray.append(round(_analyzedData[atten]["tpairData"][t]["lostPercentage"]["mean"],1))
                        except: lostPacketArray.append(0)
                        try: throughputArray.append(round(_analyzedData[atten]["tpairData"][t]["throughput"]["mean"],2))
                        except: throughputArray.append(-1)
                        try: latencyArray.append(round(_analyzedData[atten]["tpairData"][t]["iPerf2Latency"]["Mean"]["mean"],2))
                        except: latencyArray.append(-1)
                        gotThroughput = _analyzedData[atten]["tpairData"][t]["throughput"]["mean"]
                        sentThroughput = bitrate #This is per-vsta
                        print("Calculating the error rate from got {} compared to sent {}".format(gotThroughput,sentThroughput))
                        try: errorRate = 1 - (gotThroughput/sentThroughput)
                        except: errorRate = 0
                        if errorRate<0:
                            print("Well, the throughput sent, {}, is actually less than the throughput received, {}.  This would imply negative loss, which we won't allow, so setting the loss to zero.".format(sentThroughput,gotThroughput))
                            errorRate=0
                        derivedLostPacketArray.append(round(errorRate * 100,1))
                        break
            '''
            for t in range(0,len(_analyzedData[atten]["tpairData"])):
                if _analyzedData[atten]["tpairData"][t]["tpMap"] in useTPairs:
                    try: lostPacketArray.append(round(_analyzedData[atten]["tpairData"][t]["lostPercentage"]["mean"],1))
                    except: lostPacketArray.append(0)
                    try: throughputArray.append(round(_analyzedData[atten]["tpairData"][t]["throughput"]["mean"],2))
                    except: throughputArray.append(-1)
                    try: latencyArray.append(round(_analyzedData[atten]["tpairData"][t]["iPerf2Latency"]["Mean"]["mean"],2))
                    except: latencyArray.append(-1)
                    gotThroughput = _analyzedData[atten]["tpairData"][t]["throughput"]["mean"]
                    sentThroughput = bitrate #This is per-vsta
                    print("Calculating the error rate from gotThroughput {} compared to sentThroughput {}".format(gotThroughput,sentThroughput))
                    try: errorRate = 1 - (gotThroughput/sentThroughput)
                    except: errorRate = 0
                    print("So that error rate is {}%".format(errorRate*100))
                    if errorRate<0:
                        print("Well, the throughput sent, {}, is actually less than the throughput received, {}.  This would imply negative loss, which we won't allow, so setting the loss to zero.".format(sentThroughput,gotThroughput))
                        errorRate=0
                    if errorRate<0 or True: derivedLostPacketArray.append(round(errorRate * 100,1))   #If or True, that means you ALWAYS used the derived packet loss rate, not the iPerf provided value.
            print("Atten: {},  Lost Packet Array: {}".format(_analyzedData[atten]["attenuation"],lostPacketArray))
            print("Atten: {},  Throughput  Array: {}".format(_analyzedData[atten]["attenuation"],throughputArray))
            print("Atten: {},  Derived Lost Packet Array: {}".format(_analyzedData[atten]["attenuation"],derivedLostPacketArray))
            print("Atten: {},  Latency Array: {}".format(_analyzedData[atten]["attenuation"],latencyArray))
            #For now...
            if len(derivedLostPacketArray)>0:
                lostPacketArray = []
                for item in derivedLostPacketArray: lostPacketArray.append(item)
            AverageLatency = _analyzedData[atten]["iPerf2Latency"]["Mean"]["mean"]
            TotalThroughput = _analyzedData[atten]["throughput"]["mean"]

    csvTrafficPairs = _analyzedData[atten]["tpaircount"]
    if csvTrafficPairs != len(useTPairs):
        print("\nXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        print("The number of traffic pairs in the csv, {}, is not what is expected, {}".format(csvTrafficPairs,len(useTPairs)))
        print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX\n")

    activePairs = 0
    for isActive in useTPairs:
        if isActive: activePairs+=1

    theseResults = {
        "tpairCount": activePairs,
        "RatePerSTA": bitrate,
        "LostPackets":lostPacketArray,
        "Throughputs":throughputArray,
        "Latencies":latencyArray,
        "AverageLatency":AverageLatency,
        "TotalThroughput":TotalThroughput
    }

    return theseResults
    

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
        CL = ""
        for i in range(2,len(splits)):CL += splits[i] + "_"
        CL = CL[0:len(CL)-1]
        theTitle = directoriesJson["title"]
        theName = theTitle.replace(" ","_")
    except:
        CL = ""
        theTitle = "vSTA Throughput"
        theName = theTitle.replace(" ","_")

    #Delete the report link JSON file, so that if this createReport fails, you won't be misled by an older link.
    command = 'rm ' + directory_name+'TestReport.json'
    os.system(command)    
    
    if json_dir[len(json_dir)-1] != "/": json_dir += "/"
    print('>>> createReport_main json_dir', json_dir)

    #Get all test results files
    theTRs = []
    theZips = []
    for x in os.listdir(json_dir):
        if "TestResults" in x:
            '''
            try:
                packetSize = x.split("_")[1].replace(".json","")
                mssSize = x.split("_")[2]
                direction = x.split("_")[3]
                trafficType = x.split("_")[4]
            except:
                packetSize = "NA"
                mssSize = "NA"
                direction = "NA"
                trafficType = "NA"
            '''
            #theTRs.append({"fileName":json_dir + x, "packetSize":packetSize,"mssSize":mssSize,"direction":direction,"trafficType":trafficType})
            theTRs.append({"fileName":json_dir + x})
        if ".zip" in x and "csv" not in x.lower() and "json" not in x.lower(): theZips.append(json_dir+x)

    #print(theTRs)   #Test Result files.
    #print(theZips)
    
    if len(theZips) <= 0:
        myReport = {}
        myReport["Title"] = theTitle
        myReport["Report"] = []
        item = {
            "elementType": "section",
            "headingType": "h1",
            "headingContent": theTitle,
            "text":"No Zip Files Found"
        }
        myReport["Report"].append(item)
        FinalResults = []

    else:
        #For just one of the zip files, get the names of the traffic pairs.
        fileName = theZips[0]
        with open(fileName, "rb") as f:
            print("Grabbing the zip file from {}".format(fileName))
            bytes = f.read()
            encoded = base64.b64encode(bytes)
            api_endpoint = ea_root + "zip2csv"
            data = {'zip':encoded}
            theResponse = requests.post(url=api_endpoint, data=data)
            theJson = json.loads(theResponse.text)

        csv = theJson["csv"]
        print('\n### Running getStats')
        #Get basic test results information
        api_endpoint = ea_root + "getStats"
        data = {'csv':csv,'filter':'counts'}
        try:
            r = requests.post(url=api_endpoint, data=data, timeout=5)
        except requests.exceptions.RequestException as error:
            info("Error: ", error)
            sys.exit(44)	
        theStats = json.loads(r.text)
        #print('\n>>> Stats are:\n {}:'.format(theStats))
        theTrafficPairs = theStats['filteredData']['trafficPairs']['map']
        #print(theTrafficPairs)
        tpList = []
        for entry in theTrafficPairs: tpList.append(theTrafficPairs[entry])
        #print(tpList)    

        #Open the JSON files with the data.
        for TR in theTRs:        
            #jsonFile = json_dir + "TestResults.json"
            jsonFile = TR["fileName"]
            #print(jsonFile)
            try:
                f = open(jsonFile)
                resultsJson = json.load(f)
                #print(resultsJson)
                TR["json"] = resultsJson
            except:
                print("Error opening the results json file.")
                return

        #print(theTRs)

        for TR in theTRs:
            FinalResults = TR["json"]["FinalResults"]
            #Handle runs that didn't complete due to weird behavior.
            if len(FinalResults)==0:
                InterimResults = TR["json"]["InterimResults"]
                keys = list(InterimResults.keys())
                AllIR = InterimResults[keys[0]]
                LastIR = AllIR[len(AllIR)-1]
                LastIR["testConfig"] = {}
                filePath = TR["fileName"]
                print(filePath)
                parts = filePath.split("/")
                fileName = parts[len(parts)-1]
                print(fileName)
                parts = fileName.split("_")
                for part in parts:
                    if "bytes" in part: LastIR["testConfig"]["packetSize"] = part.replace("bytes","")
                    if "mss"   in part: LastIR["testConfig"]["mss"] =        part.replace("mss","")
                    if "up" in part or "dn" in part: LastIR["testConfig"]["direction"] = part
                    if "udp" in part or "tcp" in part: LastIR["testConfig"]["trafficMode"] = part                    
                FinalResults.append(LastIR)
                    
            TR["packetSize"]   = "?"
            TR["mssSize"]      = "?"
            TR["direction"]    = "?"
            TR["trafficMode"]  = "?"
            for entry in FinalResults:
                #print(entry)
                TR["packetSize"]  = entry["testConfig"]["packetSize"]
                TR["mssSize"]     = entry["testConfig"]["mss"]
                TR["direction"]   = entry["testConfig"]["direction"]
                TR["trafficMode"] = entry["testConfig"]["trafficMode"]
                throughputs = entry["Throughputs"]
                #print(throughputs)
                averageThroughput = 0
                try:
                    for throughput in throughputs: averageThroughput += throughput
                    averageThroughput /= len(throughputs)
                    #print(averageThroughput)
                except:
                    print("cannot calculate average throughput")
                entry["averageThroughput"] = "{:.2f}".format(averageThroughput)
                
            InterimResults = TR["json"]["InterimResults"]
            for vstaCount in InterimResults:
                theArray = InterimResults[vstaCount]
                for entry in theArray:
                    throughputs = entry["Throughputs"]
                    averageThroughput = 0
                    try:
                        for throughput in throughputs: averageThroughput += throughput
                        averageThroughput /= len(throughputs)
                    except:
                        print("No go on average throughput calculation.")
                    entry["averageThroughput"] = "{:.2f}".format(averageThroughput)

        #Make the report
        myReport = {}
        myReport["Title"] = theTitle
        myReport["Report"] = []

        item = {
            "elementType": "section",
            "headingType": "h1",
            "headingContent": theTitle
        }
        myReport["Report"].append(item)

        ############## Date and time of report creation
        from datetime import datetime
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Date and time of report creation:",
            "text": dt_string
        }
        myReport["Report"].append(item)    

        ################################ Per-vSTA throughput as a function of number of vSTAs
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"Per-vSTA Throughput vs. vSTA Count"
        }
        myReport["Report"].append(item)

        PacketSizes = []
        for TR in theTRs:
            FinalResults = TR["json"]["FinalResults"]
            if int(FinalResults[0]["testConfig"]["packetSize"]) not in PacketSizes: PacketSizes.append(int(FinalResults[0]["testConfig"]["packetSize"]))
        PacketSizes.sort()

        tpairCounts = []
        for TR in theTRs:
            FinalResults = TR["json"]["FinalResults"]
            for fr in FinalResults:
                if int(fr["tpairCount"]) not in tpairCounts: tpairCounts.append(int(fr["tpairCount"]))
        tpairCounts.sort()
        maxTPair = max(tpairCounts)

        theData = []
        idx = 3
        for TR in theTRs:
            if "{}pairs".format(maxTPair) not in TR["fileName"]: continue
            FinalResults = TR["json"]["FinalResults"]
            scatter = []
            #for result in FinalResults: scatter.append({"x":result["tpairCount"], "y":result["RatePerSTA"]})
            for result in FinalResults: scatter.append({"x":result["tpairCount"], "y":result["averageThroughput"]})
            theData.append({
                "label":"Per-vSTA throughput vs. vSTA count for packet size {} bytes MSS {} direction {} trafficMode {}".format(TR["packetSize"],TR["mssSize"],TR["direction"],TR["trafficMode"]),
                "color":colors[idx % len(colors)],
                "width":1,
                "radius":3,
                "data": scatter,
                "fill": -1,
                "style": "solid"
            })                
            idx += 1
        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "Final Throughput",
            "xaxis":{"string":"vSTA Count"},
            "yaxis":{"string":"Per-vSTA Throughput (Mbps)"},
            "showTable": False,
            "plotWidth":"800px",
            "data": theData
        }
        myReport["Report"].append(item)


        ################################ Steps to solution for each vSTA count
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"Path to solution for each traffic pair on each vSTA"
        }

        allData = []
        for TR in theTRs:
            if TR["trafficMode"] == "tcp": continue
            if "{}pairs".format(maxTPair) not in TR["fileName"]: continue
            #InterimResults = resultsJson["InterimResults"]
            InterimResults = TR["json"]["InterimResults"]    
            for key in InterimResults:
                vstaCount = int(key)
                thisArray = InterimResults[key]

                item = {
                    "elementType": "section",
                    "headingType": "h3",
                    "headingContent":"Path to solution for traffic pair count {}, packet size {} MSS {} direction {} trafficMode {}".format(vstaCount,TR["packetSize"],TR["mssSize"],TR["direction"],TR["trafficMode"])
                }
                myReport["Report"].append(item)

                steps = len(thisArray)
                labels = []
                for result in thisArray: labels.append(result["RatePerSTA"])
                #for result in thisArray: labels.append(result["averageThroughput"])
                allData = []
                for vsta in range(0,vstaCount):
                    theseValues = []
                    for result in thisArray:
                        try: theseValues.append(result["LostPackets"][vsta])
                        except: theseValues.append(-1)
                    color = colors[vsta % len(colors)]        
                    theData = {
                        #"label":"Loss vs. Rate for vSTA " + str(vsta),
                        "label": tpList[vsta],
                        "color": color,
                        "width":1,
                        "radius":3,
                        "data": theseValues,
                        "fill": -1,
                        "style": "solid"
                    }
                    allData.append(theData)
                item = {
                    "elementType":"plot",
                    "type": "line",
                    "title": "Paths to solution for vSTA count {}, packet size {}B  MSS {} direction {} trafficMode {}".format(key,TR["packetSize"],TR["mssSize"],TR["direction"],TR["trafficMode"]),
                    "labels": labels,
                    "showDataValues":{"show":True,"color":"red","align":"top","offset":"7","fontSize":"7"},
                    "xaxis":{"string":"Offered Data Rate (Mbps)"},
                    "yaxis":{"string":"Lost Packet Rate (%)"},
                    "showTable": False,
                    "plotWidth":"800px",
                    "data": allData
                }
                myReport["Report"].append(item)

    for x in os.listdir(json_dir):
        if "AllResults" in x:
            allResultsFile = json_dir + x
    #print(allResultsFile)
    haveAllResults = False
    try:
        f = open(allResultsFile)
        allResultsJson = json.load(f)
        haveAllResults = True
    except:
        print("Error opening the allResults json file.")

    if haveAllResults:
        #print(allResultsJson)
        columns = {}
        allResults = allResultsJson["allResults"]
        for test in allResults:
            theseTests = allResults[test]
            for pairCount in theseTests:
                thisTest = theseTests[pairCount]
                thisConfig = thisTest["testConfig"]
                for header in thisConfig:
                    if header in columns: columns[header].append(thisConfig[header])
                    else: columns[header] = [thisConfig[header]]

                Throughputs = thisTest["Throughputs"]
                averageThroughput = 0
                try:
                    for throughput in Throughputs: averageThroughput += throughput
                    averageThroughput /= len(Throughputs)
                except:
                    print("Issue with average throughput calculation")
                header = "Average Throughput (Mbps)"
                value = "{:.2f}".format(averageThroughput)
                if header in columns: columns[header].append(value)
                else: columns[header] = [value]

                totalThroughput = 0
                try:
                    for throughput in Throughputs: totalThroughput += throughput
                except:
                    print("Issue with total throughput calculation")
                header = "Total Throughput (Mbps)"
                value = "{:.2f}".format(totalThroughput)
                if header in columns: columns[header].append(value)
                else: columns[header] = [value]

                header = "# Traffic Pairs"
                value = thisTest["tpairCount"]
                if header in columns: columns[header].append(value)
                else: columns[header] = [value]

                header = "Offered Load"
                if thisConfig["trafficMode"]=="udp": value = "{}{}".format(thisTest["RatePerSTA"],thisTest["RateUnits"])
                elif thisConfig["trafficMode"]=="tcp": value = "{}{}".format(0,"M")
                if header in columns: columns[header].append(value)
                else: columns[header] = [value]

                LossPercent = thisTest["LostPackets"]
                averageLoss = 0
                try:
                    for loss in LossPercent: averageLoss += loss
                    averageLoss /= len(LossPercent)
                except:
                    print("Issue with average loss calculation")
                header = "Average Loss (%)"
                value = "{:.2f}".format(averageLoss)
                if thisConfig["trafficMode"] == "tcp": value = "N/A"
                if header in columns: columns[header].append(value)
                else: columns[header] = [value]

                header = "Average Latency (msec)"
                if thisConfig["trafficMode"]=="udp":
                    try: value = "{:.2f}".format(thisTest["AverageLatency"])
                    except: value = "{}".format("N/A")
                elif thisConfig["trafficMode"]=="tcp": value = "{}".format("N/A")
                if header in columns: columns[header].append(value)
                else: columns[header] = [value]

        allData = []
        for header in columns:
            allData.append({"label":header,"data":columns[header]})
        item = {
            "elementType":"table",
            "type": "table",
            "title": "Final Results of each test",
            #"tableWidth":"700px",
            "data":allData
        }
        myReport["Report"].append(item)
        
        
    print("{} JSON report is complete. {}".format(cGreen,cNormal))
    #print(json.dumps(myReport,indent=4))
    #############################################################
    
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
    fileName = theName + ".html"
    fullPath = storageLocation + fileName
    #print("The full path for the saved file is {}".format(fullPath))
    
    #Write out this html file
    f = open(fullPath, "w")
    f.write(html)
    f.close()
    
    print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

    #Write out this json file
    jsonPath = fullPath.replace(".html",".json")
    f = open(jsonPath, "w")
    f.write(json.dumps(myReport,indent=4))
    f.close()

    #Put one in the script directory too, for interim reporting.
    jsonPath2 = directory_name + theName + ".json"
    print("Writing out myReport to {}".format(jsonPath2))
    f = open(jsonPath2, "w")
    f.write(json.dumps(myReport,indent=4))
    f.close()
    
    print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

    
    #Create a JSON file that will put a link to the previous file into script manager.
    jsonPlot = {}
    jsonPlot["reportLink"] = {
        "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
        "label": "Report for " + theTitle
    }
    jsonPlot["_editable"] = False
    f = open(directory_name+'TestReport.json', "w")
    f.write(json.dumps(jsonPlot,indent=4))
    f.close()
    
    print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

    #Write messages if you have any.  Here's an example.
    jsonMessages = {}    
    alertMessage = ""
    for result in FinalResults:
        #alertMessage += "<br/>For {} pair, the throughput is {} Mbps.".format(result["tpairCount"],result["RatePerSTA"])
        alertMessage += "<br/>For {} pair, the throughput is {} Mbps.".format(result["tpairCount"],result["averageThroughput"])
    jsonMessages["alertMessage"] = {"val":{"_scriptMessage_":alertMessage},"label":"Throughputs"}
    jsonMessages["_editable"] = False
    f = open(directory_name+'TestMessages.json', "w")
    f.write(json.dumps(jsonMessages,indent=4))
    f.close()    

    return myReport

#===
#Use this for debugging.  Otherwise, comment it out.
'''
print("This is the debugging section of createReport for vstaThroughput.  Comment it out if you don't expect to see it.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-15_13-23_calix/1_2026-10-15_13-23_throughputSearchConfigurable/"
ea_root = "http://localhost:8080/"
fn = "Rate_2402.0M_88B_0mss_dn_1pairs_udp.zip"
fileName = json_dir + fn
useTPairs = [True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True,True]
useTPairs=['ServerTopalBox-P7C_6_0']
bitrate = 194562.0

#results = extract(directory_name,fileName,ea_root,useTPairs,bitrate)
#print(results)

main(directory_name,json_dir,ea_root)
'''
