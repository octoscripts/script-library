'''
Test Description
================
Test to run traffic on several vSTAs and narrow in on the allowed number
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime
import copy
import re
import base64
from pathlib import Path

import pprint
pp = pprint.PrettyPrinter(indent=4)

import zipfile
from zipfile import ZipFile

#----------------------------------------------------
def selectNewRate(searchType, bitrate,lastGood,lastBad,lastStep):
    
    print("Current rate: {}".format(bitrate))
    if searchType == "highToLow":
        newRate = bitrate - 10

    elif searchType == "search":
        print("Last Good {} ... Last Bad {} ... Last Step {}".format(lastGood,lastBad,lastStep))
        if allPassed:
            lastGood = bitrate
        else:
            lastBad = bitrate

        if lastGood!=None and lastBad==None:
            lastStep = 2*lastGood
        elif lastGood==None and lastBad!=None:
            lastStep = int(lastBad/2)
            lastGood = 0
        elif lastGood!=None and lastBad!=None:
            lastStep = int((lastBad-lastGood)/2)
            
        print("Last Good {} ... Last Bad {} ... Last Step {}".format(lastGood,lastBad,lastStep))
        thisRate = lastGood + lastStep
        #print(">>>>>>>>>>>>>>>>>  Would use {}".format(thisRate))
        newRate = thisRate

    return (newRate,lastGood,lastBad,lastStep)

############### END SECTION: IMPORTS #########################

#Get the location of the results directory, as far as script-manager is concerned
response = requests.get("http://localhost:5678/getResultsDirectory")
theJson = response.json()
resultsDirectory = theJson["resultsDirectory"]
print("The results directory is {}.".format(resultsDirectory))

############### START SECTION: BUILD DICTIONARY #########################

# Find working directory
try:
    directory_name=sys.argv[1]
    print(">>> The directory name passed in is {}".format(directory_name),flush=True)
except:
    #directory_name = "./"
    directory_name = os.getcwd()
    print('>>> No directory_name provided, so using {}'.format(directory_name),flush=True)

# This line makes sure script can run from command line without SM
if directory_name[len(directory_name)-1] != "/": directory_name += "/"

sys.path.append(directory_name + '../')

import globalsfile	# MUST HAVE to be able to reference global variables stored in globalsfile.py
import sd2Utils		# MUST HAVE. Contains functions used in this script and other helpful functions

from stardust_socket_listen import StardustSocketListen # MUST HAVE if you are going to use any real time stats

# Reference params and base auto test dictionaries 
paramsDict = globalsfile.paramsDict

REST_TIMEOUT = paramsDict['rest_timeout']['val'] # Used by REST API calls
print('\n>>> REST_TIMEOUT: ', REST_TIMEOUT)

# This is to bring in alternate parameters set in Script Manager Arguments field
# This enables the same script to be run with a different set of test parameters stored in a json file
#-----  Look at the test parameter info, in arg[2]
try:
    test_param_alt_file=sys.argv[2]
    print(">>> The parameters file name passed in is {}.".format(test_param_alt_file))
except:
    print('>>> No parameters file name provided')
    test_param_alt_file = None

#Update paramsDict if there is a test_param_alt_file found
if test_param_alt_file:
	
	with open(directory_name+test_param_alt_file) as f:
	  test_params = json.load(f)
	f.close()
	
	if paramsDict['debug']['val']:
		print('>>> test_params: ', test_params)
	paramsDict.update(test_params)
	
	if 'apToTest' in paramsDict:
		apToTest = paramsDict['apToTest']['val']
	else:
		print('>>> No apToTest specified. Setting AP 1')
		apToTest = 1
	print("\n>>>paramsDict apToTest: ", apToTest)
else:
	print('>>> No apToTest specified. Setting AP 1')
	apToTest = 1

# Create the output folder
globalsfile.outputDirPath = resultsDirectory+paramsDict['topDirectory']+'/'+paramsDict['subDirectory']

if not os.path.exists(globalsfile.outputDirPath):
	os.makedirs(globalsfile.outputDirPath)
print('')
print('##############################################################')
print ('>>> Data will be stored in ', globalsfile.outputDirPath)
print('##############################################################')

testPrefix = paramsDict['testPrefix']['val']   	# for test record filenames
sd2Utils.getTimestampS()	# for test record filenames

# Create path to test result log file
globalsfile.resultsPath = os.path.join(globalsfile.outputDirPath,globalsfile.timeStamp+'_'+paramsDict['dut']['val']['dutId']+'_'+paramsDict['dut']['val']['dutRevision']+'_'+testPrefix+'_testresultlog.json')

# Bring in the testName. This is used by most REST API calls. 
# MAKE SURE there are no spaces in the test name used.
testName = paramsDict['testName']['val']

# Create the base autotest_dict. 
sd2Utils.updateParamsDict()	# Update paramsDict with instrument dicts
autotest_dict = sd2Utils.initializeAutotest()

############### END SECTION: BUILD DICTIONARY #########################

# ##################################################################################	
# ##################################################################################
#	                             Start of main test script
# ##################################################################################
# ##################################################################################

import createReport
#from kafka import KafkaProducer
kafkaBrokerFound = False
# initializing the Kafka producer
'''
print("Initializing the Kafka producer")
my_producer = KafkaProducer(  
    bootstrap_servers = ['localhost:9092'],
    api_version=(0,11,5),
    value_serializer = lambda x:json.dumps(x).encode('utf-8')  
)
'''


############################
# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

# Build list for config check
instList = []
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]

thisDrop = paramsDict['palToUse']['val']
for item in thisDrop:
    if item['selected']:
        palToUse = item['value']
        break

STAisPal = True
if "iperf" in palToUse: STAisPal = False
if "multiperf" in palToUse: STAisPal = False
debuggingWithL3C = False

customAlias = paramsDict["customAlias"]["val"]
customIP = paramsDict["customIP"]["val"]
customPort = paramsDict["customPort"]["val"]

if "iperf2" in palToUse:
    if customAlias == "": customAlias = "iperf2 Endpoint"
    if customPort == "": customPort = "5001"
    if customIP == "":
        print("You have selected an iperf2 endpoint.  You need to enter the IP address to use.")
        sys.exit(50)
if "iperf3" in palToUse:
    if customAlias == "": customAlias = "iperf3 Endpoint"
    if customPort == "": customPort = "5201"
    if customIP == "":
        print("You have selected an iperf3 endpoint.  You need to enter the IP address to use.")
        sys.exit(52)
if "multiperf" in palToUse:
        if customAlias == "":
                print("You have selected a multiperf endpoint.  You need to enter the name in the customAlias field in params_test so that I can find it.")
                sys.exit(54)
    
if STAisPal:
    debuggingWithL3C = False
    instList.append(palToUse)

testUses=paramsDict['testUses']['val']+instList+attenList
print(">>> testUses: ", testUses)

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)

print(">>> Pulling in data from the test parameters file.")

# Find where Expert Analysis is running for report generation
ea_root = sd2Utils.whereIsEA()
                  
banddrop = paramsDict["band"]["val"]
for item in banddrop:
    if item["selected"]:
        band = item["value"]
        break

if "24" in band:
    ssid     = paramsDict["dut"]["val"]["dutssid24"]
    security = paramsDict["dut"]["val"]["dutsecurity24"]
    password = paramsDict["dut"]["val"]["dutpass24"]
elif "5" in band:
    ssid     = paramsDict["dut"]["val"]["dutssid5"]
    security = paramsDict["dut"]["val"]["dutsecurity5"]
    password = paramsDict["dut"]["val"]["dutpass5"]
elif "6" in band:
    ssid     = paramsDict["dut"]["val"]["dutssid6"]
    security = paramsDict["dut"]["val"]["dutsecurity6"]
    password = paramsDict["dut"]["val"]["dutpass6"]
    
#VSTAs only make sense for a Pal6, so use Pal6 stuff
primaryChannel = paramsDict["primaryChannel"]["val"]
if primaryChannel < 20: radioValue = "RADIO_24"
elif primaryChannel >= 190: radioValue = "RADIO_6"
else: radioValue = "RADIO_5"
if STAisPal:
    if paramsDict[palToUse]["val"]["devType"] == "pal7":
        if radioValue == "RADIO_5": radioValue = "RADIO_5A"

bwdrop = paramsDict["bw"]["val"]
for item in bwdrop:
    if item["selected"]:
        bw = item["value"]
        break
if "320" in bw: bandwidth = "BANDWIDTH_320_ADAPT"
if "160" in bw: bandwidth = "BANDWIDTH_160_ADAPT"
if "80" in bw: bandwidth = "BANDWIDTH_80_ADAPT"
elif "40" in bw: bandwidth = "BANDWIDTH_40_ADAPT"
elif "20" in bw: bandwidth = "BANDWIDTH_20_FIXED"

ifacedrop = paramsDict["iface"]["val"]
for item in ifacedrop:
    if item["selected"]:
        iface = item["value"]
        break
iface = iface.lower()
if "be" in iface: interface = "INTERFACE_BE"
if "ax" in iface: interface = "INTERFACE_AX"
elif "ac" in iface: interface = "INTERFACE_AC"
elif "n" in iface: interface = "INTERFACE_N"

nssdrop = paramsDict["nss"]["val"]
for item in nssdrop:
    if item["selected"]:
        nss = item["value"]
        break
if "4" in nss: streams = 4
elif "3" in nss: streams = 3
elif "2" in nss: streams = 2
elif "1" in nss: streams = 1
elif "5" in nss: streams = 5
elif "6" in nss: streams = 6
elif "7" in nss: streams = 7
elif "8" in nss: streams = 8
else: streams = 4

#What is the PHY rate this can support?

api_endpoint = ea_root + "getMCS"
standard = iface
RSSI = "-20"
BW = bw.split(" ")[0]
streams = streams
api_endpoint += "?standard={}&RSSI={}&BW={}&streams={}".format(standard,RSSI,BW,streams)
print("The api endpoint is " + api_endpoint)
r = requests.get(url=api_endpoint)
y = eval(r.text)
status = y["status"]
MCS    = y["MCS"]
print("Returned with status {}".format(status))
print("MCS found is {}".format(MCS))
    
api_endpoint = ea_root + "getDRate"
if "n" in iface or "ac" in iface: GI = "400"
elif "ax" in iface or "be" in iface: GI = "800"
api_endpoint += "?standard={}&MCS={}&BW={}&streams={}&GI={}".format(standard,MCS,BW,streams,GI)
print("The api endpoint is " + api_endpoint)
r = requests.get(url=api_endpoint)
y = eval(r.text)
status = y["status"]
phyrate    = y["rate"]
print("Returned with status {}".format(status))
print("Rate found is {}".format(phyrate))

bitrate = paramsDict["trafficBW"]["val"]
bitrateUnit = ""
if "M" in bitrate.upper(): bitrateUnit = "M"
if "K" in bitrate.upper(): bitrateUnit = "K"
bitrate = re.sub("\D","",bitrate)
bitrate = int(bitrate)

#Use the PHY
bitrate = int(phyrate)
bitrateUnit = "M"

txAtten = paramsDict["txAtten"]["val"]
#Example VSTA configuration
aConfig = {
    "bandwidth": bandwidth,
    "interface_": interface,
    "streams": streams,
    "txAtten": txAtten,
    "certFilename": '',
    "password": password,
    "radiusIdentity": '',
    "radiusPassword": '',
    "security": security,
    "ssid": ssid    
    }

thresholdPercent  = paramsDict["thresholdPercent"]["val"]
tpairCountStart = paramsDict["tpairCountStart"]["val"]
tpairCountStop  = paramsDict["tpairCountStop"]["val"]
tpairCountStep  = paramsDict["tpairCountStep"]["val"]
bitrateThreshold  = paramsDict["bitrateThreshold"]["val"]
searchTypeDrop = paramsDict["searchType"]["val"]
for item in searchTypeDrop:
    if item["selected"]:
        searchType = item["value"]
        break

numberOfVstas = paramsDict["numberOfVstas"]["val"]
if not STAisPal and numberOfVstas>1:
    print ("The STA you are using is {}, and this is not a Pal.  But you are calling for {} vSTAs.  This is not consistent, so stopping here.".format(palToUse,numberOfVstas))
    sys.exit(29)
    
vstaConfig = []
for v in range(0,numberOfVstas): vstaConfig.append(aConfig)

#Since this is for VSTAs, find the traffic address and the set of addresses for the rest of them.
trafficList = []
if STAisPal:
    mgmtIp    = paramsDict[palToUse]["val"]["address"]
    trafficIp = paramsDict[palToUse]['val']['endpoints'][radioValue]['defaultIp']
    trafficParts = trafficIp.split(".")
    trafficRoot = trafficParts[0] + '.' + trafficParts[1] + "." + trafficParts[2] + "."
    trafficStart = int(trafficParts[3])
    for i in range(trafficStart,trafficStart+numberOfVstas): trafficList.append(trafficRoot + str(i))
    mgmtParts = mgmtIp.split(".")
    useAsGateway = trafficParts[0] + '.' + trafficParts[1] + '.' + mgmtParts[2] + '.' + mgmtParts[3]
else:
    trafficList.append(customIP)
        
#print(trafficList)

print("There are {} entries in your vstaConfig list.".format(len(vstaConfig)))

serverMIp = paramsDict["oBox_server"]["val"]["address"]
serverIp = paramsDict["oBox_server"]["val"]["publicip"]
    
print("{} >>> Pulling in data from the test parameters file. DONE. {}".format(cGreen,cNormal))
############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

 
############### START SECTION: BUILD THE TEST OBJECT #########################
print(">>> Creating the complete test object.")

tmpdict={'rvrMode':'RvR'}
sd2Utils.updateAutotest(tmpdict, pushConfig=True, timeoutOverride=REST_TIMEOUT*10)

print('')
print('##############################################################')
print("########## Setting up Attenuators START ")
print('##############################################################')
sd2Utils.isolateAllBoxes()

attensToUse = paramsDict["attensToUse"]["val"]

index = 0
for atten in attensToUse:
    doPush = False
    index += 1
    if index == len(attensToUse): doPush = True
    sd2Utils.setAtten(atten,paramsDict[atten]["val"]["devType"],paramsDict["quadAttenValue"]["val"],pushConfig=doPush)
    
print('')
print('##############################################################')
print("########## Setting up Attenuators DONE ")
print('##############################################################')


#See if you are using a Pal as the AP
if paramsDict['usePalAsAP']['val']:
    palToUseAsAP = paramsDict['palToUseAsAP']['val']
    thisDrop = paramsDict['palToUseAsAPBand']['val']
    for item in thisDrop:
        if item['selected']:
            band = item['value']
            break
    palToUseAsAPChannel = paramsDict['palToUseAsAPChannel']['val']
    primaryChannel = palToUseAsAPChannel
    ssid = paramsDict['palToUseAsAPSSID']['val']
    password = paramsDict['palToUseAsAPPassword']['val']
    thisDrop = paramsDict['palToUseAsAPSecurity']['val']
    for item in thisDrop:
        if item['selected']:
            security = item['value']
            break
    apDictOverride = {"ssid":ssid,"password":password,"security":security}
    apDictOverride["bandwidth"] = bandwidth
    apDictList = []
    apDictList = sd2Utils.setupAP(palToUseAsAP, band, apDictList, type = interface, channel=palToUseAsAPChannel, pushConfig=False, apDictOverride=apDictOverride)


print('')
print('##############################################################')
print("########## Setting up Traffic pairs START ")
print('##############################################################')

#Let's do this by setting the traffic pair up using this pal, but then overwriting the information that needs to be different for each VSTA.
#First, get the tpDict object by letting sd2Utils tell us what it should be for the first element.
#To accomodate bi-directional traffic, always create both an up and a down traffic pair, and then use the "active" setting to activate the right pair(s).
tpDictList = []
override = {}
if STAisPal:
        tpDictList = sd2Utils.setupTrafficPairs(palToUse, band, "up", tpDictList, tMode="tcp", pushConfig=False)
        tpDictList = sd2Utils.setupTrafficPairs(palToUse, band, "dn", tpDictList, tMode="tcp", pushConfig=True)
        
if debuggingWithL3C:
    tpDictList = sd2Utils.setupTrafficPairs("L3C-STApal", band, "up", tpDictList, tMode="tcp", tpDictOverride=override)

#Only do all of this in the Pal, vSTA case.
if STAisPal:
    #Store away the two pairs that are used as templates.
    tpItem = copy.deepcopy(tpDictList[0])  #This is the upstream pair.
    tpItemDown = copy.deepcopy(tpDictList[1])  #This is the downstream pair.
    
    #Now, zero out the tpDictList, and rewrite it for all of the VSTAs, using that information as the base.
    tpDictList = []
    sd2Utils.deleteFromDB(tpItemDown["alias"], "trafficPairs", pushConfig=False)
    sd2Utils.deleteFromDB(tpItem["alias"], "trafficPairs", pushConfig=True)
    
    #First, create the upstream pairs
    palAlias = tpItem["from"]["alias"]
    pairAlias = tpItem["alias"]
        
    setActive = False
    for i in range(0,len(trafficList)):
        tpDictOverride = copy.deepcopy(tpItem)
        thisAlias = palAlias + "_" + str(i)
        thisPairAlias = pairAlias + "_" + str(i)
        tpDictOverride["from"]["alias"] = thisAlias
        tpDictOverride["from"]["trafficAddress"] = trafficList[i]
        tpDictOverride["alias"] = thisPairAlias
        tpDictOverride["advanced"] = True
        tpDictOverride["active"] = setActive
        doPush = False
        if i == len(trafficList)-1: doPush= True
        tpDictList = sd2Utils.setupTrafficPairs(palToUse, band, "up", tpDictList, tMode="tcp", tpDictOverride=tpDictOverride,pushConfig=doPush)
        #print("\nCurrent tpDictList is:\n {}\n".format(json.dumps(tpDictList,indent=4)))

    #Next, do the downstream pairs.
    tpItem = tpItemDown
    palAlias = tpItem["to"]["alias"]
    pairAlias = tpItem["alias"]
    setActive = False
    for i in range(0,len(trafficList)):
        tpDictOverride = copy.deepcopy(tpItem)
        thisAlias = palAlias + "_" + str(i)
        thisPairAlias = pairAlias + "_" + str(i)
        tpDictOverride["to"]["alias"] = thisAlias
        tpDictOverride["to"]["trafficAddress"] = trafficList[i]
        tpDictOverride["alias"] = thisPairAlias
        tpDictOverride["advanced"] = True
        tpDictOverride["active"] = setActive
        doPush = False
        if i == len(trafficList)-1: doPush= True
        tpDictList = sd2Utils.setupTrafficPairs(palToUse, band, "dn", tpDictList, tMode="tcp", tpDictOverride=tpDictOverride,pushConfig=doPush)

print('')
print('##############################################################')
print("########## Setting up Traffic pairs DONE ")
print('##############################################################')
#print("\nCurrent tpDictList is:\n {}\n".format(json.dumps(tpDictList,indent=4)))

print('')
print('##############################################################')
print("########## Set up and associate STA ")
print('##############################################################')
overrideDict = {
    "bandwidth": bandwidth,
    "interface_": interface,
    "ssid": ssid,
    "password": password,
    "security":security,
    "vstaCount": len(trafficList),
    "vstaConfig": vstaConfig,
    "ipGateway": useAsGateway
}
staPalDictList = []
start0 = time.time()
if STAisPal:
    staPalDictList = sd2Utils.setupSTA(palToUse,band, staPalDictList, streams=streams, channel=primaryChannel,staDictOverride=overrideDict, pushConfig=True, timeoutOverride=REST_TIMEOUT*10)
    #print('>>> staPalDictList: ' )
    #pp.pprint(staPalDictList)
    palRadio = staPalDictList[0]['palRadio']
    palAlias = staPalDictList[0]['alias']

if debuggingWithL3C:
    staPalDictList = sd2Utils.setupSTA("L3C-STApal",band, staPalDictList, streams=streams, channel=primaryChannel,staDictOverride=overrideDict, pushConfig=True)    
			
print('')
print('##############################################################')
print("########## Setting up STAs DONE ")
print('##############################################################')

testsToRun = []

thePacketSizes = paramsDict["packetSizes"]["val"]
theMSSes       = paramsDict["MSSes"]["val"]
theDirections = []
doUplink = paramsDict["doUplink"]["val"]
if doUplink: theDirections.append("up")
doDownlink = paramsDict["doDownlink"]["val"]
if doDownlink: theDirections.append("dn")
doBidirectional = paramsDict["doBidirectional"]["val"]
if doBidirectional: theDirections.append("bi")
trafficModes = []
doTCP = paramsDict["doTCP"]["val"]
if doTCP: trafficModes.append("tcp")
doUDP = paramsDict["doUDP"]["val"]
if doUDP: trafficModes.append("udp")
for trafficMode in trafficModes:
    for direction in theDirections:
        for packetSize in thePacketSizes:
            for mss in theMSSes:        
                testsToRun.append({"index":len(testsToRun),"packetSize":packetSize,"mss":mss,"direction":direction,"trafficMode":trafficMode})

print("TEST LIST IS:")
for test in testsToRun: print(test)

allResults = {}

for thisTest in testsToRun:

    print("Running test {}, with configuration: {}".format(thisTest["index"],thisTest))
    allResults[thisTest["index"]] = {}    
    
    packetSize = thisTest["packetSize"]
    mss = thisTest["mss"]
    upOrDown = thisTest["direction"]
    direction = upOrDown
    trafficMode = thisTest["trafficMode"]
    
    if not STAisPal: #which means it's an iPerf client or multiperf client, so change the traffic pair to reflect that.
        serverSide = {
            "alias": "Server",
            "managementAddress": paramsDict['oBox_server']['val']['address'],
            "trafficAddress": paramsDict['oBox_server']['val']['defaultIp'],
            "devType": "server",
            "radio": "",
            "linkMonitor":False                
        }
        if "iperf" in palToUse:
            otherSide = {
                "alias": customAlias,
                "managementAddress": customIP,
                "trafficAddress": customIP,
                "devType": palToUse + "Endpoint",
                "radio": "",
                "iperfPort": customPort,
                "linkMonitor":False
            }
        elif "multiperf" in palToUse:
            otherSide = {
                "alias": paramsDict[customAlias]["val"]["dutName"],
                "managementAddress": paramsDict[customAlias]["val"]["managementAddr"],
                "trafficAddress": paramsDict[customAlias]["val"]["endpoints"]["ETHERNET"]["defaultIp"],
                "devType": paramsDict[customAlias]["val"]["devType"],
                "radio": "",
                "linkMonitor":False
            }            
        if upOrDown == "up":
            toSide = serverSide
            fromSide = otherSide
            pairalias = palToUse + "2Server"
        else:
            toSide = otherSide
            fromSide = serverSide
            pairalias = "Server2" + palToUse
        #if len(tpDictList)==1: pairalias = tpDictList[0]['alias']        #Can't do this, because it kills the STApal config.
        updateDict = {
            "to": toSide,
            "from": fromSide,
            "settlingTime": paramsDict['settlingTime']['val'],
            "active": True,
            "alias": pairalias,
            "bitrate": paramsDict['trafficBW']['val'],
            "trafficType": paramsDict['trafficType']['val'],
            "udp": trafficMode,
            "ipVersion": "ipv4",
            "ipStreams": paramsDict['parallel']['val'],
            "window": paramsDict['window']['val'],
            "length": packetSize
        }

        #tpDictList = []
        tpDictList.append(updateDict.copy())
        sd2Utils.updateAutotestInst(tpDictList, "trafficPairs", pushConfig=True)

    else:
        #Update the traffic pair array to have the right settings
        useAsRate = phyrate/tpairCountStart
        if upOrDown == "bi": useAsRate/=2
        bitrate = useAsRate
        print("\n\n*********\n With a PHY rate of {} Mbps and {} traffic pairs, starting the bit rate throughput setting at {} Mbps.".format(phyrate,tpairCountStart,bitrate))        
        for i in range(0,len(tpDictList)):
            tpDictList[i]["length"] = packetSize
            if trafficMode == "tcp": tpDictList[i]["setMss"] = mss
            tpDictList[i]["udp"] = trafficMode
            tpDictList[i]["bitrate"] = "{}{}".format(int(useAsRate),"M")            
            if trafficMode == "tcp": tpDictList[i]['bitrate'] = '0M'                
            sd2Utils.updateTrafficPair(tpDictList[i])
        
    if debuggingWithL3C:
        #print("The tpDictList is \n{}".format(tpDictList))
        updateDict = {"alias":tpDictList[0]['alias'] , "active": False}
        sd2Utils.updateTrafficPair(updateDict)


    ############### END SECTION: BUILD THE TEST OBJECT #########################

    ############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################
    if STAisPal:
        print('')
        print('##############################################################')
        print("########## Associating STAs ")
        print('##############################################################')
        associatedStatus = False
        assocWaitTime = 30
        #print('>>> band: ', band)
        if band: # Make sure not None
                if '6' in band:
                        assocWaitTime = 40	# 6 GHz takes longer to associate

        start1 = time.time()
        associatedStatus = sd2Utils.waitForAssociation(palToUse,palRadio,timeToWait=assocWaitTime,vstasRequired=len(trafficList))
        if not associatedStatus:
                print(">>> runRvR: Association not completed. Quitting.")
                sys.exit(1) # Set for SM

        end = time.time()
        print('')
        print('##############################################################')
        print("########## runRvR: Associating STAs DONE ")
        print('##############################################################')
        print('')
        print("From the time the Pal config was pushed to the determination that association was done took {} seconds.".format(round(end-start0,2)))
        print("From the time we started checking for association to the determination that association was done took {} seconds.".format(round(end-start1,2)))

    ############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

    ############### START SECTION: START THE TEST #########################

    print (">>> Starting test...")
    Timestamp = sd2Utils.getTimestamp()

    with open(directory_name + 'directories.json') as f:
        directories = json.load(f)
    newpath = directory_name + "../../results/" + directories["topDirectory"] + "/" + directories["subDirectory"]
    print("The path to the results is {}".format(newpath))

    if not os.path.exists(newpath):
        os.makedirs(newpath)

    if STAisPal: #Only if you are able to change vSTAs, so in the Pal case.
        tpairCount = tpairCountStart
        useTPairs = []
        for i in range(0,len(tpDictList)):
            setActive = False
            if upOrDown=="bi" or upOrDown=="up":
                if i<tpairCount: setActive = True
            if upOrDown=="bi" or upOrDown=="dn":
                if i >= len(trafficList) and i-len(trafficList) < tpairCount: setActive = True
            #useTPairs.append(setActive)
            if setActive: useTPairs.append(tpDictList[i]["alias"])
            tpDictList[i]["active"] = setActive
            print("Setting traffic pair {} to activity state {}".format(i,setActive))
            sd2Utils.updateTrafficPair(tpDictList[i])
        print("At top, useTPairs = {}".format(useTPairs))
        #sd2Utils.updateAutotestInst(tpDictList, "trafficPairs")
    else:
        tpairCount = 1
        if debuggingWithL3C: tpairCount = 2

    lastGood = None
    lastBad = None
    lastStep = bitrateThreshold
    if searchType == "search": lastStep += 1
    finalResults = []
    interimResults = {}

    keepGoing = True
    theCount = 1

    with open(directory_name + 'earlyExit.json') as f:
        earlyExitFile = json.load(f)
        earlyExit = earlyExitFile["earlyExit"]["val"]
        if earlyExit:
            print("Exiting early on user request")
            keepGoing = False

    while keepGoing:
        print("***** LOOP NUMBER {} *****".format(theCount))

        #Store in this output directory
        storeJson = {"FinalResults":finalResults, "InterimResults":interimResults}
        #print(json.dumps(storeJson,indent=4))
        outFile = globalsfile.outputDirPath + "/TestResults.json_{}bytes_{}mss_{}_{}_{}pairs".format(packetSize,mss,direction,trafficMode,tpairCount)
        f = open(outFile, "w")
        f.write(json.dumps(storeJson,indent=4))
        f.close()
        myReport = createReport.main(directory_name,globalsfile.outputDirPath,ea_root)   #Do this for interim status visibility
        if kafkaBrokerFound:
            try:
                print("Sending the JSON plot to the Kafka plotStream")
                my_producer.send('plotStream', value = myReport)
            except:
                print("The Kafka broker doesn't seem to be responding.")
                kafkaBrokerFound = False


        print("Pairs: {}, Traffic/Pair: {}".format(tpairCount,str(bitrate)+bitrateUnit))
        thisTotalRate = bitrate * tpairCount
        print("The total bitrate being tried is {} Mbps".format(thisTotalRate))

        thisKey = str(tpairCount)
        if "bi" in upOrDown.lower(): thisKey = str(2*tpairCount)
        if thisKey not in interimResults: interimResults[thisKey] = []

        ####Staring Autotest
        time.sleep(2)
        json_path = sd2Utils.runAutotest(unzip=False,saveCSV=False,saveTaJSON=False,triesLimit=50)

        #print("The test is now finished.")
        #-------------------------------------------------

        #Convert this JSON information into a usable CSV file
        fileName = json_path

        #Rename the JSON zip file.
        name = "Rate_{}M_{}B_{}mss_{}_{}pairs_{}".format(thisTotalRate,packetSize,mss,direction,tpairCount,trafficMode)
        newPath = globalsfile.outputDirPath + "/" + name + ".zip"
        command = "mv " + json_path + " " + newPath
        print("Renaming the json file using this command: {}".format(command))
        os.system(command)

        print("The path to the results is {}".format(newPath))
        fileName = newPath

        print("\n{} Calling createReport.extract() with file {}, Traffic Pairs to Use = {} and Bit Rate = {} {}\n".format(cGreen,fileName,useTPairs,bitrate,cNormal))
        theseResults = createReport.extract(directory_name,fileName,ea_root,useTPairs,bitrate)
        theseResults["LossThreshold"] = thresholdPercent
        theseResults["RateUnits"] = bitrateUnit
        interimResults[thisKey].append(theseResults)
        lostPacketArray = theseResults["LostPackets"]
        throughputArray = theseResults["Throughputs"]
        latencyArray = theseResults["Latencies"]
        AverageLatency = theseResults["AverageLatency"]

        notGood = True
        for value in throughputArray:
            if value != -1: notGood = False
        if notGood:
            print("Throughput array has returned all -1, meaning no throughputs found.  This is not good.")
            #Let's treat this as a case of 1--% packet loss.  I do see it happening when the rates are higher than can be supported.  See if the test can recover.
            for entry in lostPacketArray: entry = 100
            for entry in throughputArray: entry = 0
            #sys.exit(77)

        theSum = 0
        for lp in lostPacketArray: theSum += lp
        #print("Sum of lost percentages is {}".format(theSum))

        allPassed = True
        for lossPercentage in lostPacketArray:
            if lossPercentage > thresholdPercent:
                allPassed = False

        if trafficMode == "tcp":
            allPassed = True  #No binary search for TCP mode, since there is no lost packet information.  Just the forwarding rate based on 0M offered load (max load)
            lastStep = 0
                    
        with open(directory_name + 'earlyExit.json') as f:
            earlyExitFile = json.load(f)
            earlyExit = earlyExitFile["earlyExit"]["val"]
            if earlyExit:
                print("Exiting early on user request")
                keepGoing = False
                lastStep = 0

        #if theSum > 0:
        if (not allPassed or lastStep > bitrateThreshold) and (lastStep>1):
            print("Current loss for all pairs, threshold of {}%, {}".format(thresholdPercent,lostPacketArray))
            print("Current step size: {}".format(lastStep))

            oldBitrate = bitrate
            newBitrate = oldBitrate - 10
            testRate,lastGood,lastBad,lastStep = selectNewRate(searchType,bitrate,lastGood,lastBad,lastStep)
            #print("++++++++++++++++++++++++++++++ {}".format(testRate))
            newBitrate = testRate
            bitrate = newBitrate

            #Update the traffic pair array
            for i in range(0,len(tpDictList)):
                tpDictList[i]["bitrate"] = str(bitrate) + bitrateUnit
                sd2Utils.updateTrafficPair(tpDictList[i])
            #sd2Utils.updateAutotestInst(tpDictList, "trafficPairs")
            if debuggingWithL3C:
                updateDict = {"alias":tpDictList[0]['alias'] , "active": False}
                sd2Utils.updateTrafficPair(updateDict)

            print("The old bitrate is {}".format(str(oldBitrate) + bitrateUnit))
            print("The new bitrate is {}".format(str(newBitrate) + bitrateUnit))
            bitrate = newBitrate
            theCount += 1
        else:
            #This is the end of the loop for this number of traffic pairs.
            #Create the plot of this data.
            print("All pairs passed the loss threshold of {}%".format(thresholdPercent))
            print(lostPacketArray)
            print("Or, possibly, the step size has shrunk to less than the threshold of {} Mbps: {} Mbps".format(bitrateThreshold,lastStep))
            print("***** The bitrate required for {}% packet loss with {} traffic pairs is {}".format(thresholdPercent,tpairCount,str(bitrate)+bitrateUnit))
            theseResults = {
                "testConfig": thisTest,
                "tpairCount": tpairCount,
                "LossThreshold": thresholdPercent,
                "RatePerSTA": bitrate,
                "RateUnits":bitrateUnit,
                "LostPackets":lostPacketArray,
                "Throughputs":throughputArray,
                "Latencies":latencyArray,
                "AverageLatency":AverageLatency
                }
            finalResults.append(theseResults)
            allResults[thisTest["index"]][tpairCount] = theseResults

            #See if you want to run for more traffic pairs.
            tpairCount += tpairCountStep
            if tpairCount <= tpairCountStop:
                print("{}\n************************************{}".format(cRed,cNormal))
                print("{}New number of traffic pairs is {}{}".format(cGreen,tpairCount,cNormal))
                theCount = 1
                tpairCountLast = tpairCount - tpairCountStep
                modifiedBitRate = bitrate * tpairCountLast / tpairCount
                modifiedBitRate = int(modifiedBitRate) + 1
                bitrate = modifiedBitRate
                lastGood = None
                lastBad = None
                lastStep = bitrateThreshold
                if searchType == "search": lastStep += 1
                print("Starting a loop for {} traffic pairs with {} Mbps initially for each pair.".format(tpairCount,str(bitrate)+bitrateUnit))
                if STAisPal: #Only if you are able to change vSTAs, so in the Pal case.
                    useTPairs = []
                    useAsRate = phyrate/tpairCount
                    if upOrDown == "bi": useAsRate/=2
                    bitrate = useAsRate
                    print("\n\n*********\n With a PHY rate of {} Mbps and {} traffic pairs, starting the bit rate throughput setting at {} Mbps.".format(phyrate,tpairCount,bitrate))
                    for i in range(0,len(tpDictList)):
                        setActive = False
                        if upOrDown=="bi" or upOrDown=="up":
                            if i<tpairCount: setActive = True
                        if upOrDown=="bi" or upOrDown=="dn":
                            if i >= len(trafficList) and i-len(trafficList) < tpairCount: setActive = True
                        #useTPairs.append(setActive)
                        if setActive: useTPairs.append(tpDictList[i]["alias"])
                        tpDictList[i]["active"] = setActive
                        tpDictList[i]["bitrate"] = "{}{}".format(int(useAsRate),"M")
                        sd2Utils.updateTrafficPair(tpDictList[i])
                    #sd2Utils.updateAutotestInst(tpDictList, "trafficPairs")

            else:
                keepGoing = False

    storeJson = {"FinalResults":finalResults, "InterimResults":interimResults}
    #print(json.dumps(storeJson,indent=4))
    #outFile = globalsfile.outputDirPath + "/TestResults.json"
    f = open(outFile, "w")
    f.write(json.dumps(storeJson,indent=4))
    f.close()

    allFile = globalsfile.outputDirPath + "/AllResults.json"
    storeJson = {"allResults":allResults}
    f = open(allFile, "w")
    f.write(json.dumps(storeJson,indent=4))
    f.close()
                
print("Tests are complete.  Generating final plot file.")
#generateFinalPlot()

############### END SECTION: START THE TEST #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED #########################

#########Generating JSON reports

print('')
print('##############################################################')
print("########## Creating HTML report ")
print('##############################################################')	
myReport = createReport.main(directory_name,globalsfile.outputDirPath,ea_root)
if kafkaBrokerFound:
    try:
        print("Sending the JSON plot to the Kafka plotStream")
        my_producer.send('plotStream', value = myReport)
        time.sleep(5) #Give the consumer time to grab this.
    except:
        print("The Kafka broker doesn't seem to be responding.")
        kafkaBrokerFound = False
    
testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	

