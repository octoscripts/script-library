import sys
import json
import os
import requests
import base64
import pprint
import time
import datetime
pp = pprint.PrettyPrinter(indent=4)

from pathlib import Path

import numpy as np

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
iro = ["red","blue","green","black"]

# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

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

def getPalData(file,ea_root):
        with open(file, "rb") as f:
                bytes = f.read()
                encoded = base64.b64encode(bytes)
                api_endpoint = ea_root + "zip2csv"
                data = {'zip':encoded}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)
                csv = theJson["csv"]
                f.close()

                #print('\n### Running getStats')
                #Get basic test results information
                api_endpoint = ea_root + "getStats"
                data = {'csv':csv,'filter':'counts'}
                try:  r = requests.post(url=api_endpoint, data=data, timeout=5)
                except requests.exceptions.RequestException as error:
                        info("Error: ", error)
                        sys.exit(44)
                y = json.loads(r.text)
                #print('\nStats for read-in data: >>> y: ', y)
                trafficPairMap = y["filteredData"]["trafficPairs"]["map"]

                # Analyze the CSV file
                api_endpoint = ea_root + "objectify"
                data = {'csv':csv}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)
                headers = theJson["headers"]
                dataSet = theJson["dataSet"]
                if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

        return csv,headers,dataSet
        

def generateTheReport(myReport,theTitle,directory_name):
        #print(myReport)

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
        fileName = "eMLSR_Report.html"
        fullPath = storageLocation + fileName

        #Write out this html file
        f = open(fullPath, "w")
        f.write(html)
        f.close()
        print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

        #Write out a copy of the JSON formatted report in case it's useful
        jsonPath = fullPath.replace(".html",".json")
        f = open(jsonPath, "w")
        f.write(json.dumps(myReport,indent=3))
        f.close()
        print("{} JSON report has been written to {}. {}".format(cGreen,jsonPath,cNormal))

        #Create a JSON file that will put a link to the previous file into script manager.
        jsonPlot = {}
        jsonPlot["reportLink"] = {
                "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
                "label": "Report for " + theTitle
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'eMLSR_Report.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

        return fullPath

def extract(directory_name,json_dir,jsonFile,pcapFile,ea_root):

        if directory_name[len(directory_name)-1] != "/": directory_name += "/"
        if json_dir[len(json_dir)-1] != "/": json_dir += "/"

        with open(jsonFile, "rb") as f:
                bytes = f.read()
                encoded = base64.b64encode(bytes)
                api_endpoint = ea_root + "zip2csv"
                data = {'zip':encoded}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)

                csv = theJson["csv"]
                f.close()

                print('\n### Running getStats')
                #Get basic test results information
                api_endpoint = ea_root + "getStats"
                data = {'csv':csv,'filter':'counts'}
                try:  r = requests.post(url=api_endpoint, data=data, timeout=5)
                except requests.exceptions.RequestException as error:
                    info("Error: ", error)
                    sys.exit(44)

                y = json.loads(r.text)
                print('\nStats for read-in data: >>> y: ', y)
                trafficPairMap = y["filteredData"]["trafficPairs"]["map"]

                # Analyze the CSV file
                api_endpoint = ea_root + "objectify"
                data = {'csv':csv}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)
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

                numberOfPalEndpoints = len(analyzedData)
                print("There is data for {} endpoints.".format(numberOfPalEndpoints))
                numberOfAttenuations = len(analyzedData[0])
                print("There are {} attenuation steps".format(numberOfAttenuations))
                tpairData = analyzedData[0][0]["tpairData"]
                numberOfTPairs = len(analyzedData[0][0]["tpairData"])
                print("There are {} traffic pairs".format(numberOfTPairs))

                parts = jsonFile.split("/")
                fileName = parts[len(parts)-1]
                retObj = {fileName:{}}

                for i in range(0,numberOfTPairs):
                        tpairName = trafficPairMap[str(i)]
                        data = analyzedData[0][0]["tpairData"][i]["throughput"]["mean"]
                        print("Throughput for {} is: {}\n\n".format(tpairName,data))
                        retObj[fileName][tpairName] = {"throughput":data}

                if pcapFile != None:
                        print('\n### Getting total packet count')
                        parts = pcapFile.split("/")
                        pcapFileName = parts[len(parts)-1]
                        api_endpoint = ea_root + "pcapAPI?action=getTotalPacketCount&fileName={}&pcapDir={}".format(pcapFileName,json_dir)
                        print(api_endpoint)
                        theResponse = requests.get(url=api_endpoint)
                        theJson = json.loads(theResponse.text)
                        totalCount = theJson["result"]
                        #print(totalCount)
                        useMax = min(10000,totalCount)

                        #Getting beacons
                        print('\n### Getting beacon data')
                        api_endpoint = ea_root + "pcapAPI?action=getDataOfType&filters=Beacon&fileName={}&pcapDir={}&lastPacket={}".format(pcapFileName,json_dir,useMax)
                        theResponse = requests.get(url=api_endpoint)
                        theJson = json.loads(theResponse.text)
                        beaconData = {}
                        for item in theJson["result"]["perStreamStats"]:
                                beaconData[item["transmitterAddress"]] = {"count":item["count"],"channel":item["rssiPlot"][0]["channel"]}
                        #retObj[fileName]["beaconData"] = beaconData
                        
                        #Getting streams
                        print('\n### Getting main streams')
                        api_endpoint = ea_root + "pcapAPI?action=getMainStream&fileName={}&pcapDir={}&lastPacket={}".format(pcapFileName,json_dir,useMax)
                        theResponse = requests.get(url=api_endpoint)
                        theJson = json.loads(theResponse.text)
                        streamData = theJson["result"]["perChannelResults"]
                        #retObj[fileName]["streamData"] = streamData
                        #retObj[fileName]["frequencyMHz"] = theJson["result"]["result"]["channel"]

                        BSSIDs = {}
                        theFreq = theJson["result"]["result"]["channel"]
                        APs = []
                        for bssid in beaconData:
                                if beaconData[bssid]["channel"] == theFreq: APs.append(bssid)
                        strFreq = str(theFreq)
                        if streamData[strFreq]["from"] in APs:
                                try:    BSSIDs["AP"] =  streamData[strFreq]["from"]
                                except: BSSIDs["AP"] =  "N/A 1"
                                try:    BSSIDs["STA"] = streamData[strFreq]["to"]
                                except: BSSIDs["STA"] = "N/A 2"
                        elif streamData[strFreq]["to"] in APs:
                                try:    BSSIDs["AP"] =  streamData[strFreq]["to"]
                                except: BSSIDs["AP"] =  "N/A 3"
                                try:    BSSIDs["STA"] = streamData[strFreq]["from"]
                                except: BSSIDs["STA"] = "N/A 4"
                        retObj["BSSIDs"] = BSSIDs
                        
                                                
                return retObj

