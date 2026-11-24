'''
Test Description
================
Simple test to set up one traffic pair and one sniffer and run traffic while doing packet capture.
Illustrates all the basic functions of setting up results file folder and names, setting attenuators, settting up traffic pairs, setting up and associating STA and setting up, starting and stopping sniffing.
Assumes DUT in Box A. Sniffer and STA STApals in Box C.
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime
import base64
import re

import pprint
pp = pprint.PrettyPrinter(indent=4)

import zipfile
from zipfile import ZipFile 

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

#____________###############  DO NOT MODIFY ANYTHING ABOVE THIS LINE ###############_______________
# ##################################################################################	
# ##################################################################################
#	                             Start of main test script
# ##################################################################################
# ##################################################################################

from kafka import KafkaProducer
kafkaBrokerFound = True
# initializing the Kafka producer  
my_producer = KafkaProducer(  
    bootstrap_servers = ['localhost:9092'],
    api_version=(0,11,5),
    value_serializer = lambda x:json.dumps(x).encode('utf-8')  
)

from kafka import KafkaConsumer
my_consumer = KafkaConsumer('dataStream',
                         bootstrap_servers = ['localhost:9092'],
                         auto_offset_reset = 'earliest',
                         enable_auto_commit = True,  
                         api_version=(0,11,5),
                         value_deserializer = lambda x : json.loads(x.decode('utf-8'))
                         )

############################
# Set up some text coloring
cRed=   '\033[m'
cGreen= '\033[m'
cNormal='\033[m'

qaStart = int(paramsDict["quadAttenStart"]["val"])
qaStop  = int(paramsDict["quadAttenStop"]["val"])

sd2Utils.isolateAllBoxes()

##############################################################

haveCreateReport = False
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
    import createReport
    haveCreateReport = True
else:
    print("{} No createReport at {} {}".format(cRed,createReportFilePath,cNormal))
ea_root = sd2Utils.whereIsEA()

thisDrop = paramsDict["palToUseSTA"]["val"]
for item in thisDrop:
    if item["selected"]:
        palToUseSTA = item["value"]
        break

STAisPal = True
if "iperf" in palToUseSTA: STAisPal = False
debuggingWithL3C = False
if STAisPal: debuggingWithL3C = False

customAlias = paramsDict["customAlias"]["val"]
customIP = paramsDict["customIP"]["val"]
customPort = paramsDict["customPort"]["val"]

if "iperf2" in palToUseSTA:
    if customAlias == "": customAlias = "iperf2 Endpoint"
    if customPort == "": customPort = "5001"
    if customIP == "":
        print("You have selected an iperf2 endpoint.  You need to enter the IP address to use.")
        sys.exit(50)
if "iperf3" in palToUseSTA:
    if customAlias == "": customAlias = "iperf3 Endpoint"
    if customPort == "": customPort = "5201"
    if customIP == "":
        print("You have selected an iperf3 endpoint.  You need to enter the IP address to use.")
        sys.exit(52)

primaryChannel = paramsDict["primaryChannel"]["val"]
(theBand,palRadio) = sd2Utils.findBandFromChannel(primaryChannel)

bwdrop = paramsDict["bw"]["val"]
for item in bwdrop:
    if item["selected"]:
        bw = item["value"]
        break
if "320" in bw:   bandwidth = "BANDWIDTH_320_ADAPT"
elif "160" in bw: bandwidth = "BANDWIDTH_160_ADAPT"
elif "80" in bw:  bandwidth = "BANDWIDTH_80_ADAPT"
elif "40" in bw:  bandwidth = "BANDWIDTH_40_ADAPT"
elif "20" in bw:  bandwidth = "BANDWIDTH_20_FIXED"
else: bandwidth = "BANDWIDTH_20_FIXED"

ifacedrop = paramsDict["iface"]["val"]
for item in ifacedrop:
    if item["selected"]:
        iface = item["value"]
        break
iface = iface.lower()
if "be" in iface: interface = "INTERFACE_BE"
elif "ax" in iface: interface = "INTERFACE_AX"
elif "ac" in iface: interface = "INTERFACE_AC"
elif "n" in iface: interface = "INTERFACE_N"

nss = paramsDict["nss"]["val"]
if "4" in nss: streams = 4
elif "3" in nss: streams = 3
elif "2" in nss: streams = 2
elif "1" in nss: streams = 1
elif "5" in nss: streams = 5
elif "6" in nss: streams = 6
elif "7" in nss: streams = 7
elif "8" in nss: streams = 8
else: streams = 4

txAtten = 0

############# Traffic pair stuff
iperfMode = paramsDict["iperfMode"]["val"]
iperfMode = iperfMode.lower()
if "udp" in iperfMode: useUDP = True
else: useUDP = False

bitrate = paramsDict["trafficBW"]["val"]
bitrateUnit = ""
if "M" in bitrate.upper(): bitrateUnit = "M"
if "K" in bitrate.upper(): bitrateUnit = "K"
bitrate = re.sub("\D","",bitrate)
bitrate = int(bitrate)

length = paramsDict["length"]["val"]
parallel = paramsDict["parallel"]["val"]
trafficMode = paramsDict["iperfMode"]["val"]
trafficType = paramsDict["trafficType"]["val"]

window = paramsDict["window"]["val"]
windowUnit = ""
if "M" in window.upper(): windowUnit = "M"
if "K" in window.upper(): windowUnit = "K"
window = re.sub("\D","",window)
window = int(window)

upOrDowndrop = paramsDict["ulDl"]["val"]
for item in upOrDowndrop:
    if item["selected"]:
        upOrDown = item["value"]
        ulDl = upOrDown
        break

ssidval = 'dutssid'+theBand.replace('g','')
securityval = 'dutsecurity'+theBand.replace('g','')
passwordval = 'dutpass'+theBand.replace('g','')

# ssid, security and password are taken from params_system['dut']
ssid = paramsDict['dut']['val'][ssidval]
# valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
security = paramsDict['dut']['val'][securityval]
password = paramsDict['dut']['val'][passwordval]
print('>>> ssid: %s, security: %s, password: %s, channel: %s, band: %s' % (ssid, security, password, primaryChannel, theBand))

# Get rid of empty autotest_dict entries
testInfoDict = autotest_dict.copy()
popList = []
for k,v in testInfoDict.items():
	#print('v: ', v)
	if v==[]:
		popList.append(k)
print('>>> Removing blank items from testInfoDict: ', popList)
for item in popList:
	testInfoDict.pop(item)

print('\n>>> Adding test information to testresults.json')
resultDict = {"testInfo": testInfoDict}
resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp, "security":security, "ssid":ssid, "password":password,"band":theBand, "primaryChannel":primaryChannel, "bandwidth":bandwidth, "interface":interface, "streams":streams, "upOrDown": upOrDown })
resultDict['testInfo'].update({"scriptSuiteVersion":globalsfile.scriptSuiteVersion})
resultDict['testInfo'].update({"starDustVersion":globalsfile.starDustVersion})
resultDict['testInfo'].update({"palFWversions":globalsfile.palFWdict})
if test_param_alt_file:
	resultDict['testInfo'].update({"testParamAltFile":test_param_alt_file})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

time.sleep(5)

#Setting attenuation values for attenuators or MPEs:
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=True)

usePalAsAP = paramsDict["usePalAsAP"]["val"]
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
    resultDict['testInfo'].update({"security":security, "band":band, "primaryChannel":primaryChannel })
    resultDict['testInfo'].update({"palToUseAsAP":palToUseAsAP,"ssid":ssid,"password":password,"security":security})
    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)    
    apDictList = []
    apDictList = sd2Utils.setupAP(palToUseAsAP, band, apDictList, type = interface, channel=palToUseAsAPChannel, pushConfig=False, apDictOverride=apDictOverride)


#Setting up traffic pairs:
tpDictList = []
if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"
palAsAP = None
if paramsDict["usePalAsAP"]["val"]: palAsAP = paramsDict["palToUseAsAP"]["val"]
print('>>> palAsAP: ', palAsAP)
# NOTE! MUST first set up Traffic pair using a Pal type (pal6/pal7) or STA won't be created
override = {}

if STAisPal:
    tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList, palAsAP=palAsAP, pushConfig=False)
if debuggingWithL3C:
    tpDictList = sd2Utils.setupTrafficPairs("L3C-STApal", band, upOrDown, tpDictList, tMode=trafficMode, tpDictOverride=override)
    

if STAisPal:
    palArrayName = "pal6s"
    if paramsDict[palToUseSTA]["val"]["devType"] == "pal7": palArrayName = "pal7s"
if usePalAsAP:
    apArrayName = "pal6s"
    if paramsDict[palToUseAsAP]["val"]["devType"] == "pal7": apArrayName = "pal7s"


#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }
staoverride["bandwidth"]=bandwidth
bridgeEnable = False
if paramsDict["useMiniServers"]["val"]:
    if palToUseSTA in paramsDict["miniServersToUse"]["val"]: bridgeEnable = True
print(">>> The setting for the STATION bridge enablement is {}.".format(bridgeEnable))
staoverride["bridgeEnable"] = bridgeEnable

if STAisPal:
    staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=interface, channel=primaryChannel, pushConfig=False, staDictOverride=staoverride)
    targetRadio = staDictList[0]['palRadio']
    
if debuggingWithL3C:
    staDictList = sd2Utils.setupSTA("L3C-STApal",band, staDictList, streams=streams, channel=primaryChannel,staDictOverride=staoverride, pushConfig=True)    

sd2Utils.updateAutotest({}, pushConfig=True) # update config and set attens



if not STAisPal: #which means it's an iPerf client, so change the traffic pair to reflect that.
    serverSide = {
        "alias": "Server",
        "managementAddress": paramsDict['oBox_server']['val']['address'],
        "trafficAddress": paramsDict['oBox_server']['val']['defaultIp'],
        "devType": "server",
        "radio": "",
        "linkMonitor":False                
    }
    otherSide = {
        "alias": customAlias,
        "managementAddress": customIP,
        "trafficAddress": customIP,
        "devType": palToUseSTA + "Endpoint",
        "radio": "",
        "iperfPort": customPort,
        "linkMonitor":False
    }
    if upOrDown == "up":
        toSide = serverSide
        fromSide = otherSide
        pairalias = palToUseSTA + "2Server"
    else:
        toSide = otherSide
        fromSide = serverSide
        pairalias = "Server2" + palToUseSTA
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
        "length": paramsDict['length']['val'],
    }

    tpDictList.append(updateDict.copy())
    sd2Utils.updateAutotestInst(tpDictList, "trafficPairs", pushConfig=True)

if debuggingWithL3C:
    tpDictList[0]['active'] = False
    updateDict = {"alias":tpDictList[0]['alias'] , "active": False}
    sd2Utils.updateTrafficPair(updateDict)

if paramsDict["useMiniServers"]["val"]:
    #Update the traffic pair to use miniservers
    theTrafficPair = tpDictList[0]
    #linkMonitor = True
    #customEndpoints = {"to":"OB-MINISERVER-C","from":"OB-MINISERVER-A"}
    customEndpoints = paramsDict["miniServersToUse"]["val"]
    print('>>> customEndpoints: ', customEndpoints)
    sd2Utils.trafficPairUseCustomEndpoints(theTrafficPair,customEndpoints)

#Create the list of rates that you want to run through.
#rates = [-1,0,1,2,3,4,5,6,7,8,9,10,11,12,13]
fixedMcsValues = paramsDict["fixedMcsValues"]["val"]
McsList = fixedMcsValues.split(",")
for i in range(0,len(McsList)): McsList[i] = int(McsList[i])
print("\n {} Fixed MCS values to test are:  {} {}\n".format(cGreen,McsList,cNormal))

rates = McsList
rates.append(-1) #Do the dynamic MCS test as well.

jsons = []

#For each rate, reconfigure the Pal, check for association, run the test, and save the CSV.
for rate in rates:

    if STAisPal:
        print("\n {} Setting up the Pal STA to use rate {} {}\n".format(cRed,rate,cNormal))
        staDictList[0]["rate"] = rate
        sd2Utils.updateAutotestInst(staDictList,palArrayName,pushConfig=True)

    if usePalAsAP:
        print("\n {} Setting up the Pal AP to use rate {} {}\n".format(cRed,rate,cNormal))
        apDictList[0]["rate"] = rate
        sd2Utils.updateAutotestInst(apDictList,apArrayName,pushConfig=True)
    
    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    if STAisPal:
        print("Before starting the test, make sure that the STA, {}, is associated to the AP.".format(palToUseSTA))
        sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    json_path = sd2Utils.runAutotest(sleepTime=2,unzip=False,saveCSV=False,saveTaJSON=False)

    if rate < 0:
        name = "MCS_Adapt.json"
    else:
        if rate < 10: name = "MCS_0" + str(rate) + ".json"
        else: name = "MCS_" + str(rate) + ".json"
        
    #Rename the JSON zip file.
    newPath = globalsfile.outputDirPath + "/" + name + ".zip"
    command = "mv " + json_path + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)
    
    print("The path to the results is {}".format(newPath))
            
    jsons.append({"name":name, "file":newPath})        
    sd2Utils.logToJSON(globalsfile.resultsPath, {name:newPath})

    if haveCreateReport:
        reportJson = createReport.analyze(directory_name,globalsfile.outputDirPath,ea_root)
        if kafkaBrokerFound:
            try:
                my_producer.send('plotStream', value = reportJson)
            except:
                print("The Kafka broker doesn't seem to be responding.")
                kafkaBrokerFound = False

#Once we are done with this, let's begin by grabbing each of the files and pulling out the data

if haveCreateReport:
    reportJson = createReport.analyze(directory_name,globalsfile.outputDirPath,ea_root)
    if kafkaBrokerFound:
        try:
            my_producer.send('plotStream', value = reportJson)
        except:
            print("The Kafka broker doesn't seem to be responding.")
            kafkaBrokerFound = False

print("\n {} Test is complete! {}\n".format(cGreen,cNormal))
