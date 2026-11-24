import sys
import json
import requests
import base64
import os
from pathlib import Path

colors = ["red","blue","green","orange","black","grey","purple"]

def formatMac(mac):
    fMac = mac.upper()
    fMac = fMac.replace(".","")
    fMac = fMac.replace(":","")
    return fMac

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
                theTitle = directoriesJson["title"]
                theName = theTitle.replace(" ","_")
        except:
                CL = ""
                theTitle = "Mesh Roaming"
                theName = theTitle.replace(" ","_")
        #print("Command line part is " + CL)
        print('>>> theTitle: ', theTitle)

        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        print('>>> createReport_main json_dir', json_dir)
        #Get all of the zip files in the json directory
        theZips = []
        for x in os.listdir(json_dir):
                if ".zip" in x:
                    #print (x)
                    if "CSV" not in x: theZips.append(json_dir + x)

        #Do the whole analysis part using the data in this zip file.
        theZips.sort(reverse=True)
        fileName = theZips[0]
        print("DEBUG: The file " + fileName)

        with open(fileName, "rb") as f:
                bytes = f.read()
                encoded = base64.b64encode(bytes)
                #print(encoded)
                api_endpoint = ea_root + "zip2csv"
                data = {'zip':encoded}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)
                #print(theJson)

        print("DEBUG: The json " + json_dir)
        # Find pcap files
        for x in os.listdir(json_dir):
                if "All_Sniffers.pcap" in x:
                    SnifferPCAP = x
                    print ('>>> createReport all sniffer pcap filename: ', SnifferPCAP)
                if "allAIDs.pcap" in x:
                    aidPCAP = x
                    print ('\n>>> createReport AID pcap filename: ', aidPCAP)

        #f = open(directory_name+'csv.csv', 'w')
        #f.write(theJson["csv"])
        #f.close()

        # Analyze the CSV file
        #csv_path = directory_name+'csv.csv'
        #csv = Path(csv_path).read_text()
        csv = theJson["csv"]
        #location = "local"
        api_endpoint = ea_root + "objectify"
        data = {'csv':csv}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)

        headers = theJson["headers"]
        dataSet = theJson["dataSet"]
        if "error" in theJson: print("objectify: This data returned an error: {}".format(theJson["error"]))

        api_endpoint = ea_root + "crunch"
        run = 1
        data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        if "error" in theJson: print("crunch: This data returned an error: {}".format(theJson["error"]))
        analyzedData = theJson["crunchedData"]
        theNotes = theJson["Notes"]
        #print(theNotes)

        #print("The number of traffic pairs for which you have data is {}".format(len(analyzedData)))


        #Write a report
        myReport = {}
        myReport["Title"] = "OFDMA Decoding using octoScope Software 2.0"
        myReport["Report"] = []

        item = {
                "elementType": "section",
                "headingType": "h1",
                "headingContent":"OFDMA Decoding using octoScope software 2.0"
        }
        myReport["Report"].append(item)

        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Overview",
                "text": "In this test run traffic between the device under test (DUT) and a STApals.\nUse sniffers to extract AIDs, and multiple sniffers to capture HE MU/TRIG packets."
        }
        myReport["Report"].append(item)


        if someData:

                item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Test configuration",
                   }
                myReport["Report"].append(item)

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
                            "802."+someData["iface"],someData["bw"],someData["channel"],someData["upOrDown"],someData["nss"]
                    ]
                    },
                    ]
                }
                myReport["Report"].append(item)

                #Don't bother with any of this.  The analysis already has this information.  Just pass it over.
                '''
                print('')
                print('############################################################')
                print(">>>(177) Let's find the transmitter address (BSSID) for Trigger frames.")
                print(">>> This can take up to 90 seconds.")
                URL = ea_root + "pcapAPI?fileName="+SnifferPCAP+"&pcapDir="+json_dir+"&action=getDataOfType&filters=Trigger"
                print('>>> URL: ',URL)
                theResponse = requests.get(url=URL, timeout=90)
                theJson = json.loads(theResponse.text)
                theResult = theJson["result"]
                stats = theResult["perStreamStats"]
                if len(stats) > 0:
                        theBssid = stats[0]["transmitterAddress"]
                        theBssid = formatMac(theBssid)
                        print("\n>>> The BSSID to use is {}".format(theBssid))
                        print('############################################################')

                #Get the AID list
                print('')
                print('############################################################')
                print(">>>(193) Get the AID list")
                print(">>> This can take up to 90 seconds.")
                URL = ea_root + "pcapAPI?fileName="+SnifferPCAP+"&pcapDir="+json_dir+"&action=getAIDlist"
                print('>>> URL: ',URL)
                theResponse = requests.get(url=URL, timeout=90)
                theJson = json.loads(theResponse.text)
                theResult = theJson["result"]
                lists = theResult["aidsPerBssid"]
                theList = None
                for list in lists:
                    if formatMac(list["bssid"]) == theBssid: theList = list["AIDs"]
                if theList:
                        theList.sort()
                        print("\n>>> The list of AIDs found is {}".format(theList))
                        print('############################################################')
                else:
                        print('')
                        print('############################################################')
                        print('!!!!! NO AIDs FOUND! Stopping analysis. RERUN test.')
                        print('############################################################')
                        sys.exit(1)

                #Get the AID-to-MAC map
                print('')
                print('############################################################')
                print(">>>(213) Get the AID-to-MAC map")
                print(">>> This can take up to 90 seconds.")
                URL = ea_root + "pcapAPI?fileName="+SnifferPCAP+"&pcapDir="+json_dir+"&action=getAID2MAC"
                print('>>> URL: ',URL)
                theResponse = requests.get(url=URL, timeout=90)
                theJson = json.loads(theResponse.text)
                theResult = theJson["result"]
                multiMap = theResult["multiMap"]
                theMap = None
                for map in multiMap:
                    if formatMac(map["bssid"]) == theBssid: theMap = map["map"]
                if theMap:
                        print("\n>>> The AID-to-MAC mapping for BSSID {} is {}".format(theBssid,theMap))
                        print('############################################################')
                else:
                        print('')
                        print('############################################################')
                        print('!!!!! NO AID-to-MAC mapping FOUND! Stopping analysis. RERUN test.')
                        print('############################################################')
                        sys.exit(1)

                Aid2MacMap = {}
                for item in theMap: Aid2MacMap[item["aid"]] = item["mac"]
                '''

                theBssid = formatMac(someData["bssidToUse"])
                theList = []
                for pal in someData["palBoxMACs"]: theList.append( someData["palBoxMACs"][pal]["aid"] )
                theList.sort()                
                Aid2MacMap = someData["Aid2MacMap"]

                print('\n>>> The BSSID to use is {} '.format(theBssid))
                print('\n>>> The list of AIDs found is {} '.format(theList))
                print('\n>>> Aid2MacMap: ', Aid2MacMap)

                aids = []
                macs = []
                formatting = []
                for aid,mac in Aid2MacMap.items():
                    aids.append(aid)
                    formatting.append({"background-color": colors[int(aid)%len(colors)]})
                    macs.append(mac)

                item = {
                    "elementType": "table",
                    "type": "table",
                    "title": "AID to MAC Mapping",
                    "tableWidth":"700px",
                    "data": [
                        {
                        "label": "AIDs",
                        "data": aids,
                        "formatting": formatting
                        },
                        {
                        "label": "MACs",
                        "data": macs
                        },
                    ]
                }
                myReport["Report"].append(item)

        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Alerts",
                "text": "List of any Alerts generated in the running of this test."
        }

        #print(theNotes)
        alerts = []
        if "Alerts" in theNotes: alerts = theNotes["Alerts"]
        if len(alerts) == 0:
                item = {
                    "elementType": "text",
                    "text": "\nThere are no Alerts to report."
                }
        myReport["Report"].append(item)

        #Total packets
        print('')
        print('############################################################')
        print(">>>(276) Get Total packets")
        #aUrl = ea_root + "pcapAPI?fileName=All_Sniffers.pcap&action=getTotalPacketCount"
        aUrl = ea_root + "pcapAPI?fileName="+SnifferPCAP+"&pcapDir="+json_dir+"&action=getTotalPacketCount"
        print('>>> aUrl: ',aUrl)
        theResponse = requests.get(url=aUrl, timeout=180)
        theJson = json.loads(theResponse.text)


        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"Packets Captured",
           }
        myReport["Report"].append(item)

        item = {
                "elementType": "text",
                "text": "Total packets captured\n" + str(theJson["result"])
        }
        myReport["Report"].append(item)
        print(">>> Total packets captured: " + str(theJson["result"]))
        print('############################################################')

        absoluteMaximum = 40000

        #Count packet types
        print('')
        print('############################################################')
        print(">>>(302) Start counting QoS Data and TCP packets for up to packet number {}".format(absoluteMaximum))
        print(">>> This can take up to 90 seconds.")
        thesePackets = []
        more = True
        start = 0
        end = 20000
        while more and end<absoluteMaximum: 
                aUrl = ea_root + "parsePCAP?fileName="+SnifferPCAP+"&pcapDir="+json_dir+"&filters=QoS Data,TCP&startAt=" + str(start) + "&endAt=" + str(end)
                #aUrl += "&preferTshark=true"
                print("Calling this: {} ".format(aUrl))
                theResponse = requests.get(url=aUrl, timeout=90)
                theJson = json.loads(theResponse.text)
                more = theJson["more"]
                #more = False  # For debugging
                #print('more: ', more)
                fields = theJson["fields"]
                for packet in fields:
                    if packet["packetType"]=="QoS Data" or packet["packetType"]=="TCP": thesePackets.append(packet)
                print(">>> From {} to {}, found {} QoS Data or TCP packets for a total of {}".format(start,end,len(fields),len(thesePackets)))
                print('############################################################')
                start = end + 1
                end += 20000

        print('')
        print('############################################################')
        print(">>>(325) Start counting He type packets")
        dataCount = len(thesePackets)
        notHe = 0
        he = 0
        heSU = 0
        heMU = 0
        heTrig = 0
        for packet in thesePackets:
                try:
                    if not packet["HEdata"]: notHe += 1
                except:
                    notHe += 1
                else:
                    he += 1
                    if packet["HEdata"]["PPDUformat"] == 0: heSU += 1
                    if packet["HEdata"]["PPDUformat"] == 2: heMU += 1
                    if packet["HEdata"]["PPDUformat"] == 3: heTrig += 1
        print('>>> Totals: notHe: %s, HeSU: %s, HeMU: %s, HeTrig: %s' % (notHe,heSU,heMU,heTrig))   
        print('############################################################')

        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"OFDMA Packet Type Breakdown",
           }
        myReport["Report"].append(item)

        item = {
                "elementType": "table",
                "type": "table",
                "title": "OFDMA Packet Type Count for QoS Data/TCP Packets",
                "tableWidth":"700px",
                "data": [
                {
                    "label": "Type",
                        "data": [
                            "Not HE","HE","HE-SU","HE-MU","HE-TRIG"
                        ]
                    },
                    {
                        "label": "Count",
                    "data": [
                        notHe,he,heSU,heMU,heTrig
                    ]
                    },
                ]
        }
        myReport["Report"].append(item)

        #Let's get triggers.  Just 1000 for now.
        #Count packet types

        print('')
        print('############################################################')
        print(">>>(376) Start counting triggers up to packet number {}".format(absoluteMaximum))
        triggers = []
        more = True
        start = 0
        end = 20000
        while more and len(triggers)<1000 and end<absoluteMaximum:
                aUrl = ea_root + "parsePCAP?fileName="+SnifferPCAP+"&pcapDir="+json_dir+"&filters=Trigger&startAt=" + str(start) + "&endAt=" + str(end)
                #aUrl += "&preferTshark=true"
                theResponse = requests.get(url=aUrl, timeout=90)
                print("Calling this: {} ".format(aUrl))
                theJson = json.loads(theResponse.text)
                more = theJson["more"]
                #print('more: ', more)
                fields = theJson["fields"]
                #print('fields: ', fields)
                if fields != []:
                    for packet in fields:
                        triggers.append(packet)
                        #print('triggers: ', triggers)
                else:
                    packet = 'no'
                print(">>> From {} to {}, found {} trigger packets. Running total is {}".format(start,end,len(fields),len(triggers)))
                start = end + 1
                end += 20000

        print('')
        print('############################################################')
        print(">>> Found {} total triggers.".format(len(triggers)))
        print('############################################################')

        countUsers = {}
        for trigger in triggers:
                value = len(trigger["triggerUser"])
                idx = str(value)
                if idx in countUsers: countUsers[idx] += 1
                else: countUsers[idx] = 1
        print('>>> User count from triggers: ',countUsers)
        print('############################################################')

        labels = []
        data = []
        color = []
        i = 0
        for key in countUsers:
                labels.append(key)
                data.append(countUsers[key])
                color.append(colors[i%len(colors)])
                i += 1

        item = {
                "elementType": "plot",
                "type": "pie",
                "title": "Users per trigger",
                "labels": labels,
                "showDataValues":{"show":True,"color":"white","align":"bottom","offset":"12","fontSize":"30"},
                "tableWidth":"700px",
                "data": [
                {
                    "label": "Users/Trigger",
                        "color": color,
                        "data": data
                    }
                ]
        }
        myReport["Report"].append(item)

        upTo = min(1000,len(triggers))

        item = {
                "elementType": "section",
                "headingType": "h2",
                "headingContent":"RU Allocations Per AID Extracted from Triggers, shown for {} Triggers".format(upTo)
           }
        myReport["Report"].append(item)

        #print(">>> This many triggers {}".format(len(triggers)))
        allDataLines = []
        count = 0
        for trigger in triggers:
                print('')
                print('############################################################')
                print('>>> trigger: ', trigger)
                count += 1
                if count > upTo: continue
                #print("********** {} ***********".format(trigger["packetNumber"]))
                for entry in trigger["triggerUser"]:
                        print('############################################################')
                        print('>>> entry: ', entry)
                        #print('>>> trigger["triggerUser"] ', trigger["triggerUser"])
                        print(">>> AID: {}, BW {}, range {}".format(entry["AID12"]["value"], entry["ruAllocation"]["BW"], entry["ruAllocation"]["subCarriers"]))
                        if entry["ruAllocation"]["subCarriers"]:
                                components = entry["ruAllocation"]["subCarriers"].split(",")
                                for component in components:
                                        print('############################################################')
                                        print(">>> component ", component)
                                        theSplit = component.split(":")
                                        thisDataLine = {"label":"Trigger {}, AID {}".format(trigger["packetNumber"],entry["AID12"]["value"]),
                                                                        "color": colors[entry["AID12"]["value"]%len(colors)],
                                                                        "width":1,
                                                                        "data":[{"x":theSplit[0],"y":trigger["packetNumber"]},{"x":theSplit[1],"y":trigger["packetNumber"]}],
                                                                        "fill":-1,
                                                                        "style":"solid"}
                                        allDataLines.append(thisDataLine)

        item = {
                "elementType": "plot",
                "type": "scatter",
                "title": "RU Allocations Per AID Extracted from Triggers",
                "xaxis":{"string":"Subcarrier number"},
                "yaxis":{"string":"Packet number of trigger"},
                "showTable":False,
                "showLegend":False,
                "data": allDataLines
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
        fileName = "OFDMA-Decode.html"
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
        jsonMessages["exampleMessage"] = {"val":{"_scriptMessage_":str(aids)},"label":"AIDs"}
        jsonMessages["_editable"] = False
        f = open(directory_name+'TestMessages.json', "w")
        f.write(json.dumps(jsonMessages,indent=4))
        f.close()

        print("{} Test messages have been generated. {}".format(cGreen,cNormal))

#===
#Use this for debugging.  Otherwise, comment it out.
'''
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2025-10-15_17-12_calix/1_2025-10-15_17-12_OFDMA-Decode/"
ea_root = "http://localhost:8080/"
someData = {
    "iface":"interface",
    "bw":"bandwidth",
    "channel":"primaryChannel",
    "upOrDown":"updn",
    "nss":"streams",
    "bssidToUse": "2c:27:9e:91:ba:13",
    "Aid2MacMap": {"2": '5c.b4.7e.be.e4.6b.', "1": '5c.b4.7e.c1.aa.11.', "3": '5c.b4.7e.c1.ab.10.', "4": '5c.b4.7e.be.50.f5.'},
    "palBoxMACs":{
        "L2C-STApal": {
            "macaddress": "5c:b4:7e:c1:aa:11",
            "address": "172.16.28.2",
            "aid": 1,
            "snifferName": "L4C-STApal",
            "snifferaddress": "172.16.28.4",
            "snifferAID": 1
        },
    "L5C-STApal": {
        "macaddress": "5c:b4:7e:c1:ab:10",
        "address": "172.16.28.5",
        "aid": 3,
        "snifferName": "L7C-STApal",
        "snifferaddress": "172.16.28.7",
        "snifferAID": 3
    },
    "L10C-STApal": {
        "macaddress": "5c:b4:7e:be:e4:6b",
        "address": "172.16.28.10",
        "aid": 2,
        "snifferName": "L12C-STApal",
        "snifferaddress": "172.16.28.12",
        "snifferAID": 2
    },
    "L13C-STApal": {
        "macaddress": "5c:b4:7e:be:50:f5",
        "address": "172.16.28.13",
        "aid": 4,
        "snifferName": "L15C-STApal",
        "snifferaddress": "172.16.28.15",
        "snifferAID": 4
    }
    }
    }
    
createReport(directory_name,json_dir,ea_root,someData)
'''