#
####################################################################
#

def main(directory_name,json_dir,ea_root):

        main_start = time.time()

        #Grab the directory information as created by SM.
        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        if directory_name[len(directory_name)-1] != "/": directory_name += "/"
        dirFile = directory_name + "directories.json"
        try:
                f = open(dirFile)
                directoriesJson = json.load(f)
                subDir = directoriesJson["subDirectory"]
                splits = subDir.split("_")
                runNumber = splits[0]
                theName = directoriesJson["title"]
                theTitle = theName.replace(" ","_")
        except:
                theTitle = "eMLSR"
                theName = theTitle.replace(" ","_")
                runNumber = "0"                

        #For this test, pull the JSON information created.
        for x in os.listdir(json_dir):
            if "testresultlog" in x:
                    jsonFile = json_dir + x

        f = open(jsonFile)
        testResultLogJson = json.load(f)
        f.close

        #Write a report
        myReport = {}
        myReport["Title"] = theName
        myReport["Report"] = []

        mloConfig_STA = testResultLogJson["mloConfig_STA"]
        mloBands = mloConfig_STA["bands"]        
        tableData = []
        tableData.append({"label":"Band","data":["Member of MLD?","Channel","Bandwidth"]})        
        for band in mloBands:
                tableData.append({"label":band,"data":[mloBands[band]["member"],mloBands[band]["channel"],mloBands[band]["bandwidth"]]})
        item = {
                "elementType":"table",
                "type":"table",
                "title":"MLD Composition",
                "data": tableData
        }
        myReport["Report"].append(item);

        if "palToUse" in testResultLogJson: palToUse = testResultLogJson["palToUse"]
        else: palToUse = "palBox-I15-SP7"
        print("palToUse: {}".format(palToUse))

        obssInfo = {}
        for band in mloConfig_STA["bands"]:
                if not mloConfig_STA["bands"][band]["member"]: continue
                obssInfo[mloConfig_STA["bands"][band]["palName"]] = {"band":band}
        obssAP = testResultLogJson["obssAP"]
        obssBands = obssAP["bands"]
        for key in obssInfo:
                thisBand = obssInfo[key]["band"]
                thisChannel = obssBands[thisBand]["channel"]
                obssInfo[key]["channel"] = thisChannel
        emlsrData = testResultLogJson["Throughput-EMLSR.zip"]
        for key in emlsrData:
                if palToUse in key: mainTrafficPair = key
                for obssPal in obssInfo:
                        if obssPal in key:
                                obssInfo[obssPal]["tpair"] = key
                                
        print("mainTrafficPair: {}".format(mainTrafficPair))
        #print(obssInfo)
        obssPairByChannel = {}
        for key in obssInfo: obssPairByChannel[str(obssInfo[key]["channel"])] = obssInfo[key]["tpair"]
        #print("The obssPairByChannel info is {}".format(obssPairByChannel))

        theChannels = []
        for key in testResultLogJson:
                if "_.zip" in key: continue
                if "Only" in key:
                        parts = key.replace(".zip","").split("-")
                        channelText = parts[len(parts)-1].split("_")
                        channel = channelText[1]
                        theChannels.append(channel)
        #print("theChannels: {}".format(theChannels))

        #Bar chart for first set of main data.  The non-EMLSR data.
        labels = []
        dataSets = {}
        resultsByChannel = {}
        for key in testResultLogJson:
                if "_.zip" in key: continue
                useIt = False
                thisLabel = ""
                thisChannel = "?"
                type = None
                for channel in theChannels:
                        if str(channel) in key: thisChannel = str(channel)                
                if "Throughput-Channel" in key:
                        useIt = True
                        thisLabel = "Throughput, channel {}".format(thisChannel)
                        type = "alone"
                elif "Throughput-With-Interference" in key:
                        useIt = True
                        thisLabel = "Throughput+Ix, channel {}".format(thisChannel)
                        type = "withIx"
                elif "Only" in key:
                        useIt= True
                        thisLabel = "IX only, channel {}".format(thisChannel)
                        type = "IxOnly"
                if useIt:
                        #print("The key is {}".format(key))
                        #print("The label is {}".format(thisLabel))
                        #print("The type is {}".format(type))
                        #print("The main pair is {}".format(mainTrafficPair))
                        labels.append(thisLabel)
                        for pair in testResultLogJson[key]:
                                #print("Checking pair {}".format(pair))
                                if pair==mainTrafficPair:
                                        index="main"
                                else:
                                        for chan in obssPairByChannel:
                                                if obssPairByChannel[chan]==pair:
                                                        index = "Ix, channel {}".format(chan)
                                #print("The index is {}".format(index))                                                        
                                if index not in dataSets: dataSets[index] = [testResultLogJson[key][pair]["throughput"]]
                                else: dataSets[index].append(testResultLogJson[key][pair]["throughput"])
                                
                                if thisChannel not in resultsByChannel: resultsByChannel[thisChannel] = {}
                                if type=="alone" and "alone" not in resultsByChannel[thisChannel] and index=="main":
                                        resultsByChannel[thisChannel]["alone"] = testResultLogJson[key][pair]["throughput"]
                                if type=="withIx":
                                        if index not in resultsByChannel[thisChannel]:
                                                if testResultLogJson[key][pair]["throughput"] != None:
                                                        resultsByChannel[thisChannel][index] = testResultLogJson[key][pair]["throughput"]
                                                else: resultsByChannel[thisChannel][index] = 0
                                if type=="IxOnly":
                                        if "Ix{}".format(thisChannel) not in resultsByChannel[thisChannel]:
                                                if testResultLogJson[key][pair]["throughput"] != None:
                                                        resultsByChannel[thisChannel]["Ix{}".format(thisChannel)] = testResultLogJson[key][pair]["throughput"]
                                                else: x=1 #resultsByChannel[thisChannel]["Ix{}".format(thisChannel)] = 0
                                                        
        #print("resultsByChannel: {}".format(resultsByChannel))
        for channel in resultsByChannel:
                theseResults = resultsByChannel[channel]
                for entry in theseResults:
                        if theseResults[entry]==None: theseResults[entry]=0
        #print("resultsByChannel: {}".format(resultsByChannel))
        
        barData = []
        idx = 0
        for key in dataSets:
                barData.append({
                        "label":key,
                        "color":iro[idx],
                        "width":1,
                        "radius":0,
                        "data":dataSets[key],
                        "fill": False,
                        "style": 'solid',
                        "barPercentage": 2
                })
                idx += 1
        item = {
                "elementType":"plot",
                "plotHeight": "800px",
                "plotWidth":  "2000px",
                "type":"bar",
                "title":"Non-EMLSR traffic rates",
                "labels":labels,
                "xaxis":{"string":"Test"},
                "yaxis":{"string":"Throughput [Mbps]"},
                "showDataValues":{"show":False},
                "showTable":False,
                "data": barData
        }
        myReport["Report"].append(item);

        item = {
                'elementType':'section',
                'headingType':'h1',
                'justification':'left',
                'headingContent':'Non-EMLSR results'
        }
        myReport["Report"].append(item);
        

        for channel in theChannels:
                Text = "<span style='font-size:30px;'>"
                BaselineThroughput = resultsByChannel[channel]["alone"]
                OBSSThroughput = resultsByChannel[channel]["Ix{}".format(channel)]
                InterferedThroughput = resultsByChannel[channel]["main"]
                InterferedOBSS = resultsByChannel[channel]["Ix, channel {}".format(channel)]
                Text += "On channel {}, the baseline throughput is {:.1f} Mbps, and the OBSS traffic trying to send {:.1f} Mbps\n".format(channel,BaselineThroughput,OBSSThroughput)
                Text += "With the OBSS traffic running on top of the baseline, we get {:.1f} Mbps of traffic, and {:.1f} Mbps of OBSS traffic.\n".format(InterferedThroughput,InterferedOBSS)
                try: MainReduction = (InterferedThroughput-BaselineThroughput)/BaselineThroughput*100
                except: MainReduction = 0
                try: OBSSReduction = (InterferedOBSS-OBSSThroughput)/OBSSThroughput*100
                except: OBSSReduction = 0
                Text += "This is a reduction in the main throughput by {:.1f}%, and the OBSS traffic is reduced by {:.1f}%\n".format(MainReduction,OBSSReduction)
                Text += "</span>"
                item = {
                        'elementType':'section',
                        'headingType':'h2',
                        'justification':'left',
                        'headingContent':'Channel {} results'.format(channel),
                        'text': Text
                }
                myReport["Report"].append(item);
                
        item = {
                'elementType':'section',
                'headingType':'h1',
                'justification':'left',
                'headingContent':'EMLSR results'
        }
        myReport["Report"].append(item);        

        #Bar chart for second set of main data.  The EMLSR data.
        labels = []
        dataSets = {}
        eMLSRresults = {}
        for key in testResultLogJson:
                if "_.zip" in key: continue
                useIt = False
                thisLabel = ""
                thisChannel = "?"
                for channel in theChannels:
                        if str(channel) in key: thisChannel = str(channel)            
                if "Throughput-EMLSR" in key and "Interference" not in key:
                        useIt = True
                        thisLabel = "Throughput, EMLSR"
                elif "Throughput-EMLSR" in key and "Interference" in key and "All" not in key:
                        useIt = True
                        thisLabel = "EMLSR Throughput+Ix, channel {}".format(thisChannel)                        
                elif "EMLSR" in key and "All" in key:
                        useIt= True
                        thisLabel = "EMLSR Throughput with IX on all channels"
                if useIt:
                        labels.append(thisLabel)
                        for pair in testResultLogJson[key]:
                                if pair==mainTrafficPair:
                                        index="main"
                                else:
                                        for chan in obssPairByChannel:
                                                if obssPairByChannel[chan]==pair:
                                                        index = "Ix, channel {}".format(chan)
                                if index not in dataSets: dataSets[index] = [testResultLogJson[key][pair]["throughput"]]
                                else: dataSets[index].append(testResultLogJson[key][pair]["throughput"])

                                if "Throughput-EMLSR" in key and "alone" not in eMLSRresults and index=="main":
                                        eMLSRresults["alone"] = testResultLogJson[key][pair]["throughput"]
                                elif "Throughput-EMLSR" in key and "Interference" in key and "All" not in key:
                                        if thisChannel not in eMLSRresults: eMLSRresults[thisChannel] = {}
                                        if index not in eMLSRresults[thisChannel]:
                                                if testResultLogJson[key][pair]["throughput"] != None:
                                                        eMLSRresults[thisChannel][index] = testResultLogJson[key][pair]["throughput"]
                                                else:   eMLSRresults[thisChannel][index] = 0
                                elif "EMLSR" in key and "All" in key and "withIxAll" not in eMLSRresults:
                                        if "All" not in eMLSRresults: eMLSRresults["All"] = {}
                                        if index not in eMLSRresults["All"]:
                                                if testResultLogJson[key][pair]["throughput"] != None:
                                                        eMLSRresults["All"][index] = testResultLogJson[key][pair]["throughput"]
                                                else:
                                                        eMLSRresults["All"][index] = 0

        #print("eMLSR results: {}".format(eMLSRresults))
        for key in eMLSRresults:
                if eMLSRresults[key]==None: eMLSRresults[key]=0
        #print("eMLSR results: {}".format(eMLSRresults))

        barData = []
        idx = 0
        for key in dataSets:
                barData.append({
                        "label":key,
                        "color":iro[idx],
                        "width":1,
                        "radius":0,
                        "data":dataSets[key],
                        "fill": False,
                        "style": 'solid',
                        "barPercentage": 1
                })
                idx += 1
        item = {
                "elementType":"plot",
                "plotHeight": "800px",
                "plotWidth":  "2000px",
                "type":"bar",
                "title":"EMLSR traffic rates",
                "labels":labels,
                "xaxis":{"string":"Test"},
                "yaxis":{"string":"Throughput [Mbps]"},
                "showDataValues":{"show":False},
                "showTable":False,
                "data": barData
        }
        myReport["Report"].append(item);

        #print(eMLSRresults)
        Text = "<span style='font-size:30px;'>"
        BaselineThroughput = eMLSRresults["alone"]
        Text += "For eMLSR, the baseline throughput is {:.1f} Mbps".format(BaselineThroughput)
        Text += "</span>"
        item = {
                'elementType':'text',
                'text': Text
        }
        myReport["Report"].append(item);

        for channel in theChannels:
                Text = "<span style='font-size:30px;'>"
                InterferedThroughput = eMLSRresults[channel]["main"]
                OBSSThroughput = resultsByChannel[channel]["Ix{}".format(channel)]
                InterferedOBSS = eMLSRresults[channel]["Ix, channel {}".format(channel)]
                try: MainReduction = (InterferedThroughput-BaselineThroughput)/BaselineThroughput*100
                except: MainReduction = 0
                try: OBSSReduction = (InterferedOBSS-OBSSThroughput)/OBSSThroughput*100
                except: OBSSReduction = 0
                Text += "With the OBSS traffic running on top of the eMLSR baseline, we get {:.1f} Mbps of traffic, and {:.1f} Mbps of OBSS traffic.\n".format(InterferedThroughput,InterferedOBSS)
                try: MainReduction = (InterferedThroughput-BaselineThroughput)/BaselineThroughput*100
                except: MainReduction = 0
                try: OBSSReduction = (InterferedOBSS-OBSSThroughput)/OBSSThroughput*100
                except: OBSSReduction = 0
                Text += "This is a reduction in the main throughput by {:.1f}%, and the OBSS traffic is reduced by {:.1f}%\n".format(MainReduction,OBSSReduction)
                Text += "</span>"
                item = {
                        'elementType':'section',
                        'headingType':'h2',
                        'justification':'left',
                        'headingContent':'Channel {} results'.format(channel),
                        'text': Text
                }
                Text += "</span>"
                myReport["Report"].append(item);

        Text = "<span style='font-size:30px;'>"
        InterferedThroughput = eMLSRresults["All"]["main"]
        try: MainReduction = (InterferedThroughput-BaselineThroughput)/BaselineThroughput*100
        except: MainReduction = 0
        Text += "With all channels of OBSS traffic running on top of the eMLSR baseline, we get {:.1f} Mbps of traffic, a reduction of {:.1f} %.\n".format(InterferedThroughput,MainReduction)
        for channel in theChannels:
                OBSSThroughput = resultsByChannel[channel]["Ix{}".format(channel)]
                InterferedOBSS = eMLSRresults["All"]["Ix, channel {}".format(channel)]
                try: OBSSReduction = (InterferedOBSS-OBSSThroughput)/OBSSThroughput*100
                except: OBSSReduction = 0
                Text += "With all channels of OBSS traffic running on top of the eMLSR baseline, we get {:.1f} Mbps of channel {} OBSS traffic, a reduction of {:.1f} %.\n".format(OBSSThroughput,channel,OBSSReduction)
        Text += "</span>"
        item = {
                'elementType':'section',
                'headingType':'h2',
                'justification':'left',
                'headingContent':'All Channel Interference results',
                'text': Text
        }
        myReport["Report"].append(item);

        item = {
                'elementType':'section',
                'headingType':'h1',
                'justification':'left',
                'headingContent':'Aggregate Throughput Viewpoint'
        }
        myReport["Report"].append(item);

        for channel in theChannels:
                text = "<span style='font-size:30px;'>"
                thisData = resultsByChannel[channel]
                thisIx = "Ix{}".format(channel)
                
                thisDesiredAggregate = thisData[thisIx] + thisData["alone"]
                thatIx = "Ix, channel {}".format(channel)
                thisActualAggregate = thisData["main"] + thisData[thatIx]
                try: thisActualReduction = (thisActualAggregate-thisDesiredAggregate)/thisDesiredAggregate * 100
                except: thisActualReduction = 0
                word = "enhancement" if thisActualReduction > 0 else "reduction"
                text += "For channel {}:\nThe desired total throughput is {:.1f}, and the achieved total without eMLSR is {:.1f}, a {:.1f}% {}.\n".format(channel,thisDesiredAggregate,thisActualAggregate,thisActualReduction,word)
                eMLSRAggregate = eMLSRresults[channel]["main"] + eMLSRresults[channel][thatIx]
                eMLSRReduction = (eMLSRAggregate-thisDesiredAggregate)/thisDesiredAggregate * 100
                word = "enhancement" if eMLSRReduction > 0 else "reduction"
                text += "With eMLSR, the achieved total is {:.1f}, a {:.1f}% {}.\n".format(eMLSRAggregate,eMLSRReduction,word)
                eMLSREnhancement = (eMLSRAggregate-thisActualAggregate)/thisActualAggregate * 100
                word = "enhancement" if eMLSREnhancement > 0 else "reduction"
                text += "Compared to the non-eMLSR case, with eMLSR there is a {:.1f}% {} in the total achieved throughput.\n\n".format(eMLSREnhancement,word)
                text += "</span>"
                #print(text)
                item = {
                        'elementType':'text',
                        'text':text
                }
                myReport["Report"].append(item);

        item = {
                'elementType':'section',
                'headingType':'h1',
                'justification':'left',
                'headingContent':'EMLSR Throughput Time Plots'
        }
        myReport["Report"].append(item);
        zipsToAnalyze = []
        zipsToAnalyze.append("Throughput-EMLSR.zip")
        for channel in theChannels: zipsToAnalyze.append("Throughput-EMLSR-With-Interference-Channel_{}.zip".format(channel))
        zipsToAnalyze.append("Throughput-EMLSR-With-Interference_All.zip")
        #print(zipsToAnalyze)
        #print("palToUse: {}".format(palToUse))
        #print("obssInfo: {}".format(obssInfo))
        #print("obssPairByChannel: {}".format(obssPairByChannel))        
        item = {'elementType':'gridFormatting','action':'start'}
        myReport["Report"].append(item);
        for zip in zipsToAnalyze:
                with open(json_dir+zip, "rb") as f:
                        bytes = f.read()
                        encoded = base64.b64encode(bytes)
                        api_endpoint = ea_root + "zip2csv"
                        data = {'zip':encoded}
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        csv = theJson["csv"]
                        f.close()

                        #print('\n### Running getStats')
                        #Get basic test results information
                        api_endpoint = ea_root + "getStats"
                        data = {'csv':csv,'filter':'counts'}
                        try:  r = requests.post(url=api_endpoint, data=data, timeout=5)
                        except requests.exceptions.RequestException as error:
                                info("Error: ", error)
                                sys.exit(44)

                        y = json.loads(r.text)
                        #print('\nStats for read-in data: >>> y: ', y)
                        trafficPairMap = y["filteredData"]["trafficPairs"]["map"]

                        # Analyze the CSV file
                        api_endpoint = ea_root + "objectify"
                        data = {'csv':csv}
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)
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
                        
                        dataSets = []
                        mainTraffic = []
                        for datum in dataSet:
                                #print (datum["{} Throughput [Mbps]".format(mainTrafficPair)])
                                try:
                                        value = datum["{} Throughput [Mbps]".format(mainTrafficPair)]
                                        #print(value)
                                        theY = float(value)
                                        mainTraffic.append({'x': datum['Time [ms]'], 'y':theY})
                                except:
                                        error = "some kind of error"
                                        #print(error)
                        dataSets.append({'label':"Main throughput",'color':iro[0],'width':1,'data':mainTraffic,'fill':-1})

                        idx = 0
                        for channel in theChannels:
                                idx += 1
                                channelData = []
                                if "Interference" in zip and (channel in zip or "All" in zip):
                                        thisPair = obssPairByChannel[channel]
                                        for datum in dataSet:
                                                #print (datum["{} Throughput [Mbps]".format(thisPair)])
                                                try:
                                                        value = datum["{} Throughput [Mbps]".format(thisPair)]
                                                        #print(value)
                                                        theY = float(value)
                                                        channelData.append({'x': datum['Time [ms]'], 'y':theY})
                                                except:
                                                        error = "some kind of error"
                                                        #print(error)
                                        dataSets.append({'label':"OBSS traffic, channel {}".format(channel),'color':iro[idx],'width':1,'data':json.loads(json.dumps(channelData)),'fill':-1})
                        
                        item = {'elementType':'gridFormatting','action':'newItem','padding-left':20,'padding-right':20}
                        myReport["Report"].append(item);
                        item = {
                                'elementType':'plot',
                                'type': 'scatter',
                                'title': 'Time series of main EMLSR throughput',
                                'xaxis':{'string':'Time (msec)'},
                                'yaxis':{'string':'Throughput (Mbps)','min':0},
                                'showTable': False,
                                'data': dataSets
                        }
                        myReport["Report"].append(item);
                        item = {'elementType':'gridFormatting','action':'endItem'}
                        myReport["Report"].append(item);
                        #print(item)
                                
        item = {'elementType':'gridFormatting','action':'end'}
        myReport["Report"].append(item);
                
        item = {
                'elementType':'section',
                'headingType':'h1',
                'justification':'left',
                'headingContent':'Latency Analysis'
        }
        myReport["Report"].append(item)

        item = {
                'elementType':'section',
                'headingType':'h2',
                'justification':'left',
                'headingContent':'Non-eMLSR Latency Analysis'
        }
        myReport["Report"].append(item)
        
        item = {'elementType':'gridFormatting','action':'start'}
        myReport["Report"].append(item);
        
        for channel in theChannels:
                dataSets = []
                cleanZip = "Throughput-Channel_{}.zip".format(channel)
                csv,headers,dataSet = getPalData(json_dir+cleanZip,ea_root)
                thisData = []
                for datum in dataSet:
                        try:
                                value = datum["{} iPerf2 Latency Mean [ms]".format(mainTrafficPair)]
                                theY = float(value)
                                #thisData.append({'x': datum['Time [ms]'], 'y':theY})
                                thisData.append(theY)
                        except:
                                error = "some kind of error"
                                #print(error)
                #print(thisData)
                api_endpoint = ea_root + "createCdfFrom"
                data = {'data':thisData,'norm':0,'dir':0}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)
                #print(theJson)
                theCDF = theJson['cdf']

                dataSets.append({'label':"Latency",'color':iro[0],'width':1,'data':json.loads(json.dumps(theCDF)),'fill':-1})

                dirtyZip = "Throughput-With-Interference-Channel_{}.zip".format(channel)
                csv,headers,dataSet = getPalData(json_dir+dirtyZip,ea_root)
                thisData = []
                for datum in dataSet:
                        try:
                                value = datum["{} iPerf2 Latency Mean [ms]".format(mainTrafficPair)]
                                theY = float(value)
                                #thisData.append({'x': datum['Time [ms]'], 'y':theY})
                                thisData.append(theY)
                        except:
                                error = "some kind of error"
                                #print(error)
                #print(thisData)
                api_endpoint = ea_root + "createCdfFrom"
                data = {'data':thisData,'norm':0,'dir':0}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)
                #print(theJson)
                theCDF = theJson['cdf']

                dataSets.append({'label':"Latency with channel {} Interference".format(channel),'color':iro[1],'width':1,'data':json.loads(json.dumps(theCDF)),'fill':-1})                        
                        
                item = {'elementType':'gridFormatting','action':'newItem','padding-left':20,'padding-right':20}
                myReport["Report"].append(item);
                item = {
                        'elementType':'plot',
                        'type': 'scatter',
                        'title': 'Latency CDFs',
                        'xaxis':{'string':'Time (msec)'},
                        'yaxis':{'string':'Latency (ms)','min':0},
                        'showTable': False,
                        'data': dataSets
                }
                myReport["Report"].append(item);
                item = {'elementType':'gridFormatting','action':'endItem'}
                myReport["Report"].append(item);

        item = {'elementType':'gridFormatting','action':'end'}
        myReport["Report"].append(item);

        item = {
                'elementType':'section',
                'headingType':'h2',
                'justification':'left',
                'headingContent':'eMLSR Latency Analysis'
        }
        myReport["Report"].append(item)
        
        
        dataSets = []
        cleanZip = "Throughput-EMLSR.zip"
        csv,headers,dataSet = getPalData(json_dir+cleanZip,ea_root)
        thisData = []
        for datum in dataSet:
                try:
                        value = datum["{} iPerf2 Latency Mean [ms]".format(mainTrafficPair)]
                        theY = float(value)
                        #thisData.append({'x': datum['Time [ms]'], 'y':theY})
                        thisData.append(theY)
                except:
                        error = "some kind of error"
                        #print(error)
        #print(thisData)
        api_endpoint = ea_root + "createCdfFrom"
        data = {'data':thisData,'norm':0,'dir':0}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        #print(theJson)
        theCDF = theJson['cdf']
        
        dataSets.append({'label':"Latency",'color':iro[0],'width':1,'data':json.loads(json.dumps(theCDF)),'fill':-1})

        idx = 0
        for channel in theChannels:
                idx += 1
                dirtyZip = "Throughput-EMLSR-With-Interference-Channel_{}.zip".format(channel)
                csv,headers,dataSet = getPalData(json_dir+dirtyZip,ea_root)
                thisData = []
                for datum in dataSet:
                        try:
                                value = datum["{} iPerf2 Latency Mean [ms]".format(mainTrafficPair)]
                                theY = float(value)
                                #thisData.append({'x': datum['Time [ms]'], 'y':theY})
                                thisData.append(theY)
                        except:
                                error = "some kind of error"
                                #print(error)
                #print(thisData)
                api_endpoint = ea_root + "createCdfFrom"
                data = {'data':thisData,'norm':0,'dir':0}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)
                #print(theJson)
                theCDF = theJson['cdf']

                dataSets.append({'label':"Latency with channel {} interference".format(channel),'color':iro[idx],'width':1,'data':json.loads(json.dumps(theCDF)),'fill':-1})

        dirtyZip = "Throughput-EMLSR-With-Interference_All.zip"
        csv,headers,dataSet = getPalData(json_dir+dirtyZip,ea_root)
        thisData = []
        for datum in dataSet:
                try:
                        value = datum["{} iPerf2 Latency Mean [ms]".format(mainTrafficPair)]
                        theY = float(value)
                        #thisData.append({'x': datum['Time [ms]'], 'y':theY})
                        thisData.append(theY)
                except:
                        error = "some kind of error"
                        #print(error)
        #print(thisData)
        api_endpoint = ea_root + "createCdfFrom"
        data = {'data':thisData,'norm':0,'dir':0}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        #print(theJson)
        theCDF = theJson['cdf']

        idx += 1
        idx = idx % len(iro)
        dataSets.append({'label':"Latency with all interference",'color':iro[idx],'width':1,'data':json.loads(json.dumps(theCDF)),'fill':-1})
                
        item = {
                'elementType':'plot',
                'type': 'scatter',
                'title': 'Latency CDFs',
                'xaxis':{'string':'Time (msec)'},
                'yaxis':{'string':'Latency (ms)','min':0},
                'showTable': False,
                'data': dataSets
        }
        myReport["Report"].append(item);                        
        
        
        ############################## PCAP Analysis Starts Here
        item = {
                'elementType':'section',
                'headingType':'h1',
                'justification':'left',
                'headingContent':'PCAP Analysis'
        }
        myReport["Report"].append(item)

        eMLSRpcap = "EMLSR-Capture.pcap"
        if os.path.exists(json_dir+eMLSRpcap):
                totalCount = getCount(eMLSRpcap,json_dir,ea_root)
                print("The number of packets for {} is {}".format(eMLSRpcap,totalCount))
                useMax = min(20000,totalCount)                

                api_endpoint = ea_root + "pcapAPI?action=getMLO&fileName={}&pcapDir={}&lastPacket={}".format(eMLSRpcap,json_dir,useMax)
                print("Calling endpoint:\n {}".format(api_endpoint))
                theResponse = requests.get(url=api_endpoint)
                theJson = json.loads(theResponse.text)

                item = {
                        'elementType':'section',
                        'headingType':'h1',
                        'justification':'left',
                        'headingContent':'MLD Details'
                }
                myReport["Report"].append(item);                
                try:
                        apMLD = theJson["retObj"]["AP_MLD"]
                        mldText = json.dumps(apMLD,indent=3)
                        text = "<pre>{}</pre>".format(mldText)
                except: text = "No AP MLD found"
                item = {'elementType':'gridFormatting','action':'start'}
                myReport["Report"].append(item);
                item = {'elementType':'gridFormatting','action':'newItem','padding-left':200,'padding-right':200}
                myReport["Report"].append(item);
                item = {
                        'elementType':'section',
                        'headingType':'h2',
                        'justification':'left',
                        'headingContent':'AP MLD',
                        'text': "<span style='font-size:30px;'>{}</span>".format(text)
                }
                myReport["Report"].append(item);
                item = {'elementType':'gridFormatting','action':'endItem'}
                myReport["Report"].append(item);

                try:
                        staMLD = theJson["retObj"]["STA_MLD"]
                        mldText = json.dumps(staMLD,indent=3)
                        text = "<pre>{}</pre>".format(mldText)                
                except: text = "No STA MLD found"
                item = {'elementType':'gridFormatting','action':'newItem','padding-left':200,'padding-right':200}
                myReport["Report"].append(item);
                item = {
                        'elementType':'section',
                        'headingType':'h2',
                        'justification':'left',
                        'headingContent':'STA MLD',
                        'text': "<span style='font-size:30px;'>{}</span>".format(text)
                }
                myReport["Report"].append(item);
                item = {'elementType':'gridFormatting','action':'endItem'}
                myReport["Report"].append(item);
                item = {'elementType':'gridFormatting','action':'end'}
                myReport["Report"].append(item);

                returnedReportText = theJson["retObj"]["JsonReport"]
                returnedReport = json.loads(returnedReportText)
                returnedReportItems = returnedReport["Report"]
                        
        channelToFreq = {}
        bssidMap = {}
        obssIDs = []        
        # Use the interference-only captures to find the MAC addresses of the OBSS APs, and the OBSS STAs.
        for channel in theChannels:
                IxPCAP = "Only-Interference-Channel_{}.pcap".format(channel)
                if os.path.exists(json_dir+IxPCAP):
                        totalCount = getCount(IxPCAP,json_dir,ea_root)
                        print("The number of packets for {} is {}".format(IxPCAP,totalCount))
                        useMax = min(10000,totalCount)
                        beaconObj = getPacketTypes(IxPCAP,json_dir,ea_root,["Beacon"],useMax)
                        beaconData = {}
                        for item in beaconObj["perStreamStats"]:
                                beaconData[item["transmitterAddress"]] = {"count":item["count"],"channel":item["rssiPlot"][0]["channel"]}
                        #print(beaconData)
                        streamObj = getMainStream(IxPCAP,json_dir,ea_root,useMax)
                        streamData = streamObj["perChannelResults"]
                        #print(streamData)
                        BSSIDs = {}
                        theFreq = streamObj["result"]["channel"]
                        APs = []
                        for bssid in beaconData:
                                if beaconData[bssid]["channel"] == theFreq: APs.append(bssid)
                        strFreq = str(theFreq)
                        if streamData[strFreq]["from"] in APs:
                                try:    BSSIDs["AP"] =  streamData[strFreq]["from"]
                                except: BSSIDs["AP"] =  "N/A 1"
                                try:    BSSIDs["STA"] = streamData[strFreq]["to"]
                                except: BSSIDs["STA"] = "N/A 2"
                        elif streamData[strFreq]["to"] in APs:
                                try:    BSSIDs["AP"] =  streamData[strFreq]["to"]
                                except: BSSIDs["AP"] =  "N/A 3"
                                try:    BSSIDs["STA"] = streamData[strFreq]["from"]
                                except: BSSIDs["STA"] = "N/A 4"
                        #print(BSSIDs)
                        if channel not in channelToFreq: channelToFreq[channel] = theFreq
                        bssidMap["OBSS-AP_{}".format(channel)] = BSSIDs["AP"]
                        bssidMap["OBSS-STA_{}".format(channel)] = BSSIDs["STA"]
                        obssIDs.append(BSSIDs["AP"])
                        obssIDs.append(BSSIDs["STA"])
        print("BSSID Map so far: {}".format(bssidMap))
        print("channelToFreq map: {}".format(channelToFreq))
        
        # Now use the traffic runs for non-eMLSR to identify the MAC addresses for the DUT on the different bands, and the STA on the different bands.
        linkAPs = []
        for channel in theChannels:
                TputPCAP = "Throughput-Channel_{}.pcap".format(channel)
                frequency = channelToFreq[channel]
                if os.path.exists(json_dir+TputPCAP):
                        totalCount = getCount(TputPCAP,json_dir,ea_root)
                        print("The number of packets for {} is {}".format(TputPCAP,totalCount))
                        useMax = min(10000,totalCount)
                        beaconObj = getPacketTypes(TputPCAP,json_dir,ea_root,["Beacon"],useMax)
                        beaconData = {}
                        for item in beaconObj["perStreamStats"]:
                                beaconData[item["transmitterAddress"]] = {"count":item["count"],"channel":item["rssiPlot"][0]["channel"]}
                        #print(beaconData)
                        bssidMap["Link-AP_{}".format(channel)] = None
                        for mac in beaconData:
                                if beaconData[mac]["channel"] != frequency: continue
                                if bssidMap["Link-AP_{}".format(channel)] == None:
                                        bssidMap["Link-AP_{}".format(channel)] = mac
                                        currentMax = beaconData[mac]["count"]
                                if beaconData[mac]["count"] > currentMax:
                                        bssidMap["Link-AP_{}".format(channel)] = mac
                                        currentMax = beaconData[mac]["count"]
                        theAPmac = bssidMap["Link-AP_{}".format(channel)]
                        linkAPs.append(theAPmac)
                        #print(theAPmac)
                        streamObj = getMainStream(TputPCAP,json_dir,ea_root,useMax)
                        streamData = streamObj["perChannelResults"]
                        thisStream = streamData[str(frequency)]
                        #print(thisStream)
                        theSTAmac = None
                        if thisStream["from"]==theAPmac: theSTAmac = thisStream["to"]
                        elif thisStream["to"]==theAPmac: theSTAmac = thisStream["from"]
                        #print(theSTAmac)
                        bssidMap["Link-STA_{}".format(channel)] = theSTAmac
                                        
        print("BSSID Map so far: {}".format(bssidMap))

        tableData = [{"label":"Device","data":[]},{"label":"Address","data":[]}]
        for device in bssidMap:
                tableData[0]["data"].append(device)
                tableData[1]["data"].append(bssidMap[device])
        
        item = {
                "elementType":"table",
                "type":"table",
                "title":"Addresses for various devices extracted from PCAPs",
                "data": tableData
        }
        myReport["Report"].append(item);

        configs = []
        for channel in theChannels:
                frequency = channelToFreq[channel]
                strFrequency = str(frequency)
                configs.append( {"channel":channel,"frequency":frequency,"AP_Link_MAC":apMLD[strFrequency]["MAC"],"band": apMLD[strFrequency]["band"]} )
        #print(configs)

        filesToAnalyze = []
        
        filesToAnalyze.append("Throughput-EMLSR_.pcap")
        for channel in theChannels: filesToAnalyze.append("Throughput-EMLSR-With-Interference-Channel_{}_.pcap".format(channel))
        filesToAnalyze.append("Throughput-EMLSR-With-Interference_All_.pcap")

        #filesToAnalyze.append("Throughput-EMLSR.pcap")
        #for channel in theChannels: filesToAnalyze.append("Throughput-EMLSR-With-Interference-Channel_{}.pcap".format(channel))
        #filesToAnalyze.append("Throughput-EMLSR-With-Interference_All.pcap")

        
        print("Analyzing these files: {}".format(filesToAnalyze))
        
        htmlFile = generateTheReport(myReport,theTitle,directory_name)        
        
        for fileToUse in filesToAnalyze:
                if os.path.exists(json_dir+fileToUse):

                        item = {
                                'elementType':'section',
                                'headingType':'h1',
                                'justification':'left',
                                'headingContent':'Band breakdown for {}'.format(fileToUse)
                        }
                        myReport["Report"].append(item);                
                        
                        pcap_file = fileToUse
                        pcap_dir = json_dir
                        totalCount = getCount(fileToUse,json_dir,ea_root)
                        print("The number of packets for The {} capture is {}".format(fileToUse,totalCount))
                        useMax = min(50001,totalCount)

                        perChannelData = {}
                        for config in configs:
                                channel = config["channel"]
                                useFrom = config["AP_Link_MAC"]
                                filters = "QoS Data"
                                summedResults = None
                                chunkSize = 200000 #200000
                                firstPacket = 1
                                lastPacket = chunkSize
                                start_time = time.time()
                                processedPackets = 0
                                calls = 0
                                while firstPacket < totalCount: # and processedPackets<=20000:
                                        api_endpoint = ea_root + "pcapAPI?action=getTimeSeriesInfo&fileName={}&pcapDir={}&filters={}&firstPacket={}&lastPacket={}&from={}".format(pcap_file,pcap_dir,filters,firstPacket,lastPacket,useFrom)
                                        calls += 1
                                        print("#{}: Calling endpoint:\n {}".format(calls,api_endpoint))
                                        start_t = time.time()
                                        theResponse = requests.get(url=api_endpoint,timeout=600)
                                        theJson = json.loads(theResponse.text)
                                        stop_t = time.time()
                                        print("... interim time to get time series info for {} packets  = {} seconds.  {} sec/packet.".format(lastPacket-firstPacket+1,stop_t-start_t, (stop_t-start_t)/(lastPacket-firstPacket+1)))
                                        processedPackets += lastPacket-firstPacket+1
                                        theResult = theJson["result"]
                                        if summedResults == None: summedResults = json.loads(json.dumps(theResult))
                                        else:
                                                for plot in summedResults:
                                                        if plot not in theResult: continue
                                                        sumPlot = summedResults[plot]
                                                        try: lastTime = sumPlot[len(sumPlot)-1]["x"]
                                                        except: lastTime = 0
                                                        newPlot = theResult[plot]
                                                        for entry in newPlot: sumPlot.append({"x":lastTime+entry["x"],"y":entry["y"]})
                                                        summedResults[plot] = json.loads(json.dumps(sumPlot))
                                        firstPacket = lastPacket+1
                                        lastPacket += chunkSize
                                perChannelData[channel] = json.loads(json.dumps(summedResults))
                                stop_time = time.time()
                                print("Time to get time series info for {} packets  = {} seconds.  {} sec/packet.".format(totalCount,stop_time-start_time, (stop_time-start_time)/(processedPackets)))


                        item = {'elementType':'gridFormatting','action':'start'}
                        myReport["Report"].append(item);

                        #Pie chart of packet counts !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        item = {'elementType':'gridFormatting','action':'newItem','padding-left':0,'padding-right':0}
                        myReport["Report"].append(item);
                        item = {
                                'elementType':'plot',
                                'type': 'pie',
                                'title': 'Total packets per channel',
                                'labels': [],
                                'showDataValues':{'show':True,'color':'white','align':'bottom','offset':'12','fontSize':'30'},
                                'tableWidth':'1200px',
                                'showTable':False,
                                'data':[]
                        }
                        idx = 0
                        innerColor = []
                        innerData = []
                        for channel in perChannelData:
                                item['labels'].append(channel)
                                innerColor.append(iro[idx])
                                packetSum = 0
                                for datum in perChannelData[channel]["Packets"]: packetSum += datum["y"]
                                innerData.append(packetSum)
                                idx += 1
                        item['data'].append({"label":"Packet counts","color":innerColor,"data":innerData})
                        myReport["Report"].append(item);
                        item = {'elementType':'gridFormatting','action':'endItem'}
                        myReport["Report"].append(item);

                        firstStamp = 0
                        for channel in perChannelData:
                                stampData  = perChannelData[channel]["TimeStamps"]
                                if   firstStamp == 0 and len(stampData)>0 : firstStamp = stampData[0]["y"]
                                elif firstStamp != 0 and len(stampData)>0 :
                                        if stampData[0]["y"] < firstStamp: firstStamp = stampData[0]["y"]
                        print("The earliest timestamp found, and the one used to offset all times, is {}".format(firstStamp))
                        

                        #Time plot of packet counts !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                        item = {'elementType':'gridFormatting','action':'newItem','padding-left':0,'padding-right':0}
                        myReport["Report"].append(item);
                        item = {
                                'elementType':'plot',
                                'type': 'scatter',
                                'title': 'Time series of packet counts per channel',
                                'xaxis':{'string':'Time (sec)'},
                                'yaxis':{'string':'Packet count'},
                                'showTable': False,
                                'data':[]
                        }
                        innerData = []
                        idx = 0                        
                        for channel in perChannelData:
                                packetData = perChannelData[channel]["Packets"]
                                stampData  = perChannelData[channel]["TimeStamps"]
                                useData = []
                                for i in range (0,len(packetData)): useData.append({"x":stampData[i]["y"]-firstStamp, "y":packetData[i]["y"]})
                                innerData.append({'label':"Packets on channel {}".format(channel),'color':iro[idx],'width':1,'data':useData,'fill':-1})
                                idx += 1
                        item['data'] = innerData
                        myReport["Report"].append(item);
                        item = {'elementType':'gridFormatting','action':'endItem'}
                        myReport["Report"].append(item);

                        #Time plot of byte counts
                        item = {'elementType':'gridFormatting','action':'newItem','padding-left':0,'padding-right':0}
                        myReport["Report"].append(item);
                        item = {
                                'elementType':'plot',
                                'type': 'scatter',
                                'title': 'Time series of bytes per channel',
                                'xaxis':{'string':'Time (sec)'},
                                'yaxis':{'string':'Byte count'},
                                'showTable': False,
                                'data':[]
                        }
                        innerData = []
                        idx = 0
                        for channel in perChannelData:
                                packetData = perChannelData[channel]["Bytes"]
                                stampData  = perChannelData[channel]["TimeStamps"]
                                useData = []
                                for i in range (0,len(packetData)): useData.append({"x":stampData[i]["y"]-firstStamp, "y":packetData[i]["y"]})
                                innerData.append({'label':"Bytes on channel {}".format(channel),'color':iro[idx],'width':1,'data':useData,'fill':-1})
                                idx += 1
                        item['data'] = innerData
                        myReport["Report"].append(item);
                        item = {'elementType':'gridFormatting','action':'endItem'}
                        myReport["Report"].append(item);

                        #Time plot of throughput
                        item = {'elementType':'gridFormatting','action':'newItem','padding-left':0,'padding-right':0}
                        myReport["Report"].append(item);
                        item = {
                                'elementType':'plot',
                                'type': 'scatter',
                                'title': 'Time series of throughput per channel',
                                'xaxis':{'string':'Time (sec)'},
                                'yaxis':{'string':'Throughput (Mbps)'},
                                'showTable': False,
                                'data':[]
                        }
                        innerData = []
                        idx = 0
                        for channel in perChannelData:
                                packetData = perChannelData[channel]["Mbps"]
                                stampData  = perChannelData[channel]["TimeStamps"]
                                useData = []
                                for i in range (0,len(packetData)): useData.append({"x":stampData[i]["y"]-firstStamp, "y":packetData[i]["y"]})
                                innerData.append({'label':"Throughput on channel {}".format(channel),'color':iro[idx],'width':1,'data':useData,'fill':-1})
                                idx += 1
                        item['data'] = innerData
                        myReport["Report"].append(item);
                        item = {'elementType':'gridFormatting','action':'endItem'}
                        myReport["Report"].append(item);

                        item = {'elementType':'gridFormatting','action':'end'}
                        myReport["Report"].append(item);

                        htmlFile = generateTheReport(myReport,theTitle,directory_name)                                

        ###################################  PCAP ANALYSIS ENDS HERE
        
        
        main_end = time.time()

        text = "Total time to run the full analysis is {} seconds.\n".format(main_end-main_start)
        hms = str(datetime.timedelta(seconds=main_end-main_start))
        text += "In hours/minutes/seconds this is {}".format(hms)

        item = {
                'elementType':'section',
                'headingType':'h1',
                'justification':'left',
                'headingContent':'Complete post-processing analysis time',
                'text': text
        }
        myReport["Report"].append(item);                
        
        
        htmlFile = generateTheReport(myReport,theTitle,directory_name)        


        print("Total time to run the full analysis is {} seconds.".format(main_end-main_start))
        hms = str(datetime.timedelta(seconds=main_end-main_start))
        print("In hours/minutes/seconds this is {}".format(hms))

        return myReport

#===
#Use this for debugging.  Otherwise, comment it out.
'''
print("This is the debug section of simpleMLO, createReport.  Comment it out if you see it and don't expect to.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/eMLSR-Complete-Set/1_2025-09-15_11-46_eMLSR/"
json_dir = "/home/octoscope/Documents/automationResults/2025-09-24_14-18_BE-19000/1_2025-09-24_14-18_eMLSR/"
pcapFile = json_dir + "Only-Interference-Channel_36.pcap"
jsonFile = json_dir + "Only-Interference-Channel_36.zip"
ea_root = "http://localhost:8080/"

#retObj = extract(directory_name,json_dir,jsonFile,pcapFile,ea_root)
#print(retObj)

main(directory_name,json_dir,ea_root)
'''
