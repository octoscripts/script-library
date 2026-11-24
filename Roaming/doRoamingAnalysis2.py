import os
import sys
import time
import requests
import json
from pathlib import Path
import math
import base64

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

def formatMAC(mac):
    fMAC = mac
    fMAC = fMAC.replace(".",":")
    fMAC = fMAC.upper()
    if(fMAC[len(fMAC)-1]==":"): fMAC = fMAC[0:len(fMAC)-1]
    fMAC = fMAC.strip()
    return fMAC

def bssidUpdate(bssidList,bssid):
    found = False
    for item in bssidList:
        if item["bssid"] == bssid:
            item["count"] += 1
            found = True
            break
    if not found: bssidList.append({"bssid":bssid, "count":1})
def listHasPacket(list,packetNumber):
    has = False
    for item in list:
        if item["packetNumber"] == packetNumber:
            has = True
            break
    return has
def thinArrayTo(array,maxPoints):
    thinnedArray = []
    if math.isnan(maxPoints):
        thinnedArray = array
    else:
        maxPoints = int(maxPoints)
        if len(array) > maxPoints:
            print("Trimming from {} points....".format(len(array)))
            stepSize = math.ceil(len(array)/maxPoints)
            for x in range (0,len(array),stepSize): thinnedArray.append(array[x])
            print("...to {} points.".format(len(thinnedArray)))
        else:
            thinnedArray = array
    return thinnedArray

def FrequencyToChannelNumber(frequency):
    # frequency is in MHz, and we are converting to the channel number.
    frequency = float(frequency)
    chNo = None
    if math.isnan(frequency):
        chNo = None
    elif frequency<3000:
        chNo = (frequency-2412)/5 + 1
        if chNo - int(chNo) == 0: chNo = int(chNo)
        else: chNo = None
    else:
        chNo = (frequency-5000)/5
        if chNo - int(chNo) == 0: chNo = int(chNo)
        else: chNo = None
    return chNo

def ChannelNumberToFrequency(chNo):
    # frequency is in MHz, and we are converting from the channel number.
    frequency = None
    if math.isnan(chNo):
        frequency = None
    elif chNo<20:
        frequency = (chNo-1)*5 +2412
        if frequency - int(frequency) == 0: frequency = int(frequency)
        else: frequency = None
    else:
        frequency = (chNo-1)*5 +2412
        if frequency - int(frequency) == 0: frequency = int(frequency)
        else: frequency = None
    return frequency


def main(pcapDir,directory_name,pcapFile,jsonFile,etc):

    #etc = {"endpointTag":endpointTag, "countRoams":countRoams, "roamSet":roamSet}
    endpointTag = etc["endpointTag"]
    countRoams = etc["countRoams"]
    roamSet = etc["roamSet"]
    upOrDown = etc["upOrDown"]
    
    print("At doRoamingAnalysis2 main with: \n{} \n{} \n{} \n{} \n{}".format(pcapDir,directory_name,pcapFile,jsonFile,etc))    
    
    startTime = time.time()
    if pcapDir[len(pcapDir)-1] != "/": pcapDir += "/"

    packetSizeMin = 200
    packetSizeMax = 2000
    
    roamTimes = []
    allFTtimes = []
    throughputs = {}    
            
    theName = "roamPlot"

    #Write a report
    myReport = {}
    myReport["Title"] = theName
    myReport["Report"] = []

    base_endpoint = "http://localhost:8080/pcapAPI"
    #Find all pcap files.
    thePcaps = []
    for x in os.listdir(pcapDir):
        if ".pcap" in x and ".pcapng" not in x: thePcaps.append(x)

    parts = pcapFile.split("/")
    thePcaps = [parts[len(parts)-1]]
    #print(thePcaps)
    
    if len(thePcaps)==0:
        item = {
            "elementType":"text",
            "text": "<p/><b> There are no PCAP files found in " + pcapDir + ". No roaming events analyzed, no roam times calculated.</b>"
        }
        myReport["Report"].append(item)
        print("No PCAP found")
        return myReport,None,None,None,None,None
            
    #Find the testlog file
    for x in os.listdir(pcapDir):
        if "testresultlog" in x:
            #print (x)
            logFile = pcapDir + x
    #print(logFile)
    #Get the roaming STA MAC address
    #logFile = pcapDir + logFile
    roamingMAC = None
    roamingMACs = []
    try:
        f = open(logFile)
        logs = json.load(f)    
        roamingMAC = formatMAC(logs["palMAC"])
        print("The MAC address of the roaming STA is {}".format(roamingMAC))
        item = {
            "elementType":"text",
            "text": "<p/><b> The MAC address of the roaming STA is " + roamingMAC + " </b>"
        }
        myReport["Report"].append(item)
        if "staQueries" in logs:
            theseQueries = logs["staQueries"][str(roamSet)]
            for endpoint in theseQueries:
                if endpointTag in endpoint:
                    thisQuery = theseQueries[endpoint]
                    try:
                        beforeLinks = thisQuery["staQuery"]["before"]["staInfo"]["links"]
                        afterLinks = thisQuery["staQuery"]["after"]["staInfo"]["links"]
                        for entry in beforeLinks:
                            if "freq" in beforeLinks[str(entry)] or True: roamingMACs.append(beforeLinks[str(entry)]["address"])
                        for entry in afterLinks:
                            if "freq" in afterLinks[str(entry)] or True: roamingMACs.append(afterLinks[str(entry)]["address"])
                        for i in range(0,len(roamingMACs)): roamingMACs[i] = formatMAC(roamingMACs[i])
                    except:
                        print("Either no beforeLinks, or afterLinks, for {}".format(endpoint))            
    except:
        item = {
            "elementType":"text",
            "text": "<p/><b> Not able to get the roaming STA MAC address from file " + logFile + ". No roaming events analyzed, no roam times calculated.</b>"
        }
        myReport["Report"].append(item)
        print("No roaming sta mac address file.")
        return myReport,None,None,None,None,None

    #Change the methodology to operate on a set of roaming MACs, which is what happens in the MLO case.  So for backwards compatibility, and non-MLO stuff, make sure that roamingMACs is filled.
    if len(roamingMACs)==0 and roamingMAC != None: roamingMACs = [roamingMAC]

    print("Using this set of roaming MACs: {}".format(roamingMACs))

    item = {
        "elementType":"text",
        "text": "Based on information from a STApal query, using iw dev, etc, the set of roaming MACs available is {}".format(roamingMACs)
    }
    myReport["Report"].append(item)
            
    #Get the possible BSSIDs that you would be interested in seeing.
    #meshFile = directory_name + "../meshinfo.json"
    meshFile = pcapDir + "meshinfo.json"
    print (meshFile)
    APlist = []
    try:
        f = open(meshFile)
        meshJson = json.load(f)
        meshText = json.dumps(meshJson)
        if "bssid" in meshJson["boxa_24g"]: APlist.append(meshJson["boxa_24g"]["bssid"])
        if "bssid" in meshJson["boxa_5g"]:  APlist.append(meshJson["boxa_5g"]["bssid"]) 
        if "bssid" in meshJson["boxa_6g"]: APlist.append(meshJson["boxa_6g"]["bssid"]) 
        if "bssid" in meshJson["boxb_24g"]: APlist.append(meshJson["boxb_24g"]["bssid"]) 
        if "bssid" in meshJson["boxb_5g"]: APlist.append(meshJson["boxb_5g"]["bssid"]) 
        if "bssid" in meshJson["boxb_6g"]: APlist.append(meshJson["boxb_6g"]["bssid"]) 
        item = {
            "elementType":"text",
            "text": "<p/><b> Here is the list of BSSIDs to focus on from a roaming point of view:  " + str(APlist) + "</b>"
        }
        myReport["Report"].append(item)
    except:
        print ("Bad meshinfo file")
        APlist = []
        item = {
            "elementType":"text",
            "text": "<p/><b> No BSSID information gathered from meshinfo.json.  So no BSSID information passed to getRoaming.</b>"
        }
        myReport["Report"].append(item)

    for i in range(0,len(APlist)): APlist[i] = formatMAC(APlist[i])
    print("This is the AP List {}".format(APlist))

    for file in thePcaps:
    
        item = {
            "elementType":"section",
            "headingType":"h1",
            "headingContent":"PCAP File Under Analysis: " + file,
            "text": pcapDir + file
        }
        myReport["Report"].append(item)
        
        #Get the total number of packets.
        api_endpoint = base_endpoint + "?action=getTotalPacketCount"
        api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
        print("The call is to:  " + api_endpoint)
        apiResponse = requests.get(url=api_endpoint)
        returnObject = json.loads(apiResponse.text)
        totalPackets = returnObject["result"]
        print("The total number of packets in this file is {}".format(totalPackets))

        #In case this is just setting of AP MACs, let's see what we find if we do this ourselves.
        api_endpoint = base_endpoint + "?action=getDataOfType" + "&filters=Beacon" + "&firstPacket=1&lastPacket=10"
        api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
        print("The call is to:  " + api_endpoint)
        apiResponse = requests.get(url=api_endpoint)
        returnObject = json.loads(apiResponse.text)
        foundAPs = []
        for obj in returnObject["result"]["perStreamStats"]: foundAPs.append(obj["transmitterAddress"])
        if len(APlist)==0:
            for bssid in foundAPs:
                if formatMAC(bssid) not in APlist: APlist.append(formatMAC(bssid))
            print("This is the AP List {}".format(APlist))                
        for AP in foundAPs:
            if formatMAC(AP) not in APlist:
                print("********************\n WARNING! I AM SEEING AN AP WITH MAC {} SENDING BEACONS, AND NOT IN YOUR AP LIST.  CONFIRM THAT LIST IS CORRECT! \n*************************".format(formatMAC(AP)))

        #Get samples throughout the file
        #stepSize = 50000
        stepSize = 19999
        sampleSize = 100
        tryTimes = 50
        firstPacket = 1
        lastPacket = sampleSize
        currentBSSID = None
        lastBSSID = None
        transitionRegions = []
        foundDirection = None
        directions = {"up":0,"down":0}
        while firstPacket < totalPackets:
            lastPacket = min(firstPacket+sampleSize,totalPackets)
            gotIt = False
            tried = 0
            while not gotIt and tried<tryTimes:
                api_endpoint = base_endpoint + "?action=getMainStream"
                api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
                api_endpoint += "&firstPacket=" + str(firstPacket) + "&lastPacket=" + str(lastPacket)
                #print("The call is to:  " + api_endpoint)
                print("Try from {} to {}".format(firstPacket,lastPacket))
                apiResponse = requests.get(url=api_endpoint)
                returnObject = json.loads(apiResponse.text)
                #print("{}".format(returnObject["result"]))
                theResult = returnObject["result"]["result"]
                #print(theResult["streams"])
                #Which one has my roamingMAC?
                atIndex = -1
                thisIndex = 0
                for stream in theResult["streams"]:
                    #if formatMAC(stream["ta"])==roamingMAC or formatMAC(stream["ra"])==roamingMAC:
                    if formatMAC(stream["ta"]) in roamingMACs or formatMAC(stream["ra"]) in roamingMACs:
                        atIndex = thisIndex
                        break
                    thisIndex += 1
                #print("My guy is at index " + str(atIndex))
                if atIndex>=0:
                    theStream = theResult["streams"][atIndex]
                    #if formatMAC(theStream["ta"]) == roamingMAC:
                    if formatMAC(theStream["ta"]) in roamingMACs:
                        currentBSSID = formatMAC(theStream["ra"])
                        foundDirection = "ul"
                        directions["up"] += 1
                    #if formatMAC(theStream["ra"]) == roamingMAC:
                    if formatMAC(theStream["ra"]) in roamingMACs:
                        currentBSSID = formatMAC(theStream["ta"])
                        foundDirection = "dl"
                        directions["down"] += 1
                    print("Between {} and {}, currently connected to {}".format(firstPacket,lastPacket,currentBSSID))
                    gotIt = True
                else:
                    tried += 1
                    lastPacket = min(firstPacket + 2**tried*sampleSize, totalPackets)

            if not gotIt: print("NOTE: I never found any roaming MAC in a stream for this part of the test.")
            if currentBSSID != lastBSSID:
                if currentBSSID and lastBSSID:
                    startPoint = max(1,firstPacket-stepSize)
                    print("BSSID has switched from {} to {} between {} and {}".format(lastBSSID,currentBSSID,startPoint,lastPacket))
                    transitionRegions.append({"start":startPoint, "end":lastPacket})
            firstPacket = firstPacket + stepSize
            lastBSSID = currentBSSID

        #Do a final region, right at the end.
        print("Try a region right at the end.")
        lastPacket  = totalPackets
        gotIt = False
        tried = 0
        while not gotIt and tried<tryTimes:
            #firstPacket = totalPackets - (2**tried)*sampleSize
            firstPacket = lastPacket - 100
            print("Try from {} to {}".format(firstPacket,lastPacket))
            api_endpoint = base_endpoint + "?action=getMainStream"
            api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
            api_endpoint += "&firstPacket=" + str(firstPacket) + "&lastPacket=" + str(lastPacket)
            apiResponse = requests.get(url=api_endpoint)
            returnObject = json.loads(apiResponse.text)
            theResult = returnObject["result"]["result"]
            #Which one has my roamingMACs?
            atIndex = -1
            thisIndex = 0
            for stream in theResult["streams"]:
                #if formatMAC(stream["ta"])==roamingMAC or formatMAC(stream["ra"])==roamingMAC:
                if formatMAC(stream["ta"]) in roamingMACs or formatMAC(stream["ra"]) in roamingMACs:
                    atIndex = thisIndex
                    break
                thisIndex += 1
            if atIndex>=0:
                theStream = theResult["streams"][atIndex]
                #if formatMAC(theStream["ta"]) == roamingMAC: currentBSSID = formatMAC(theStream["ra"])
                if formatMAC(theStream["ta"]) in roamingMACs: currentBSSID = formatMAC(theStream["ra"])
                #if formatMAC(theStream["ra"]) == roamingMAC: currentBSSID = formatMAC(theStream["ta"])
                if formatMAC(theStream["ra"]) in roamingMACs: currentBSSID = formatMAC(theStream["ta"])
                print("Between {} and {}, currently connected to {} vs {}".format(firstPacket,lastPacket,currentBSSID,lastBSSID))
                if currentBSSID != lastBSSID: gotIt = True
                else:
                    tried += 1
                    lastPacket = firstPacket
            else:
                tried += 1
                lastPacket = firstPacket
        if currentBSSID != lastBSSID:
            if currentBSSID and lastBSSID:
                startPoint = max(1,firstPacket-stepSize)
                print("BSSID has switched from {} to {} between {} and {}".format(lastBSSID,currentBSSID,startPoint,lastPacket))
                transitionRegions.append({"start":startPoint, "end":lastPacket})


        weirdMACformat = (roamingMAC.replace(":",".") + ".").lower()
        weirdMACformats = []
        for i in range(0,len(roamingMACs)):
            w = (roamingMACs[i].replace(":",".") + ".").lower()
            weirdMACformats.append(w) 
                
        print("The transition regions to check are: {}".format(transitionRegions))
        print("foundDirection: {}".format(foundDirection))
        print("directions: {}".format(directions))

        if len(transitionRegions)==0:
            item = {
                "elementType":"text",
                "text": "<p/><b> There are no transitions found in the data.  No roaming events analyzed, no roam times calculated.</b>"
            }
            myReport["Report"].append(item)

        #LMC Debug
        bumpUp = 10000  #Bump up the end of the transition region.  Why?  Because you may have found a transition, but not yet reached the data packets, etc.
        doingWholeFile = False
        if totalPackets < 20000:
            transitionRegions = [{"start":1, "end":-1}]
            bumpUp = 0
            doingWholeFile = True
            
        #See what the roaming analysis tells us
        if foundDirection != None:
            print("Based on packet analysis, I believe that the direction of traffic is {}".format(foundDirection))
            staDirection = foundDirection
        else:
            staDirection = "dl"

        #Finally, check to see if a useful direction was passed in.
        if not upOrDown: upOrDown = "none"
        if "d" in upOrDown.lower():
            staDirection = "dl"
            print("upOrDown was passed in as {}, so setting the STA direction to downlink.".format(upOrDown))
        elif "u" in upOrDown.lower():
            staDirection = "ul"
            print("upOrDown was passed in as {}, so setting the STA direction to uplink.".format(upOrDown))
            
        roamsReported = []

        pps = -1
        timeGap = -1
        SteadyStatePacketRate = -1
        LostPackets = -1
        theGap = -1

        allGood = True
        if len(transitionRegions) == 0: allGood = False

        EAPOLs = []
        
        for region in transitionRegions:
            success = False
            shifts = 0
            while not success:
                success = True
                rssiArray = []
                mobilityEvents = []
                firstPacketArrival = None
                roamTimes = []
                timeAverages  = []
                roamStory = []
                start = region["start"]
                end = region["end"] + bumpUp
                steps = []
                if(end-start+1>40000):
                    first = start
                    last = first+19999
                    while first < end:
                        steps.append({"first":first, "last":last})
                        first = last+1
                        last = first+19999
                else: steps.append({"first":start, "last":end})
                print("Using steps {}".format(steps))
                for step in steps:
                    api_endpoint = base_endpoint + "?action=getRoaming"
                    api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
                    api_endpoint += "&firstPacket=" + str(step["first"]) + "&lastPacket=" + str(step["last"])
                    #toMAC = weirdMACformat
                    toMAC = ""
                    for entry in weirdMACformats:toMAC += entry + ","
                    if toMAC[len(toMAC)-1] == ",": toMAC = toMAC[:-1]
                    if len(toMAC)>0: api_endpoint += "&to=" + toMAC
                    fromMAC = ""
                    if(len(APlist)>0):
                        fromMAC = ""
                        for ap in APlist: fromMAC += (ap.replace(":",".") + ".").lower() + ","                    
                    if len(fromMAC)>0:
                        if fromMAC[len(fromMAC)-1] == ",": fromMAC = fromMAC[:-1]
                        api_endpoint += "&from=" + fromMAC
                    api_endpoint += "&logic=or"
                    api_endpoint += "&direction=" + staDirection
                    print("The call is to:  " + api_endpoint)
                    apiResponse = requests.get(url=api_endpoint)
                    returnObject = json.loads(apiResponse.text)
                    #print("{}".format(returnObject["result"]))
                    theResult = returnObject["result"]
                    print("Here is the roam calculation message from getRoaming:  {}".format(theResult["roamMessage"]))
                    #if len(theResult["roamTimes"])>0: print("I found roam times here: {}".format(theResult["roamTimes"]))
                    #for key in theResult: print(key)
                    #Check to see if you have a bad edge effect.  If so, don't load this, but create shifted versions to try and center the roam.
                    thereAreAuths = False
                    for story in theResult["roamStory"]:
                        try:
                            if len(story["auths"])>0: thereAreAuths = True
                        except:
                            print("Problem with this story.  Likely that there are no AUTHs found.")
                            print(story)
                            thereAreAuths = False
                    #if len(theResult["roamStory"])>0 and len(theResult["roamTimes"])==0:
                    if thereAreAuths and len(theResult["roamTimes"])==0 and shifts<2 and not doingWholeFile:
                        print("\n\n  WARNING.  YOU SHOULD SHIFT AND TRY AGAIN \n\n")
                        success = False
                        region["start"] -= 10000
                        region["end"]   += 10000
                        shifts += 1
                        break
                    else:
                        rssiArray = rssiArray + theResult["rssiArray"]
                        mobilityEvents = mobilityEvents + theResult["mobilityEvents"]
                        if not firstPacketArrival: firstPacketArrival = theResult["firstPacketArrival"]
                        roamTimes = roamTimes + theResult["roamTimes"]
                        timeAverages = timeAverages + theResult["timeAverages"]
                        roamStory = roamStory + theResult["roamStory"]

            #print("Length of the rssi array is {}".format(len(rssiArray)))
            #for entry in rssiArray:
            #    print("{} {} {} {}".format(entry["transmitterAddress"],entry["receiverAddress"],entry["sourceAddress"],entry["destinationAddress"]))
            
            #print(roamStory)
            #print(json.dumps(mobilityEvents,indent=3))
            #print("\n\n ROAM TIMES ")
            #print(json.dumps(roamTimes,indent=2))

            if len(roamStory)==0 and len(roamTimes)==0:
                print("No roam stories or roam times, so continuing without looking anymore.")
                allGood = False
                continue

            #lmclmc
            FTtiming = []
            thePair = {}
            for event in mobilityEvents:
                #if event["packetType"] == "Authentication" and formatMAC(event["transmitterAddress"]) == roamingMAC:
                if event["packetType"] == "Authentication" and formatMAC(event["transmitterAddress"]) in roamingMACs:
                    thePair["auth"] = event
                elif event["packetType"] == "Reassociation response":
                        thePair["reassoc"] = event
                        if "auth" in thePair and "reassoc" in thePair:
                            FTtiming.append(thePair)
                            thePair = {}

            if len(FTtiming)==0:
                thePair = {}
                for event in mobilityEvents:
                    #if event["packetType"] == "Authentication" and formatMAC(event["receiverAddress"]) == roamingMAC:
                    if event["packetType"] == "Authentication" and formatMAC(event["receiverAddress"]) in roamingMACs:
                        thePair["auth"] = event
                    elif event["packetType"] == "Reassociation response":
                            thePair["reassoc"] = event
                            if "auth" in thePair and "reassoc" in thePair:
                                FTtiming.append(thePair)
                                thePair = {}
                

            #print("FT times: {}".format(FTtiming))

            merged = []
            packetsBeforeAndAfter = []
            for item in mobilityEvents: merged.append(item)
            for roam in roamTimes:
                merged.append(roam["before"])
                merged.append(roam["after"])
                if "packetNumber" in roam["before"]: packetsBeforeAndAfter.append(roam["before"]["packetNumber"])
                if "packetNumber" in roam["after"]:  packetsBeforeAndAfter.append(roam["after"]["packetNumber"])

            #Let's associate auth/assoc events with the various roam event timing.
            for roam in roamTimes:
                roam["assocs"] = []
                roam["auths"] = []
                roam["id"] = None
                if "packetNumber" in roam["before"]: packetBefore = roam["before"]["packetNumber"]
                else: continue
                if "packetNumber" in roam["after"]:  packetAfter  = roam["after"]["packetNumber"]
                else: continue
                for event in mobilityEvents:
                    if event["packetNumber"] < packetBefore: continue
                    if event["packetNumber"] > packetAfter: continue
                    if "auth" in event["packetType"].lower(): roam["auths"].append(event)
                    if "assoc" in event["packetType"].lower(): roam["assocs"].append(event)

            #Assign these roam times to a roam number.  What's going on?  Well, you can have more than one roam time calculation for any given roam event, since there
            #can be many different definitions of roam time.  But a roam will have the same set of associations and authentications.  So I want to be able to identify
            #which even this particular roam time calcuation is talking about.
            atIndex = 0
            for i in range(0,len(roamTimes)):
                if roamTimes[i]["id"] == None:
                    #Check to see if any previous roams have the same associations and authentications
                    useIndex = -1
                    for j in range(0,i):
                        #if str(roamTimes[i]["auths"])==str(roamTimes[j]["auths"]) and str(roamTimes[i]["assocs"])==str(roamTimes[j]["assocs"]):
                        if str(roamTimes[i]["assocs"])==str(roamTimes[j]["assocs"]):
                            useIndex = j
                            break
                    if useIndex >= 0:
                        roamTimes[i]["id"] = roamTimes[useIndex]["id"]
                    else:
                        roamTimes[i]["id"] = atIndex
                        atIndex += 1

            #OK.  We have assigned atIndex number of roams.  For each one, let's highlight if this is the "shortest" roam time calculation we have.
            for thisIndex in range(0,atIndex):
                shortestTime = None
                shortestIndex = None
                for r in range(0,len(roamTimes)):
                    if roamTimes[r]["type"] == "Cisco": continue   #For now, do not use the Cisco roaming calculation.
                    if roamTimes[r]["id"] != thisIndex: continue
                    if shortestTime == None:
                        shortestTime = roamTimes[r]["roamTime"]
                        shortestIndex = r
                    if roamTimes[r]["roamTime"] < shortestTime:
                        shortestTime = roamTimes[r]["roamTime"]
                        shortestIndex = r
                for r in range(0,len(roamTimes)):
                    if roamTimes[r]["id"] != thisIndex: continue
                    if r == shortestIndex: roamTimes[r]["shortestTime"] = True
                    else: roamTimes[r]["shortestTime"] = False


            #print("There are {} roam times".format(len(roamTimes)))
            #print("There are {} roam stories".format(len(roamStory)))
            #print("And here are the roam times now.")
            #print("\n\n ROAM TIMES ")
            #print(json.dumps(roamTimes,indent=2))

            #print(merged)
            combined = []
            while len(merged) > 0:
                theLowest = None
                for item in merged:
                    if theLowest == None: theLowest = item
                    if item["arrivalTimeSeconds"] < theLowest["arrivalTimeSeconds"]: theLowest = item
                combined.append(theLowest)
                merged.remove(theLowest)
            #print("Combined: {}".format(combined))

            skipThis = False
            howManyAlreadyReported = 0
            for roam in roamTimes:
                thisItem = {"before":roam["before"], "after":roam["after"]}
                if thisItem in roamsReported: howManyAlreadyReported += 1
            if howManyAlreadyReported == len(roamTimes) and howManyAlreadyReported>0: skipThis = True
            for roam in roamTimes:
                thisItem = {"before":roam["before"], "after":roam["after"]}
                roamsReported.append(thisItem)
            if skipThis:
                print("Skipping this roam. {}".format(thisItem))
                continue
            
            item = {
                "elementType":"section",
                "headingType":"h1",
                "headingContent":"Transition Region",
                "text": "From packet {} to packet {}".format(region["start"],region["end"])
            }
            myReport["Report"].append(item)            

            #Using this list of combined packets, let's indicate for each roam if there are any WNM packets that might be associated with it.
            startPacket = 0
            for roam in roamTimes:
                assocs = roam["assocs"]
                if(len(assocs)==0):
                    roam["wnms"] = []
                    continue
                lastPacket = assocs[len(assocs)-1]["packetNumber"]
                wnms = []
                for item in combined:
                    if item["packetNumber"]<startPacket or item["packetNumber"]>lastPacket: continue
                    try:
                        if "action" in item["packetType"].lower() and "wnm" in item["category"].lower() and "bss" in item["action"].lower(): wnms.append(item)
                    except: continue
                roam["wnms"] = []
                for wnm in wnms: roam["wnms"].append(wnm)
                startPacket = lastPacket + 1
                
            #print("\n\n ROAM TIMES ")
            #print(json.dumps(roamTimes,indent=2))
            for roam in roamTimes: print("Roam type {} has roam time of {} seconds.".format(roam["type"],roam["roamTime"]))

            #Get a list of data packets that use your STA and are in the proper direction
            rssiData = []
            bssidList = []
            for item in rssiArray:
                if staDirection == "dl":
                    #if item["receiverAddress"]==weirdMACformat or item["destinationAddress"]==weirdMACformat: rssiData.append(item)
                    if item["receiverAddress"] in weirdMACformats or item["destinationAddress"] in weirdMACformats: rssiData.append(item)
                    bssidUpdate(bssidList,item["transmitterAddress"])
                    #if item["sourceAddress"] != item["transmitterAddress"]: bssidUpdate(bssidList,item["sourceAddress"])
                elif staDirection == "ul":
                    #if item["transmitterAddress"]==weirdMACformat or item["sourceAddress"]==weirdMACformat: rssiData.append(item)
                    if item["transmitterAddress"] in weirdMACformats or item["sourceAddress"] in weirdMACformats: rssiData.append(item)
                    bssidUpdate(bssidList,item["receiverAddress"])
                    #if item["destinationAddress"] != item["receiverAddress"]: bssidUpdate(bssidList,item["destinationAddress"])

            #print(len(rssiData))
            #for item in rssiData:
            #    print("{} {} {} {}".format(item["transmitterAddress"],item["receiverAddress"],item["sourceAddress"],item["destinationAddress"]))

            #print(bssidList)
            trimBssidList = []
            for item in bssidList:
                if item["count"] > 2: trimBssidList.append(item["bssid"])
            #print(trimBssidList)
            trimRssiList = []
            for item in rssiData:
                if staDirection == "dl":
                    #if (item["receiverAddress"]==weirdMACformat or item["destinationAddress"]==weirdMACformat) and (item["transmitterAddress"] in trimBssidList or item["sourceAddress"] in trimBssidList):
                    if (item["receiverAddress"] in weirdMACformats or item["destinationAddress"] in weirdMACformats) and (item["transmitterAddress"] in trimBssidList or item["sourceAddress"] in trimBssidList):
                        trimRssiList.append(item)
                elif staDirection == "ul":
                    #if (item["transmitterAddress"]==weirdMACformat or item["sourceAddress"]==weirdMACformat)   and (item["receiverAddress"] in trimBssidList or item["destinationAddress"] in trimBssidList):
                    if (item["transmitterAddress"] in weirdMACformats or item["sourceAddress"] in weirdMACformats)   and (item["receiverAddress"] in trimBssidList or item["destinationAddress"] in trimBssidList):
                        trimRssiList.append(item)
            
            #print(len(trimRssiList))
            #for item in trimRssiList:
            #    print("{} {} {} {}".format(item["transmitterAddress"],item["receiverAddress"],item["sourceAddress"],item["destinationAddress"]))

            plotPerBssid = []
            for bssid in trimBssidList:
                thisPlot = []
                for item in trimRssiList:
                    thisTime = item["arrivalTimeSeconds"] - firstPacketArrival
                    if item["receiverAddress"]==bssid or item["destinationAddress"]==bssid or item["transmitterAddress"]==bssid or item["sourceAddress"]==bssid:
                        thisPlot.append({"x":thisTime, "y":item["RSSI"]})
                if len(thisPlot)>0: plotPerBssid.append({"bssid":bssid, "rssiPlot":thisPlot})
            '''
            for plot in plotPerBssid:
                print("For bssid {} the length of the plot is {}".format(plot["bssid"],len(plot["rssiPlot"])))
            '''
            
            #RSSI plot for the data packets.  Gives a sense of how the connection is changing around the roaming point.
            allData = []
            idx = 0
            for plot in plotPerBssid:                
                thisObject = {"label": "BSSID: " + plot["bssid"],
                              "color": colors[idx % len(colors) + 4],
                              "width": 1,
                              "radius": 0,
                              "data": thinArrayTo(plot["rssiPlot"],500),
                              "fill": -1,
                              "style": "solid"
                            }
                allData.append(thisObject)
                idx += 1

            #Probe packets
            probeData = []
            for event in mobilityEvents:
                if "probe" in event["packetType"].lower():
                    thisTime = event["arrivalTimeSeconds"] - firstPacketArrival
                    probeData.append({"x":thisTime, "y":event["RSSI"]})
            thisObject = {"label": "Probe Packets",
                          "color": colors[idx % len(colors) + 4],
                          "width": -1,
                          "radius": 3,
                          "data": probeData,
                          "fill": -1,
                          "style": "solid"
                          }
            allData.append(thisObject)
            idx += 1

            #Authentication packets
            authData = []
            for event in mobilityEvents:
                if "auth" in event["packetType"].lower():
                    thisTime = event["arrivalTimeSeconds"] - firstPacketArrival
                    authData.append({"x":thisTime, "y":event["RSSI"]})
            thisObject = {"label": "Authentication Packets",
                          "color": colors[idx % len(colors) + 4],
                          "width": -1,
                          "radius": 5,
                          "data": authData,
                          "fill": -1,
                          "style": "solid"
                          }
            allData.append(thisObject)
            idx += 1

            #Association packets
            assocData = []
            for event in mobilityEvents:
                if "assoc" in event["packetType"].lower():
                    thisTime = event["arrivalTimeSeconds"] - firstPacketArrival
                    assocData.append({"x":thisTime, "y":event["RSSI"]})
            thisObject = {"label": "Association Packets",
                          "color": colors[idx % len(colors) + 4],
                          "width": -1,
                          "radius": 8,
                          "data": assocData,
                          "fill": -1,
                          "style": "solid"
                          }
            allData.append(thisObject)
            idx += 1

            #WNM packets
            wnmData = []
            bssPackets = []
            for event in mobilityEvents:
                try: 
                    if "action" in event["packetType"].lower() and "wnm" in event["category"].lower() and "bss" in event["action"].lower(): 
                        thisTime = event["arrivalTimeSeconds"] - firstPacketArrival
                        wnmData.append({"x":thisTime, "y":event["RSSI"]})
                        bssPackets.append(event["packetNumber"])
                except:
                    continue
            thisObject = {"label": "WNM Packets",
                          "color": colors[idx % len(colors) + 4],
                          "width": -1,
                          "radius": 12,
                          "data": wnmData,
                          "fill": -1,
                          "style": "solid"
                          }
            allData.append(thisObject)
            idx += 1

            item = {
                "elementType":"plot",
                "type": "scatter",
                "title": "Roaming plot",
                "xaxis":{"string":"Time (sec)"},
                "yaxis":{"string":"RSSI (dBm)"},
                "showTable": False,
                "plotWidth":"800px",
                "data": allData 
            }
            myReport["Report"].append(item)

            #Roaming related packets
            cols = {
                "Packet Number":[],
                "Arrival Timestamp":[],
                "Arrival Time":[],
                "Tx":[],
                "Rx":[],
                "Type":[],
                "Category":[],
                "Action":[],
                "Frequency":[],
                "RSSI":[]
            }
            formatting = {
                "Packet Number":[],
                "Arrival Timestamp":[],
                "Arrival Time":[],
                "Tx":[],
                "Rx":[],
                "Type":[],
                "Category":[],
                "Action":[],
                "Frequency":[],
                "RSSI":[]
            }
            #for event in mobilityEvents:
            for event in combined:
                use = False
                if "probe" in event["packetType"].lower(): use=True
                if "auth" in event["packetType"].lower(): use=True
                if "assoc" in event["packetType"].lower(): use=True
                use=True   #Use everything for now.
                try: 
                    if "action" in event["packetType"].lower() and "ack" in event["category"].lower(): use=False
                except:
                    use = True
                if use:
                    cols["Packet Number"].append(event["packetNumber"])
                    cols["Arrival Timestamp"].append(event["arrivalTimeSeconds"])
                    cols["Arrival Time"].append(round(event["arrivalTimeSeconds"]-firstPacketArrival,3))
                    cols["Tx"].append(event["transmitterAddress"])
                    cols["Rx"].append(event["receiverAddress"])
                    cols["Type"].append(event["packetType"])
                    cols["Frequency"].append(event["channelFrequency"])
                    cols["RSSI"].append(event["RSSI"])
                    try: cols["Category"].append(event["category"])
                    except: cols["Category"].append("")
                    try: cols["Action"].append(event["action"])
                    except: cols["Action"].append("")
                    color="black"
                    backgroundColor="white"
                    if event["packetNumber"] in packetsBeforeAndAfter:
                        color="white"
                        backgroundColor="red"
                    if event["packetNumber"] in bssPackets or "reassociation" in event["packetType"].lower():
                        color="white"
                        backgroundColor="green"
                    for thing in formatting: formatting[thing].append({"color":color,"background-color":backgroundColor})
                    '''
                    if "data" in event["packetType"].lower():
                        for thing in formatting: formatting[thing].append({"color":"white","background-color":"red"})
                    else:
                        for thing in formatting: formatting[thing].append({"color":"black","background-color":"white"})
                    '''
            allData = []
            for key in cols:
                thisData = {"label":key,
                            "units":"",
                            "justification":"",
                            "data":cols[key],
                            "formatting":formatting[key]
                            }
                allData.append(thisData)
            item = {
                "elementType":"table",
                "type":"table",
                "title":"Roaming Related Packets",
                "data": allData
            }
            myReport["Report"].append(item)
                                        

            #The roam summary information, for this location
            item = {
                "elementType":"section",
                "headingType":"h2",
                "headingContent":"Roam summaries"
            }
            myReport["Report"].append(item)

            for roam in roamStory:
                item = {
                    "elementType":"text",
                    "text":roam["summary"] + "\n"
                }
                myReport["Report"].append(item)

            #The roam time calcuation, for this location
            item = {
                "elementType":"section",
                "headingType":"h2",
                "headingContent":"Roam times"
            }
            myReport["Report"].append(item)

            theText = ""
            for roam in roamTimes:
                theText = "Calculation type: {}".format(roam["type"])
                theText += "<br/>"
                bef = roam["before"]
                theText += "Before the roam, packet {} of type {} at time {}, Tx(src) -> Rx(dest) {}({}) -> {}({}) at RSSI {} dBm, {} MHz.".format(bef["packetNumber"],bef["packetType"],bef["arrivalTimeSeconds"],
                                                                                                                                           bef["transmitterAddress"], bef["sourceAddress"],
                                                                                                                                           bef["receiverAddress"],bef["destinationAddress"],
                                                                                                                                                   bef["RSSI"],bef["channelFrequency"])
                theText += "<br/>"
                aft = roam["after"]
                theText += "After the roam, packet {} of type {} at time {}, Tx(src) -> Rx(dest) {}({}) -> {}({}) at RSSI {} dBm., {} MHz".format(aft["packetNumber"],aft["packetType"],aft["arrivalTimeSeconds"],
                                                                                                                                          aft["transmitterAddress"],aft["sourceAddress"],
                                                                                                                                          aft["receiverAddress"],aft["destinationAddress"],
                                                                                                                                                  aft["RSSI"],aft["channelFrequency"])
                theText += "<br/>"
                theText += "Roam time calculation: {} seconds.".format(round(roam["roamTime"],3))
                theText += "<br/>"
                theText += "For roam index: {}.".format(roam["id"])
                theText += "<p/>"
                item = {
                    "elementType":"text",
                    "text":theText
                }
                myReport["Report"].append(item)

            #The fast transition time calcuations
            item = {
                "elementType":"section",
                "headingType":"h2",
                "headingContent":"Fast transition timings"
            }
            myReport["Report"].append(item)

            theText = ""
            for pair in FTtiming:
                auth = pair["auth"]
                reassoc = pair["reassoc"]
                theText += "Auth packet is packet {}, at time {}, Tx -> Rx {} -> {}".format(auth["packetNumber"],auth["arrivalTimeSeconds"],auth["transmitterAddress"],auth["receiverAddress"])
                theText += "<br/>"
                theText += "Reassociation packet is packet {}, at time {}, Tx -> Rx {} -> {}".format(reassoc["packetNumber"],
                                                                                                     reassoc["arrivalTimeSeconds"],reassoc["transmitterAddress"],reassoc["receiverAddress"])
                theText += "<br/>"
                thisTime = reassoc["arrivalTimeSeconds"] - auth["arrivalTimeSeconds"]
                thisTime *= 1000
                theText += "Fast Association time calculation: {} milliseconds.".format(round(thisTime,3))
                theText += "<p/>"
                allFTtimes.append(thisTime)
                
            item = {
                "elementType":"text",
                "text":theText
            }
            myReport["Report"].append(item)

            #ALL NEW
            
            #Make a combined plot of many things.  RSSI vs Time, colored to show BSSID transitions, with lines indicating association or reassociation events.
            theZip = jsonFile
            print("Use zip file {}".format(theZip))
            if theZip != None:
                #csv the zip.
                ea_root = "http://localhost:8080/"
                #ea_root = "http://www.octapi.tech/"
                with open(theZip, "rb") as f:
                    bytes = f.read()
                    encoded = base64.b64encode(bytes)
                    api_endpoint = ea_root + "zip2csv"
                    data = {'zip':encoded}
                    theResponse = requests.post(url=api_endpoint, data=data, timeout=120)
                    theJson = json.loads(theResponse.text)
                    csv = theJson["csv"]

                # Objectify the csv
                api_endpoint = ea_root + "objectify"
                data = {'csv':csv}
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)

                headers = theJson["headers"]
                dataSet = theJson["dataSet"]
                if "error" in theJson:
                    print("objectify: This data returned an error: {}".format(theJson["error"]))
                    continue

                #Get basic test results information
                api_endpoint = ea_root + "getStats"
                data = {'csv':csv,'filter':'counts'}
                try:
                   r = requests.post(url=api_endpoint, data=data, timeout=55)
                except requests.exceptions.RequestException as error:
                   print("Error: ", error)
                   continue
            
                y = json.loads(r.text)

                #print("DEBUG:\n{}".format(y))

                #Bit hard-coded right now, but find the "E" device which should be the roamer.
                peMap = y["filteredData"]["palEndpoints"]["map"]
                print("This is the map of the pal endpoints: {}".format(peMap))
                tpMap = y["filteredData"]["trafficPairs"]["map"]
                peId = None
                for key in peMap:
                    if endpointTag in peMap[key] and "sn" not in peMap[key]:
                       peId = key
                    '''
                    if "E" in peMap[key] and "sn" not in peMap[key]:
                       peId = key
                    if "philips" in peMap[key] and "sn" not in peMap[key]:
                       peId = key
                    if "Samsung" in peMap[key] and "sn" not in peMap[key]:
                       peId = key
                    '''
                if not peId:
                    print("Lookng for pal endpoint with ID {}, but did not find it.  The pal endpoint map it {}".format(endpointTag,peMap))
                    sys.exit(88)
                    
                peName = y["filteredData"]["palEndpoints"]["map"][peId]
                whichPE = str( int(peId)+1 )
                print("Pal endpoint name {}".format(peName))

                #Make an RSSI plot broken apart by BSSID.
                sections = []
                for index in range (0,len(dataSet)):
                    if "Pal Endpoint " + whichPE + " BSSID" not in dataSet[index]:
                        #print("At {}, Pal Endpoint {} BSSID not found.".format(index,whichPE))
                        continue
                    if ":" not in dataSet[index]["Pal Endpoint " + whichPE + " BSSID"]: continue
                    break  #The first index value at which you have a valid BSSID
                print("Start at index {}".format(index))
                print(len(dataSet))
                while index < len(dataSet)-1:
                    thisSection = []
                    thisSection.append(dataSet[index])
                    while dataSet[index+1]["Pal Endpoint " + whichPE + " BSSID"] == dataSet[index]["Pal Endpoint " + whichPE + " BSSID"]:
                        index += 1
                        thisSection.append(dataSet[index])
                        if index>len(dataSet)-2: break
                    sections.append(thisSection)
                    print("Appending a section of length {}".format(len(thisSection)))
                    index += 1
                    if index>len(dataSet)-1: break
                    while ":" not in dataSet[index]["Pal Endpoint " + whichPE + " BSSID"]:
                        index += 1
                        if index>len(dataSet)-1: break                        
                    print("Now at index {}".format(index))

                theData = []
                for section in sections: theData.append({"bssid":section[0]["Pal Endpoint " + whichPE + " BSSID"], "xyPlot":[]})
                for s in range(0,len(sections)):
                    secFirstPacket = None
                    secLastPacket = None
                    for i in range(0,len(sections[s])):
                        theData[s]["xyPlot"].append({"x":sections[s][i]["_palTimeStamp"], "y":sections[s][i]["Pal Endpoint "+whichPE+" Data RSSI [dBm] Mean"]})
                        if secFirstPacket == None: secFirstPacket = sections[s][i]
                        secLastPacket = sections[s][i]
                    theData[s]["firstPacket"] = secFirstPacket
                    theData[s]["lastPacket"] = secLastPacket
                for x in range(len(theData)-1,0,-1):
                    #print("Compare {} and {}".format(theData[x]["bssid"],theData[x-1]["bssid"]))
                    if theData[x]["bssid"] == theData[x-1]["bssid"]:
                        print("Merging and removing")
                        theData[x-1]["xyPlot"] = theData[x-1]["xyPlot"] + theData[x]["xyPlot"]
                        theData[x-1]["lastPacket"] = theData[x]["lastPacket"]
                        theData.remove(theData[x])
                
                allData = []
                idx = 10
                for data in theData:
                    idx += 1
                    thisData = {
	                "label": "BSSID: " + data["bssid"],
	                "color": colors[idx % len(colors)],
	                "width":1,
	                "radius":0,
	                "data": data["xyPlot"],
	                "fill": -1,
	                "style": "solid",
		        "yAxisID": "left"
	            }
                    allData.append(thisData)
                indexRoamTime = 0
                for item in roamTimes:
                    assocs = item["assocs"]
                    numAssocs = len(assocs)
                    if numAssocs > 0:
                        thisData = {
	                    "label": "Last association packet for roam time " + str(indexRoamTime),
	                    "color": "black",
	                    "width":3,
	                    "radius":0,
	                    "data": [{"x":assocs[numAssocs-1]["arrivalTimeSeconds"],"y":-90},{"x":assocs[numAssocs-1]["arrivalTimeSeconds"],"y":-30}],
	                    "fill": -1,
	                    "style": "solid",
		            "yAxisID": "left"
	                }
                        allData.append(thisData)
                    indexRoamTime += 1
                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "RSSI in BSSID sections",
                    "xaxis":{"string":"Time (sec)"},
                    "yaxis":{"string":"Data RSSI [dBm]"},
	            "yaxisNames":[
		        {"name":"left","location":"left","label":"Data RSSI [dBm]"},
		        #{"name":"right","location":"right","label":"Lost packets [%]"}
		        #{"name":"right","location":"right","label":"Lost packets"}
	            ],	    
                    "showTable": False,
                    "plotWidth":"800px",
                    "data": allData
                }
                myReport["Report"].append(item)

                #Final summary for these roaming events
                for event in roamTimes:
                    if not event["shortestTime"]: continue
                    if len(event["wnms"]) > 0 : roamInit = "Mesh Initiated"
                    else: roamInit = "STA Initiated"
                    roamType = "Association"
                    reassocFound = False
                    for item in event["assocs"]:
                        if "reassoc" in item["packetType"].lower(): reassocFound = True
                    if reassocFound: roamType = "Reassociation"
                    #if event["before"]["transmitterAddress"] == weirdMACformat: bssidBefore = event["before"]["receiverAddress"]
                    #if event["before"]["receiverAddress"] == weirdMACformat: bssidBefore = event["before"]["transmitterAddress"]
                    #if event["after"]["transmitterAddress"] == weirdMACformat: bssidAfter = event["after"]["receiverAddress"]
                    #if event["after"]["receiverAddress"] == weirdMACformat: bssidAfter = event["after"]["transmitterAddress"]
                    if event["before"]["transmitterAddress"] in weirdMACformats: bssidBefore = event["before"]["receiverAddress"]
                    if event["before"]["receiverAddress"] in weirdMACformats: bssidBefore = event["before"]["transmitterAddress"]
                    if event["after"]["transmitterAddress"] in weirdMACformats: bssidAfter = event["after"]["receiverAddress"]
                    if event["after"]["receiverAddress"] in weirdMACformats: bssidAfter = event["after"]["transmitterAddress"]
                    try:
                        tableData = [{"label":"File","units":"","justification":"","data":[file]},
                                     #{"label":"Time Before (sec)","units":"","justification":"","data":[theData[0]["lastPacket"]["Time [ms]"]]},
                                     {"label":"Timestamp Before","units":"","justification":"","data":[event["before"]["arrivalTimeSeconds"]]},
                                     {"label":"BSSID Before","units":"","justification":"","data":[bssidBefore]},
                                     {"label":"Frequency Before","units":"MHz","justification":"","data":[event["before"]["channelFrequency"]]},
                                     {"label":"Channel Before","units":"","justification":"","data":[FrequencyToChannelNumber(event["before"]["channelFrequency"])]},
                                     {"label":"RSSI Before","units":"dBm","justification":"","data":[event["before"]["RSSI"]]},
                                     #{"label":"Time After (sec)","units":"","justification":"","data":[theData[1]["firstPacket"]["Time [ms]"]]},
                                     {"label":"Timestamp After","units":"","justification":"","data":[event["before"]["arrivalTimeSeconds"]]},
                                     {"label":"BSSID After","units":"","justification":"","data":[bssidAfter]},
                                     {"label":"Frequency After","units":"MHz","justification":"","data":[event["after"]["channelFrequency"]]},
                                     {"label":"Channel After","units":"","justification":"","data":[FrequencyToChannelNumber(event["after"]["channelFrequency"])]},
                                     {"label":"RSSI After","units":"dBm","justification":"","data":[event["after"]["RSSI"]]},
                                     {"label":"Roam Event Type","units":"","justification":"","data":[roamType]},
                                     {"label":"Roam Event Initiated By","units":"","justification":"","data":[roamInit]},
                                     {"label":"Roam Time","units":"sec","justification":"","data":[round(event["roamTime"],3)]}
                                     ]                             
                        item = {
                            "elementType":"table",
                            "type":"table",
                            "title":"Roam Event Table",
                            "data": tableData
                        }
                        myReport["Report"].append(item)
                    except:
                        print("No before/after table created.")

                #Plot for throughput and BSSID
                throughputs = {}
                setOfPlots = {}
                for key in tpMap:
                    tpName = tpMap[key]
                    if endpointTag not in tpName: continue
                    throughputs[tpName] = {}
                    thisPlot = []                    
                    for thisData in dataSet:
                        xVal = thisData["Time [ms]"]
                        try: xVal = int(xVal)
                        except: continue
                        yName = tpName + " Throughput [Mbps]"
                        if yName not in thisData: continue
                        yVal = thisData[yName]
                        if yVal == "#N/A": continue
                        try: yVal = float(yVal)
                        except: continue
                        thisPlot.append({"x":xVal/1000, "y":yVal})
                    if len(thisPlot)>0: setOfPlots[tpName + " Throughput"] = thisPlot.copy()

                    idx = 0
                    for section in sections:
                        thisPlot = []
                        tputSum = 0
                        holdBssid = ""
                        for thisData in section:
                            xVal = thisData["Time [ms]"]
                            try: xVal = int(xVal)
                            except: continue
                            yName = tpName + " Throughput [Mbps]"
                            if yName not in thisData: continue
                            yVal = thisData[yName]
                            if yVal == "#N/A": continue
                            try: yVal = float(yVal)
                            except: continue
                            thisPlot.append({"x":xVal/1000, "y":yVal})
                            tputSum += yVal;
                            if idx == 0: tag = "pre-roam"
                            else: tag = "post-roam"
                            epName = "Pal Endpoint " + whichPE
                            zName = epName + " BSSID"
                            zVal = thisData[zName]
                            if ":" not in holdBssid and ":" in zVal: holdBssid = zVal
                        if len(thisPlot)>0: setOfPlots[tpName + " Throughput " + tag] = thisPlot.copy()
                        tputAve = None
                        if len(thisPlot)>0:
                            tputAve = tputSum/len(thisPlot)
                            throughputs[tpName][tag] = {"bssid":holdBssid, "ave":tputAve}
                        idx += 1
                    
                epName = "Pal Endpoint " + whichPE
                thisPlot = []
                bssids = {}
                bssidCount = 0
                for thisData in dataSet:
                    xVal = thisData["Time [ms]"]
                    try: xVal = int(xVal)
                    except: continue
                    yName = epName + " BSSID"
                    if yName not in thisData: continue
                    yVal = thisData[yName]
                    if yVal == "#N/A": continue
                    if ":" not in yVal: continue
                    if yVal in bssids: useVal = bssids[yVal]
                    else:
                        bssids[yVal] = bssidCount
                        bssidCount += 1
                        useVal = bssids[yVal]
                    thisPlot.append({"x":xVal/1000, "y":useVal})
                    if len(thisPlot)>0: setOfPlots[epName + " BSSID"] = thisPlot.copy()

                #print(setOfPlots)
                print(throughputs)

                allData = []
                idx = 0
                for plot in setOfPlots:
                    useID = "left"
                    if "BSSID" in plot: useID = "right"
                    thisData = {
	                "label": plot,
	                "color": colors[idx % len(colors) + 8],
	                "width":3,
	                "radius":0,
	                "data": setOfPlots[plot],
	                "fill": -1,
	                "style": "solid",
		        "yAxisID": useID
	            }
                    allData.append(thisData)
                    idx += 1

                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "Throughput aligned with BSSID. BSSID mapping is {}".format(bssids),
                    "xaxis":{"string":"Time (sec)"},
                    "yaxis":{"string":"Packets or Lost Packets"},
	            "yaxisNames":[
		        {"name":"left","location":"left","label":"Throughput (Mbps)"},
		        {"name":"right","location":"right","label":"BSSID","step":1,"grid":False}
	            ],	    
                    "showTable": False,
                    "plotWidth":"800px",
                    "data": allData
                }
                myReport["Report"].append(item)
                
                    
                #Plot for all packets and lost packets
                setOfPlots = {}
                for key in tpMap:
                    tpName = tpMap[key]
                    if endpointTag not in tpName: continue
                    thisPlot = []
                    for thisData in dataSet:
                        xVal = thisData["Time [ms]"]
                        try: xVal = int(xVal)
                        except: continue
                        yName = tpName + " Packets"                        
                        if yName not in thisData: continue
                        yVal = thisData[yName]
                        if yVal == "#N/A": continue
                        try: yVal = int(yVal)
                        except: continue
                        thisPlot.append({"x":xVal/1000, "y":yVal})
                    if len(thisPlot)>0: setOfPlots[tpName + " Packets"] = thisPlot.copy()
                    thisPlot = []
                    for thisData in dataSet:
                        xVal = thisData["Time [ms]"]
                        try: xVal = int(xVal)
                        except: continue
                        yName = tpName + " Lost Packets"                        
                        if yName not in thisData: continue
                        yVal = thisData[yName]
                        if yVal == "#N/A": continue
                        try: yVal = int(yVal)
                        except: continue
                        thisPlot.append({"x":xVal/1000, "y":yVal})
                    if len(thisPlot)>0: setOfPlots[tpName + " Lost Packets"] = thisPlot.copy()

                #print(setOfPlots)

                allData = []
                idx = 0
                for plot in setOfPlots:
                    useID = "left"
                    if "Lost" in plot: useID = "right"
                    thisData = {
	                "label": plot,
	                "color": colors[idx % len(colors) + 8],
	                "width":3,
	                "radius":0,
	                "data": setOfPlots[plot],
	                "fill": -1,
	                "style": "solid",
		        "yAxisID": useID
	            }
                    allData.append(thisData)
                    idx += 1

                item = {
                    "elementType":"plot",
                    "type": "scatter",
                    "title": "Packets and Lost Packets for each traffic pair",
                    "xaxis":{"string":"Time (sec)"},
                    "yaxis":{"string":"Packets or Lost Packets"},
	            "yaxisNames":[
		        {"name":"left","location":"left","label":"Packets"},
		        {"name":"right","location":"right","label":"Lost packets"}
	            ],	    
                    "showTable": False,
                    "plotWidth":"800px",
                    "data": allData
                }
                myReport["Report"].append(item)

                #Do analysis of the lost packet information.
                #For now, sort of hard code that you only care about the traffic pair that goes "2Server"
                #Analysis based on iPerf data
                LostPacketsPlot = []
                PacketsPlot = []
                for plot in setOfPlots:
                    if "Lost" in plot and "Server" in plot: LostPacketsPlot = setOfPlots[plot]
                    if "Lost" not in plot and "Server" in plot: PacketsPlot = setOfPlots[plot]
                #Count packets for all times when lost packets is zero

                #print("LostPacketsPlot {}".format(LostPacketsPlot))
                #print("PacketsPlot {}".format(PacketsPlot))
                SteadyStatePacketRate = -1
                LostPackets = -1
                theGap = -1
                if len(LostPacketsPlot)>0 and len(PacketsPlot)>0:

                    AllPackets = 0
                    ZeroTimes = 0
                    LostPackets = 0
                    for entry in PacketsPlot:
                        thisTime = entry["x"]
                        try: count = int(entry["y"])
                        except: continue
                        for item in LostPacketsPlot:
                            if item["x"]==thisTime and int(item["y"])==0:
                                AllPackets += count
                                ZeroTimes += 1
                    for entry in LostPacketsPlot:
                        thisTime = entry["x"]
                        try: count = int(entry["y"])
                        except: continue
                        LostPackets += count
                    print("There are {} seconds with zero packet loss".format(ZeroTimes))
                    SteadyStatePacketRate = AllPackets/ZeroTimes
                    print("The  steady state packet arrival rate is {} per second".format(SteadyStatePacketRate))                
                    print("There are a total of {} missing packets".format(LostPackets))
                    try: theGap = LostPackets/SteadyStatePacketRate*1000
                    except:
                        print("Cannot get a gap from iPerf because the LostPacket count is {}, and the steady-state packet rate is {}".format(LostPackets,SteadyStatePacketRate))
                        theGap = -1
                    print("The missing packet gap is {} msec".format(theGap))

            #DEBUG.  NOTE.  TEST SECTION.  Used to determine the lost packets due to the roam.
            #Analysis based on packet analysis
            # Where is the last packet before the roam?
            allGood = True
            if len(roamTimes) == 0: allGood = False
            roamPacket = None
            for roam in roamTimes:
                print("{}:, {}".format(roam["type"],roam["before"]))
                #if "All" in roam["type"] or "Both" in roam["type"] or "Cisco" in roam["type"]:  roamPacket = roam["before"]["packetNumber"]
                if "Both" in roam["type"]:
                    roamPacket = roam["before"]["packetNumber"]
                    break
                if "All" in roam["type"]:
                    roamPacket = roam["before"]["packetNumber"]
                    break
                if "UL" in roam["type"]:
                    roamPacket = roam["before"]["packetNumber"]
                    break
                if "TCP" in roam["type"]:
                    roamPacket = roam["before"]["packetNumber"]
                    break
                if "Cisco" in roam["type"]:
                    roamPacket = roam["before"]["packetNumber"]
                    break
                if "Block" in roam["type"]:
                    roamPacket = roam["before"]["packetNumber"]
                    break
                if "experiment" in roam["type"]:
                    roamPacket = roam["before"]["packetNumber"]
                    break
            if roamPacket == None: allGood = False
            print("The value of roamPacket is {}".format(roamPacket))

            print("allGood at #1 is {}".format(allGood))
            if allGood:
                lastPacket = roamPacket
                firstPacket = max(0,roamPacket-10000)
                #Get all of the QoS data packets before this one, for like 10K packets
                api_endpoint = base_endpoint + "?action=getPacketList"
                api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
                api_endpoint += "&firstPacket=" + str(firstPacket) + "&lastPacket=" + str(lastPacket)
                api_endpoint += "&filters=QoS Data,UDP"
                print("The call is to:  " + api_endpoint)
                apiResponse = requests.get(url=api_endpoint)
                returnObject = json.loads(apiResponse.text)
                packetList = returnObject["result"]
                print("Found {} packets. ".format(len(packetList)))
                #Filter this list to not include retries.
                newPacketList = []
                for packet in packetList:
                    if packet["retryFlag"]==0: newPacketList.append(packet)
                print("Filtered to {} packets. ".format(len(newPacketList)))
                #Assume you know roughly the size of the packets being sent.
                packetList = []
                for packet in newPacketList:
                    if packet["packetBytes"]>=packetSizeMin and packet["packetBytes"]<=packetSizeMax: packetList.append(packet)
                print("Filtered to {} packets. ".format(len(packetList)))
                if len(packetList) == 0:
                    #Try looking in the other direction.  After the roam.
                    firstPacket = roamPacket + 1
                    lastPacket = roamPacket + 10000
                    #Get all of the QoS data packets before this one, for like 10K packets
                    api_endpoint = base_endpoint + "?action=getPacketList"
                    api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
                    api_endpoint += "&firstPacket=" + str(firstPacket) + "&lastPacket=" + str(lastPacket)
                    api_endpoint += "&filters=QoS Data,UDP"
                    print("The call is to:  " + api_endpoint)
                    apiResponse = requests.get(url=api_endpoint)
                    returnObject = json.loads(apiResponse.text)
                    packetList = returnObject["result"]
                    print("Found {} packets. ".format(len(packetList)))
                    #Filter this list to not include retries.
                    newPacketList = []
                    for packet in packetList:
                        if packet["retryFlag"]==0: newPacketList.append(packet)
                    print("Filtered to {} packets. ".format(len(newPacketList)))
                    #Assume you know roughly the size of the packets being sent.
                    packetList = []
                    for packet in newPacketList:
                        if packet["packetBytes"]>=packetSizeMin and packet["packetBytes"]<=packetSizeMax: packetList.append(packet)
                    print("Filtered to {} packets. ".format(len(packetList)))
                    
                timeGaps = []
                for i in range(0,len(packetList)-1):
                    thisGap = packetList[i+1]["arrivalTimeSeconds"] - packetList[i]["arrivalTimeSeconds"]
                    timeGaps.append(thisGap*1000)

                sumGaps = 0
                for gap in timeGaps: sumGaps += gap
                aveGap = sumGaps/len(timeGaps)
                minGap = min(timeGaps)
                maxGap = max(timeGaps)
                api_endpoint = ea_root + "createHistogramFrom"
                data = {'data':timeGaps,'bins':100,'minVal':minGap,'maxVal':maxGap}
                try:
                    r = requests.post(url=api_endpoint, data=data, timeout=55)
                except requests.exceptions.RequestException as error:
                    print("Error: ", error)
                    sys.exit(78)

                theHist = json.loads(r.text)
                #print(theHist)

                item = {
                    "elementType":"section",
                    "headingType":"h2",
                    "headingContent":"Histogram of packet gap timing before the roam"
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
                    "title": "Data stream packet gap, Ave={:.2f} msec".format(aveGap),
                    "xaxis":{"string":"Gap (msec)"},
                    "yaxis":{"string":"Counts"},
                    "showTable": False,
                    "plotWidth":"800px",
                    "data": [{
                        "label": "Packet Gap(msec)",
                        "color": "blue",
                        "width": 1,
                        "data": data,
                        "fill": -1
                    }]
                }
                myReport["Report"].append(item)

                #Also, find the gap here for the handover.

                packetsToUse = 0
                lastPacket = roamPacket
                firstPacket = roamPacket
                while packetsToUse<2:
                    lastPacket += 1000
                    firstPacket -= 1000
                    firstPacket = max(0,firstPacket)
                    #Get all of the QoS data packets during this time
                    api_endpoint = base_endpoint + "?action=getPacketList"
                    api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
                    api_endpoint += "&firstPacket=" + str(firstPacket) + "&lastPacket=" + str(lastPacket)
                    api_endpoint += "&filters=QoS Data,UDP"
                    print("The call is to:  " + api_endpoint)
                    apiResponse = requests.get(url=api_endpoint)
                    returnObject = json.loads(apiResponse.text)
                    packetList = returnObject["result"]
                    print("At a1p found {} packets".format(len(packetList)))
                    #Filter this list to not include retries.
                    newPacketList = []
                    for packet in packetList:
                        if packet["retryFlag"]==0: newPacketList.append(packet)
                    print("At c3x Filtered to {} packets. ".format(len(newPacketList)))
                    packetsToUse = len(newPacketList)
                    
                #Assume you know roughly the size of the packets being sent.
                packetList = []
                for packet in newPacketList:
                    if packet["packetBytes"]>=packetSizeMin and packet["packetBytes"]<=packetSizeMax: packetList.append(packet)
                print("Filtered to {} packets. ".format(len(packetList)))

                #Make sure roaming MAC is in the packet.
                #This was commented out.  Going to put it back in.  If you comment it out again, please make a note as to WHY.
                newPacketList = []
                for packet in packetList:
                    #if formatMAC(packet["transmitterAddress"])==roamingMAC or formatMAC(packet["receiverAddress"])==roamingMAC: newPacketList.append(packet)
                    if formatMAC(packet["transmitterAddress"]) in roamingMACs or formatMAC(packet["receiverAddress"]) in roamingMACs: newPacketList.append(packet)
                packetList = []
                for packet in newPacketList: packetList.append(packet)
                print("After MAC check, Filtered to {} packets. ".format(len(packetList)))
                #print(packetList[0])
                #print(packetList[len(packetList)-1])

                #print(roamingMAC)
                #print(packetList[0])

                if len(packetList)>0:
                    '''
                    if formatMAC(packetList[0]["transmitterAddress"])==roamingMAC: initialMAC = packetList[0]["receiverAddress"]
                    if formatMAC(packetList[0]["receiverAddress"])==roamingMAC: initialMAC = packetList[0]["transmitterAddress"]
                    if formatMAC(packetList[len(packetList)-1]["transmitterAddress"])==roamingMAC: finalMAC = packetList[len(packetList)-1]["receiverAddress"]
                    if formatMAC(packetList[len(packetList)-1]["receiverAddress"])==roamingMAC: finalMAC = packetList[len(packetList)-1]["transmitterAddress"]
                    '''
                    if formatMAC(packetList[0]["transmitterAddress"]) in roamingMACs: initialMAC = packetList[0]["receiverAddress"]
                    if formatMAC(packetList[0]["receiverAddress"])    in roamingMACs: initialMAC = packetList[0]["transmitterAddress"]
                    if formatMAC(packetList[len(packetList)-1]["transmitterAddress"]) in roamingMACs: finalMAC = packetList[len(packetList)-1]["receiverAddress"]
                    if formatMAC(packetList[len(packetList)-1]["receiverAddress"])    in roamingMACs: finalMAC = packetList[len(packetList)-1]["transmitterAddress"]
                    # EDIT
                    print("Initial MAC: {}, final MAC: {}".format(initialMAC,finalMAC))

                    #Find the point at which this stream moves from initial mac to final mac
                    aSwitch = False
                    for i in range(0,len(packetList)-1):
                        aSwitch = False
                        '''
                        if packetList[i]["transmitterAddress"] == initialMAC and packetList[i+1]["transmitterAddress"] == finalMAC: aSwitch = True
                        if packetList[i]["transmitterAddress"] == initialMAC and packetList[i+1]["receiverAddress"] == finalMAC: aSwitch = True
                        if packetList[i]["receiverAddress"] == initialMAC and packetList[i+1]["receiverAddress"] == finalMAC: aSwitch = True
                        if packetList[i]["receiverAddress"] == initialMAC and packetList[i+1]["transmitterAddress"] == finalMAC: aSwitch = True
                        '''

                        firstHasInitial = packetList[i]["transmitterAddress"] == initialMAC or packetList[i]["receiverAddress"] == initialMAC
                        secondHasInitial = packetList[i+1]["transmitterAddress"] == initialMAC or packetList[i+1]["receiverAddress"] == initialMAC
                        if firstHasInitial and not secondHasInitial: aSwitch = True
                        if aSwitch: break
                    if aSwitch:
                        print("Switch happens between packets {} and {}".format(packetList[i]["packetNumber"],packetList[i+1]["packetNumber"]))
                        timeGap = packetList[i+1]["arrivalTimeSeconds"] - packetList[i]["arrivalTimeSeconds"]
                        timeGap *= 1000
                        print("The gap between data packets caused by the roam is {:.3f} msec.".format(timeGap))
                        
                        missingPackets = math.ceil(timeGap / aveGap)
                        pps = 1000/aveGap
                    else:
                        missingPackets = -1
                        timeGap = -1
                        pps = -1                    
                else:
                    missingPackets = -1
                    timeGap = -1
                    pps = -1                    
            else:
                missingPackets = -1
                aveGap = -1
                timeGap = -1
                pps = -1
                
            print("Based on the average packet timing of {:.2f} msec, and the gap length of {:.2f} msec, the roam is causing a loss of about {} packets.".format(aveGap,timeGap,missingPackets))
                                    
            #ALL NEW
                            
            #How much time was spent in EAPOL transitions in this data?
            print("allGood at #2 is {}".format(allGood))

            EAPOL_groups = []
            if allGood:
                firstPacket = roamPacket
                lastPacket = roamPacket
                ePackets = 0
                gap = 0
                while ePackets<1 and gap<20000:
                    firstPacket -= 1000
                    firstPacket = max(0,firstPacket)
                    lastPacket += 1000
                    api_endpoint = base_endpoint + "?action=getPacketList"
                    api_endpoint += "&fileName=" + file + "&pcapDir=" + pcapDir
                    api_endpoint += "&firstPacket=" + str(firstPacket)+ "&lastPacket=" + str(lastPacket)
                    api_endpoint += "&filters=EAPOL"
                    print("The call is to:  " + api_endpoint)
                    apiResponse = requests.get(url=api_endpoint)
                    returnObject = json.loads(apiResponse.text)
                    packetList = returnObject["result"]
                    ePackets = len(packetList)
                    gap = lastPacket-firstPacket

                #print(returnObject)
                for packet in packetList:
                    ra = packet["receiverAddress"]
                    ta = packet["transmitterAddress"]
                    #if formatMAC(ra) != roamingMAC and formatMAC(ta) != roamingMAC : continue
                    if not formatMAC(ra) in roamingMACs and not formatMAC(ta) in roamingMACs : continue
                    #print("For {} and {}...".format(ra,ta))
                    found = False
                    for group in EAPOL_groups:
                        if (group["end1"]==ra and group["end2"]==ta) or (group["end1"]==ta and group["end2"]==ra):
                            group["packets"].append({"pn":packet["packetNumber"],"time":packet["arrivalTimeSeconds"]})
                            found = True
                            #print("Using existing group.")
                            break
                    if not found:
                        EAPOL_groups.append({"end1":ra, "end2":ta, "packets":[{"pn":packet["packetNumber"],"time":packet["arrivalTimeSeconds"]}]})
                        #print("Creating a new group")
                    #print (EAPOL_groups)

                for group in EAPOL_groups:
                    timeSpentMsec = ( group["packets"][len(group["packets"])-1]["time"] - group["packets"][0]["time"] ) * 1000
                    group["timeSpentMsec"] = timeSpentMsec
            EAPOLs.append(EAPOL_groups)

        #Done looking at the various transition regions.

        #Find the EAPOL transition that is related to the roam of this particular STA
        EAPOL_groups = []
        for group in EAPOLs:
            print(group)
            for exchange in group:                
                if formatMAC(exchange["end1"]) in roamingMACs or formatMAC(exchange["end2"]) in roamingMACs:
                    EAPOL_groups = group
                    break
            
    #Done looking at the different pcap files.
    #Verify where scriptManager is running
    api_endpoint = "http://localhost:5678/exec?command=pwd"
    r = requests.get(url=api_endpoint)
    y = json.loads(r.text)
    scriptManagerLocation = y["stdout"]
    scriptManagerLocation = scriptManagerLocation.replace("\n","")
    storageLocation = scriptManagerLocation + "/" + "storage/"
    #print("storageLocation is {}".format(storageLocation))

    #Write the json file
    fileName = theName+".json"
    fullPath = storageLocation + fileName
    f = open(fullPath, "w")
    f.write(json.dumps(myReport,indent=4))
    f.close()
    
    #Generate the proper html for this report
    api_endpoint = "http://localhost:5678/jsonToHtmlReport"
    data = {'json':json.dumps(myReport,indent=4)}
    r = requests.post(url=api_endpoint,data=data)
    y = json.loads(r.text)
    html = y["html"]

    print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))
    
    fileName = theName+".html"
    fullPath = storageLocation + fileName
    #print("The full path for the saved file is {}".format(fullPath))
    #Write out this html file
    f = open(fullPath, "w")
    f.write(html)
    f.close()

    print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

    #Save the roam analysis file in the results directory.
    theSplit = pcapFile.split("_")
    theCount = "0"
    for item in theSplit:
        if ".pcap" in item: theCount = item.replace(".pcap","")
    #print("theCount used for the HTML plot is {}".format(theCount))
    if not theCount.isnumeric(): theCount = "0"
    theCount = str(countRoams)
    #print("theCount used for the HTML plot is {}".format(theCount))
    usePath = pcapDir + "roamPlot_" + theCount + ".html"
    print("the path used for the HTML plot is {}".format(usePath))
    f = open(usePath, "w")
    f.write(html)
    f.close()
    
    executionTime = (time.time() - startTime)
    print('Execution time in seconds: ' + str(executionTime))

    #print ("DEBUG:\n{}".format(roamTimes))

    appGap = {
        "pps": pps,
        "applicationGap": timeGap,
        "steadyStateRate": SteadyStatePacketRate,
        "lostPackets": LostPackets,
        "iperfGap": theGap
    }
    return myReport,roamTimes,allFTtimes,appGap,EAPOL_groups,throughputs

#For debugging only
'''
print("This is the debugging section of Roaming, doRoamingAnalysis2.  Comment it out if you see it and don't expect to.")
directory_name = "./"
pcapDir =  "/home/octoscope/Documents/automation/results/2025-12-12_12-30_DUTID/1_2025-12-12_12-30_Roaming/"
pcapFile = pcapDir + "2025-12-12_12-33_DUTID_Vx-x_roaming.pcap"
jsonFile = pcapDir + "2025-12-12_12-33_DUTID_Vx-x_roaming.zip"
endpointTag = "STA-51"
countRoams = 1
roamSet = 0
upOrDown = "dn"
etc = {"endpointTag":endpointTag, "countRoams":countRoams, "roamSet":roamSet, "upOrDown":upOrDown}

myReport,roamTimes,allFTtimes,appGap,EAPOL_groups,throughputs = main(pcapDir,directory_name,pcapFile,jsonFile,etc)
print ("RoamTimes: {}\n\n allFTtimes: {}\n\n appGap: {}\n\n  EAPOL_groups: {}\n\n  throughputs: {}\n\n".format(roamTimes,allFTtimes,appGap,EAPOL_groups,throughputs))
'''
