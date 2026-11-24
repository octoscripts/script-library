'''
Test Description
================
Roam from box A to box B, and capture sniffing trace.  Test finds the attenuation value at which the connection to box A breaks, and the same for box B.  It then tries to create an attenuation ramping range to focus on the condition to cause a roam.  The roam is caused, the data is sniffed, the roam time is calculated.  Then the test allows the user to ask for this to be done over and over again.  Statistics are stored in the results log file.
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime

import zipfile
from zipfile import ZipFile

import pprint
pp = pprint.PrettyPrinter(indent=4)


############### END SECTION: IMPORTS #########################

# Get the location of the results directory, as far as script-manager is concerned
response = requests.get("http://localhost:5678/getResultsDirectory")
theJson = response.json()
resultsDirectory = theJson["resultsDirectory"]
print("The results directory is {}.".format(resultsDirectory))

############### START SECTION: BUILD DICTIONARY #########################

# Find working directory
try:
	directory_name = sys.argv[1]
	print(">>> The directory name passed in is {}".format(
		directory_name), flush=True)
except:
	# directory_name = "./"
	directory_name = os.getcwd()
	print('>>> No directory_name provided, so using {}'.format(
		directory_name), flush=True)

# This line makes sure script can run from command line without SM
if directory_name[len(directory_name)-1] != "/": directory_name += "/"

sys.path.append(directory_name + '../')

# MUST HAVE if you are going to use any real time stats
from stardust_socket_listen import StardustSocketListen
# MUST HAVE. Contains functions used in this script and other helpful functions
import sd2Utils
# MUST HAVE to be able to reference global variables stored in globalsfile.py
import globalsfile

# Reference params and base auto test dictionaries
paramsDict = globalsfile.paramsDict

REST_TIMEOUT = paramsDict['rest_timeout']['val']  # Used by REST API calls
print('\n>>> REST_TIMEOUT: ', REST_TIMEOUT)

# This is to bring in alternate parameters set in Script Manager Arguments field
# This enables the same script to be run with a different set of test parameters stored in a json file
# -----  Look at the test parameter info, in arg[2]
try:
	test_param_alt_file = sys.argv[2]
	print(">>> The parameters file name passed in is {}.".format(test_param_alt_file))
except:
	print('>>> No parameters file name provided')
	test_param_alt_file = None

# Update paramsDict if there is a test_param_alt_file found
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

import querySTA
allowEarlyRampStop = False

def cyclePalAndTryAgain(thisPal,stasAndConfigs,staDictList):
        #First, restart the Pal and wait for it to come back.
        restartList = [thisPal]
        sd2Utils.restartPals(restartList,180)

        #Next, find the previous configuration for this Pal, and push it back onto the Pal.
        thisConfig = stasAndConfigs[thisPal]
        theBand    = thisConfig["band"]
        theConfig  = thisConfig["config"]
        theChannel = theConfig["primaryChannel"]
        theStreams = theConfig["streams"]
        
        #Remove the entry from the staDictList
        #staDictList.remove(theConfig)
        index = -1
        for i in range(0,len(staDictList)):
                if str(staDictList[i]) == str(theConfig):
                        index = i
                        break;
        print("The index found is {}".format(index))
        if index >=0: del staDictList[index]

        #Push the configuration again, which will put this back into the staDictList.
        staDictList = sd2Utils.setupSTA(thisPal, theBand, staDictList, type="INTERFACE_AX", channel=theChannel, bssid='', streams=theStreams, staDictOverride=theConfig, pushConfig=True)

        return staDictList

#from kafka import KafkaProducer
kafkaBrokerFound = False
# initializing the Kafka producer
'''
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

############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

############### START SECTION: BUILD THE TEST OBJECT #########################

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

time.sleep(5)
sd2Utils.isolateAllBoxes()

outlierLow = float(paramsDict["outlierLow"]["val"])
if outlierLow < 0: outlierLow = 0
if outlierLow > 100: outlierLow = 100
outlierHigh = float(paramsDict["outlierHigh"]["val"])
if outlierHigh < 0: outlierHigh = 0
if outlierHigh > 100: outlierHigh = 100

stationCount = paramsDict["stationCount"]["val"]
if stationCount < 1:
        print("The station count has to be at least 1, so setting it to 1.")
        stationCount = 1

palToUseSTAdrop = paramsDict["palToUseSTA"]["val"]
for item in palToUseSTAdrop:
    if item["selected"]:
        palToUseSTA = item["value"]
        break

palsToUseSTA = paramsDict["palsToUseSTA"]["val"]
if len(palsToUseSTA) == 0: palsToUseSTA = [palToUseSTA]
else: palToUseSTA = palsToUseSTA[0]["name"]

assigned_STA_MACs = paramsDict["assigned_STA_MACs"]["val"]

'''
if stationCount == 1:
        palsToUseSTA = [{"name":palToUseSTA,"interface":"INTERFACE_AX"}]
        assigned_STA_MACs = [{"MAC":paramsDict["assigned_STA_MAC"]["val"], "tag":paramsDict["endpointTag"]["val"]}]
elif stationCount >1:
        longestList = max(len(palsToUseSTA),len(assigned_STA_MACs))
        if longestList < stationCount:
                print("You only have entered enough information to handle {} stations, so setting the station count to {}".format(longestList,longestList))
                stationCount = longestList
        while len(palsToUseSTA)>stationCount: popped = palsToUseSTA.pop()
        while len(assigned_STA_MACs)>stationCount: popped = assigned_STA_MACs.pop()
'''
longestList = max(len(palsToUseSTA),len(assigned_STA_MACs))
if longestList < stationCount:
        print("You only have entered enough information to handle {} stations, so setting the station count to {}".format(longestList,longestList))
        stationCount = longestList
while len(palsToUseSTA)>stationCount: popped = palsToUseSTA.pop()
while len(assigned_STA_MACs)>stationCount: popped = assigned_STA_MACs.pop()
print("\n\n")
print("The number of stations to use in this test is : {}".format(stationCount))
print("The list of station names is: {}".format(palsToUseSTA))
print("The list of MACs and tags is: {}".format(assigned_STA_MACs))
print("\n\n")
time.sleep(4)

customAlias = paramsDict["customAlias"]["val"]
customIP    = paramsDict["customIP"]["val"]
customPort  = paramsDict["customPort"]["val"]
if palToUseSTA == "iperf2":
        if customAlias == "": customAlias = "iperf2 Endpoint"
        if customPort == "": customPort = "5001"
        if customIP == "":
                print("You have selected an iperf2 endpoint.  You need to enter the IP address to use.")
                sys.exit(50)
if palToUseSTA == "iperf3":
        if customAlias == "": customAlias = "iperf3 Endpoint"
        if customPort == "": customPort = "5201"
        if customIP == "":
                print("You have selected an iperf3 endpoint.  You need to enter the IP address to use.")
                sys.exit(52)
if palToUseSTA == "multiperf":
        if customAlias == "":
                print("You have selected a multiperf endpoint.  You need to enter the name in the customAlias field in params_test so that I can find it.")
                sys.exit(54)

isRealSta = False
if "Android" in palToUseSTA:
        attenForBoxA = "QG-12"
        attenForBoxB = "QA-H"
        attenForSniffer = "QJ-12"
        isRealSta = True
elif "iperf" in palToUseSTA:   ##  NOTE!!!!! Most of the time, the values here should be pretty much the same as for the Android case.  
        attenForBoxA = "QG-12"
        attenForBoxB = "QA-H"
        #attenForBoxA = "QJ-34"  #If iperf client is STApal
        #attenForBoxB = "QE-12"  #If iperf client is STApal
        attenForSniffer = "QJ-12"
        isRealSta = True
elif "multiper" in palToUseSTA:   ##  NOTE!!!!! Most of the time, the values here should be pretty much the same as for the Android case.  
        attenForBoxA = "QG-12"
        attenForBoxB = "QA-H"
        attenForSniffer = "QJ-12"
        isRealSta = True
else:
        attenForBoxA = "QA-N34"
        attenForBoxB = "QA-P34"
        attensForSniffers = ["QA-N12","QA-P12"]
        for atten in attensForSniffers: sd2Utils.setAtten(atten,"virtualAtten",0)

#Setting attenuation values for attenuators or MPEs:
#sd2Utils.setAtten('QA-G',"virtualAtten",35) #Backhaul
backhaulAttenValue = paramsDict['backhaulAttenValue']['val']
sd2Utils.setAtten('QA-G',"virtualAtten",backhaulAttenValue) #Backhaul
'''
sd2Utils.setVatten(attenForBoxA,0,attenValueStop=0)
if "12" in attenForBoxB or "34" in attenForBoxB: sd2Utils.setVatten(attenForBoxB,0,attenValueStop=0)
else: sd2Utils.setAtten(attenForBoxB,"quadAtten",0,attenValueStop=0)
if isRealSta: sd2Utils.setVatten(attenForSniffer,0,attenValueStop=0)
#sd2Utils.setAtten('QA-F',"quadAtten",20) #Backhaul
#sd2Utils.setAtten('QA-D',"quadAtten",20) #Backhaul
'''

channelToUse = paramsDict["channelToUseSTA"]["val"]
if channelToUse < 20: band = "24g"
elif channelToUse > 191: band = "6g"
else: band = "5g"
channelToUseSniffer1 = paramsDict["channelToUseSniffer1"]["val"]
if channelToUseSniffer1 < 20: band1 = "24g"
elif channelToUseSniffer1 > 191: band1 = "6g"
else: band1 = "5g"
channelToUseSniffer2 = paramsDict["channelToUseSniffer2"]["val"]
if channelToUseSniffer2 < 20: band2 = "24g"
elif channelToUseSniffer2 > 191: band2 = "6g"
else: band2 = "5g"
channelToUseSniffer3 = paramsDict["channelToUseSniffer3"]["val"]
if channelToUseSniffer3 < 20: band3 = "24g"
elif channelToUseSniffer3 > 191: band3 = "6g"
else: band3 = "5g"

#Grab ssid/password/security information from system file
# ssid, security and password are taken from params_system['dut']
ssidval = 'dutssid'+band.replace('g','')
ssid = paramsDict['dut']['val'][ssidval]
# valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
securityval = 'dutsecurity'+band.replace('g','')
security = paramsDict['dut']['val'][securityval]
passwordval = 'dutpass'+band.replace('g','')
password = paramsDict['dut']['val'][passwordval]
print('\nSecurity information from the system paramters file:: ssid: %s, security: %s, password: %s, channel: %s, band: %s' % (ssid, security, password, channelToUse, band))

palsAsAPs = paramsDict["palsAsAPs"]["val"]
if palsAsAPs:

        palAsAPssid = paramsDict["palAsAPssid"]["val"]
        palAsAPpassword = paramsDict["palAsAPpassword"]["val"]
        thisDrop = paramsDict["palAsAPsecurity"]["val"]
        for item in thisDrop:
                if item["selected"]:
                        palAsAPsecurity = item["value"]
                        break
        apDictOverride = {"ssid":palAsAPssid}
        apDictOverride["security"]=palAsAPsecurity
        apDictOverride["password"]=palAsAPpassword
        if isRealSta: apDictOverride["rate"]=0
        #apDictOverride["vEnable"]=True
        #apDictOverride["kEnable"]=True
        apDictOverride["rFastTransitionEnable"]=True   #Pals can do 11r, so best to leave this one enabled.

        #Setting up AP configurations:
        apDictList = []
        apDictList = sd2Utils.setupAP("Pal-6A", band, apDictList, type = "INTERFACE_AX", channel=channelToUse, streams= 4, apBridge= True, pushConfig=False, apDictOverride=apDictOverride)
        apDictList = sd2Utils.setupAP("Pal-6B", band, apDictList, type = "INTERFACE_AX", channel=channelToUse, streams= 4, apBridge= True, pushConfig=False, apDictOverride=apDictOverride)
        
#Setting up traffic pairs.
thisDrop = paramsDict["tGenerator"]["val"]
for item in thisDrop:
    if item["selected"]:
        tGenerator = item["value"]
        break
thisDrop = paramsDict["tProtocol"]["val"]
for item in thisDrop:
    if item["selected"]:
        tProtocol = item["value"]
        break
upOrDownDrop = paramsDict["upOrDown"]["val"]
for item in upOrDownDrop:
    if item["selected"]:
        upOrDown = item["value"]
        break
tParallel = paramsDict["parallel"]["val"]
tWindow = paramsDict["window"]["val"]
tLength = paramsDict["length"]["val"]
tRate = paramsDict["tRate"]["val"]
override = {}
override["advanced"] = paramsDict["showAdvanced"]["val"]
override["dscp"] = paramsDict["dscp"]["val"]
override["interval"] = paramsDict["pingInterval"]["val"]
override["isochronous"] = paramsDict["isochronous"]["val"]
if override["isochronous"]:
        override["ipg"] = paramsDict["iso_gap"]["val"]
        iso_mean = paramsDict["iso_mean"]["val"]
        iso_mean_units_drop = paramsDict["iso_mean_units"]["val"]
        for item in iso_mean_units_drop:
                if item["selected"]:
                        iso_mean_units = item["value"]
                        break
        override["mean"] = str(iso_mean) + iso_mean_units
        override["stdev"] = paramsDict["iso_stdev"]["val"]
        override["fps"] = paramsDict["iso_fps"]["val"]

tpDictList = []

if not isRealSta:
        if upOrDown == "up" or upOrDown == "dn":
                for thePal in palsToUseSTA:
                        thisPal = thePal["name"]
                        thisInterface = thePal["interface"]
                        tpDictList = sd2Utils.setupTrafficPairs(thisPal, '5g', upOrDown, tpDictList, useWANendpoint=False, measureCongestion=False, palAsAP='', tType=tGenerator, tMode=tProtocol, tBW=tRate, tParallel=tParallel, tLength=tLength, tWindow=tWindow, tpDictOverride=override)
        elif upOrDown == "bi":
                for thePal in palsToUseSTA:
                        thisPal = thePal["name"]
                        thisInterface = thePal["interface"]
                        tpDictList = sd2Utils.setupTrafficPairs(thisPal, '5g', "up", tpDictList, useWANendpoint=False, measureCongestion=False, palAsAP='', tType=tGenerator, tMode=tProtocol, tBW=tRate, tParallel=tParallel, tLength=tLength, tWindow=tWindow, tpDictOverride=override)
                        tpDictList = sd2Utils.setupTrafficPairs(thisPal, '5g', "dn", tpDictList, useWANendpoint=False, measureCongestion=False, palAsAP='', tType=tGenerator, tMode=tProtocol, tBW=tRate, tParallel=tParallel, tLength=tLength, tWindow=tWindow, tpDictOverride=override)
                

else:
        serverSide = {
                "alias": "Server",
                "managementAddress": paramsDict['oBox_server']['val']['address'],
                "trafficAddress": paramsDict['oBox_server']['val']['defaultIp'],
                "devType": "server",
                "radio": "",
                "linkMonitor":False                
        }
        if "Android" in palToUseSTA:
                otherSide = {
                        "alias": "Android",
                        "managementAddress": paramsDict['Android']['val']['address'],
                        "trafficAddress": paramsDict['Android']['val']['endpoints']['ETHERNET']['defaultIp'],
                        "devType": "android",
                        "radio": "",
                        "linkMonitor":False
                }
                if upOrDown == "up":
                        toSide = serverSide
                        fromSide = otherSide
                        pairalias = "Android2Server"
                else:
                        toSide = otherSide
                        fromSide = serverSide
                        pairalias = "Server2Android"
        elif "multiperf" in palToUseSTA:
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
                        pairalias = customAlias + "2Server"
                else:
                        toSide = otherSide
                        fromSide = serverSide
                        pairalias = "Server2" + customAlias
        elif "iperf" in palToUseSTA:
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
                "bitrate": tRate,
                "interval": override["interval"],
                "trafficType": tGenerator,
                "udp": tProtocol,
                "ipVersion": "ipv4",
                "ipStreams": tParallel,
                "window": tWindow,
                "length": tLength,
                "advanced": override["advanced"],
                "dscp": override["dscp"],
                "isochronous": override["isochronous"]
        }
        if updateDict["isochronous"]:
                updateDict["ipg"] = override["ipg"]
                updateDict["mean"] = override["mean"]
                updateDict["stdev"] = override["stdev"]
                updateDict["fps"] = override["fps"]                

        tpDictList.append(updateDict.copy())
        sd2Utils.updateAutotestInst(tpDictList, "trafficPairs", pushConfig=True)

        if upOrDown == "bi":
                toSide = serverSide
                fromSide = otherSide
                if "Android" in palToUseSTA:
                        pairalias = "Android2Server"
                elif "multiperf" in palToUseSTA:
                        pairalias = customAlias + "2Server"
                elif "iperf" in palToUseSTA:
                        pairalias = palToUseSTA + "2Server"
                updateDict = {
                        "to": toSide,
                        "from": fromSide,
                        "settlingTime": paramsDict['settlingTime']['val'],
                        "active": True,
                        "alias": pairalias,
                        "bitrate": tRate,
                        "interval": override["interval"],
                        "trafficType": tGenerator,
                        "udp": tProtocol,
                        "ipVersion": "ipv4",
                        "ipStreams": tParallel,
                        "window": tWindow,
                        "length": tLength,
                        "advanced": override["advanced"],
                        "dscp": override["dscp"],
                        "isochronous": override["isochronous"]
                }
                if updateDict["isochronous"]:
                        updateDict["ipg"] = override["ipg"]
                        updateDict["mean"] = override["mean"]
                        updateDict["stdev"] = override["stdev"]
                        updateDict["fps"] = override["fps"]
                        
                tpDictList.append(updateDict.copy())
                sd2Utils.updateAutotestInst(tpDictList, "trafficPairs", pushConfig=True)

#Remove the attenuators from the setup
print("Removing the attenuators from the test configuration.")
sd2Utils.setAttenDirect(attenForBoxA, 0)
updateDict =({"quadAttens": []})
sd2Utils.updateAutotest(updateDict)
updateDict =({"virtualAttens": []})
sd2Utils.updateAutotest(updateDict)
updateDict =({"mpes": []})
sd2Utils.updateAutotest(updateDict)
sd2Utils.setAttenDirect(attenForBoxA, 0)
sd2Utils.setAttenDirect(attenForBoxB, 90)

if not isRealSta:
        #Setting up Pal configurations:
        staDictList = []
        stasAndConfigs = {}
        if band=="5g":         staDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT"}
        elif band=="24g":      staDictOverride={"bandwidth":"BANDWIDTH_40_ADAPT"}
        #staDictOverride={"bandwidth":"BANDWIDTH_20_FIXED"}
        staDictOverride={"bandwidth":"BANDWIDTH_ADAPT"}
        staDictOverride["vEnable"]=True
        staDictOverride["kEnable"]=True
        staDictOverride["rFastTransitionEnable"]=True
        staDictOverride["ssid"] = ssid        
        staDictOverride["security"] = security        
        staDictOverride["password"] = password        
        if palsAsAPs:
                staDictOverride["ssid"] = palAsAPssid
                staDictOverride["password"] = palAsAPpassword
                staDictOverride["security"] = palAsAPsecurity
        if paramsDict["roamTargetThreshold"]["val"] != "": staDictOverride["roamTargetThreshold"] = paramsDict["roamTargetThreshold"]["val"]
        if paramsDict["roamThreshold"]["val"] != "":       staDictOverride["roamThreshold"]       = paramsDict["roamThreshold"]["val"]
        for thePal in palsToUseSTA:
                thisPal = thePal["name"]
                thisInterface = thePal["interface"]
                if "mlo" in thePal:
                        #Setting up Pal STA MLO configurations:
                        print('Setting up PAL STA MLO configurations:')
                        mloConfig_STA = thePal["mlo"]
                        mloConfig = mloConfig_STA
                        (STAselectedValues, staDictList) = sd2Utils.setupMloSTA(thisPal, mloConfig,staDictList,bssid='',pushConfig=True)
                else:
                        staDictList = sd2Utils.setupSTA(thisPal, band, staDictList, type=thisInterface, channel=channelToUse, bssid='', streams=2, staDictOverride=staDictOverride, pushConfig=True)
                stasAndConfigs[thisPal] = {"band":band, "config":staDictList[len(staDictList)-1]}

        print(staDictList[0])
        targetRadio = staDictList[0]['palRadio']

#### NOTE!!!!  DEBUG ONLY!!!! REMOVE THIS FOR NORMAL OPERATION.
'''
tpDictList = sd2Utils.setupTrafficPairs("W1E-STApal", '5g', "dn", tpDictList, useWANendpoint=False, measureCongestion=False, palAsAP='', tType=tGenerator, tMode=tProtocol, tBW="1K", tParallel=tParallel, tLength=tLength, tWindow=tWindow, tpDictOverride=override)

staDictList = []
staDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT"}
staDictOverride["vEnable"]=True
staDictOverride["kEnable"]=True
staDictOverride["rFastTransitionEnable"]=True
if palsAsAPs: staDictOverride["ssid"] = palAsAPssid
if paramsDict["roamTargetThreshold"]["val"] != "": staDictOverride["roamTargetThreshold"] = paramsDict["roamTargetThreshold"]["val"]
if paramsDict["roamThreshold"]["val"] != "":       staDictOverride["roamThreshold"]       = paramsDict["roamThreshold"]["val"]
staDictList = sd2Utils.setupSTA("W1E-STApal", '5g', staDictList, type="INTERFACE_AX", channel=0, bssid='', streams=2, staDictOverride=staDictOverride, pushConfig=True)
targetRadio = staDictList[0]['palRadio']
'''

############### START SECTION: WAIT FOR REQUIRED PAL TO BE ASSOCIATED #########################

if not isRealSta:
        for thePal in palsToUseSTA:
                thisPal = thePal["name"]
                thisInterface = thePal["interface"]
                maxTries = 2
                tries = 0
                while tries < maxTries:
                        retObj = sd2Utils.waitForAssociation(thisPal,targetRadio,timeToWait=45,quitOnFail=False)
                        tries += 1
                        if "returnStatus" in retObj:
                                if retObj["returnStatus"] == "failed":
                                        print("waitForAssociation failed with: {}".format(retObj["reason"]))
                                        if tries < maxTries:
                                                staDictList = cyclePalAndTryAgain(thisPal,stasAndConfigs,staDictList)
                                        else:
                                                print("Failure of waitForAssociation {} times, for reason:{}.  Allowing termination of the script.".format(tries,retObj["reason"]))
                                                sys.exit(22)
else:
        print("Wait a bit and hope that your real station is associated.")
        time.sleep(10)

stasInfo = {}
if not isRealSta:
        if globalsfile.online:
            print("The AP is associated.  Now get the current BSSID.")
            for thePal in palsToUseSTA:
                    thisPal = thePal["name"]
                    thisInterface = thePal["interface"]
                    sd2Utils.getPalStatus(thisPal,3,targetRadio=targetRadio)
                    print(globalsfile.palStatus)
                    theChannel = globalsfile.palStatus["primaryChannel"]
                    if theChannel < 20: theBand = "24g"
                    if theChannel > 20: theBand = "5g"
                    theBSSID = globalsfile.palStatus["bssid"]
                    stasInfo[thisPal] = {"channel":theChannel, "band":theBand, "bssid":theBSSID}
        else:
            print("Not online.")
            sys.exit(42)

print("The station info is {}".format(stasInfo))
        
palToUseSnifferdrop = paramsDict["palToUseSniff"]["val"]
for item in palToUseSnifferdrop:
    if item["selected"]:
        palToUseSniffer = item["value"]
        break

thisDrop = paramsDict["palToUseSniff2"]["val"]
for item in thisDrop:
    if item["selected"]:
        palToUseSniffer2 = item["value"]
        break
if palToUseSniffer2 == "None": palToUseSniffer2 = None
if palToUseSniffer2 == palToUseSniffer:
        print("The pal configured for the second sniffer ({}) is the same as the pal configured for the first sniffer.  No point to this, so not doing a second sniffer.".format(palToUseSniffer2))
        palToUseSniffer2 = None
if palToUseSniffer2 == palToUseSTA:
        print("The pal configured for the second sniffer ({}) is the same as the pal configured for the STA.  Cannot be done, so not doing a second sniffer.".format(palToUseSniffer2))
        palToUseSniffer2 = None

thisDrop = paramsDict["palToUseSniff3"]["val"]
for item in thisDrop:
    if item["selected"]:
        palToUseSniffer3 = item["value"]
        break
if palToUseSniffer3 == "None": palToUseSniffer3 = None
if palToUseSniffer3 == palToUseSniffer:
        print("The pal configured for the third sniffer ({}) is the same as the pal configured for the first sniffer.  No point to this, so not doing a third sniffer.".format(palToUseSniffer3))
        palToUseSniffer3 = None
if palToUseSniffer3 == palToUseSTA:
        print("The pal configured for the third sniffer ({}) is the same as the pal configured for the STA.  Cannot be done, so not doing a third sniffer.".format(palToUseSniffer3))
        palToUseSniffer3 = None

#Setting up sniffers.
#Is SnifferRelay running?
SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],False,args=paramsDict['oBox_server']['val']['publicip'])

#Make a single sniffer
snifSetDictList = []
snifDispDictList = []
snifStartDictList = []

(snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer, band1, 160, channelToUseSniffer1, "INTERFACE_AX", snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])
if palToUseSniffer2 != None:
        (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer2, band2, 160, channelToUseSniffer2, "INTERFACE_AX", snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])
	
if palToUseSniffer3 != None:
        (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer3, band3, 160, channelToUseSniffer3, "INTERFACE_AX", snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])
	
# Update sniffer Autotest configs and push
sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True)

############### END SECTION: WAIT FOR REQUIRED PAL TO BE ASSOCIATED #########################

findDisconnectionPoints = False

if not findDisconnectionPoints:
        disconnectionPoints = paramsDict["disconnectionPoints"]["val"]
        dp = disconnectionPoints.split(",")
        if len(dp) != 2: findDisconnectionPoints = True

if not findDisconnectionPoints:
        disconnectPointA = int(dp[0])
        if disconnectPointA < 0 or disconnectPointA > 90: findDisconnectionPoints = True
        disconnectPointB = int(dp[1])
        if disconnectPointB < 0 or disconnectPointB > 90: findDisconnectionPoints = True

boxAbssid = None
boxBbssid = None
meshObject = None

assign_STA_MAC = paramsDict["assign_STA_MAC"]["val"]
if assign_STA_MAC:
        globalsfile.palStatus = {}
        globalsfile.palStatus["macAddress"] = paramsDict["assigned_STA_MAC"]["val"]
assign_BoxA_AP_MAC = paramsDict["assign_BoxA_AP_MAC"]["val"]
if assign_BoxA_AP_MAC:
        if meshObject == None: meshObject = {}
        meshObject["boxa_24g"] = {"bssid":paramsDict["assigned_BoxA_AP_MAC"]["val"].lower()}
        meshObject["boxa_5g"] =  {"bssid":paramsDict["assigned_BoxA_AP_MAC"]["val"].lower()}
        meshObject["boxa_6g"] =  {"bssid":paramsDict["assigned_BoxA_AP_MAC"]["val"].lower()}
        globalsfile.palStatus["bssid"] = paramsDict["assigned_BoxA_AP_MAC"]["val"].lower()
        boxAbssid = paramsDict["assigned_BoxA_AP_MAC"]["val"].lower()
        theBSSID = boxAbssid.lower()
assign_BoxB_AP_MAC = paramsDict["assign_BoxB_AP_MAC"]["val"]
if assign_BoxB_AP_MAC:
        if meshObject == None: meshObject = {}
        meshObject["boxb_24g"] = {"bssid":paramsDict["assigned_BoxB_AP_MAC"]["val"].lower()}
        meshObject["boxb_5g"] =  {"bssid":paramsDict["assigned_BoxB_AP_MAC"]["val"].lower()}
        meshObject["boxb_6g"] =  {"bssid":paramsDict["assigned_BoxB_AP_MAC"]["val"].lower()}
        boxBbssid = paramsDict["assigned_BoxB_AP_MAC"]["val"].lower()

base_endpoint = "http://localhost:8080/pcapAPI"

if palToUseSniffer2 != None:
        theChans = [channelToUseSniffer1,channelToUseSniffer2]
        
        if not assign_BoxA_AP_MAC:
                sd2Utils.setAttenDirect(attenForBoxA, 0)
                sd2Utils.setAttenDirect(attenForBoxB, 90)
                '''
                for atten in range (1,90,2):
                        print("Ramping the attenuation to BoxB to {}".format(atten))
                        sd2Utils.setAttenDirect(attenForBoxB,atten)
                        time.sleep(1)
                '''
                #Find the bssids using the sniffer.  This should be generic even if you are using a real client.
                sd2Utils.startSniffers(snifStartDictList)
                time.sleep(15)
                pcapFile = sd2Utils.stopSniffers()
                print("PCAP file used to get the BSSID is located here: " + pcapFile)
                parts = pcapFile.split("/")
                fileName = parts[len(parts)-1]
                pcapDir = ""
                for p in range(0,len(parts)-1): pcapDir += parts[p] + "/"
                api_endpoint = base_endpoint + "?action=getDataOfType"
                api_endpoint += "&filters=Beacon"
                api_endpoint += "&lastPacket=100000"
                api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
                print("The call is to:  " + api_endpoint)
                apiResponse = requests.get(url=api_endpoint)
                returnObject = json.loads(apiResponse.text)
                result = returnObject["result"]
                pss = result["perStreamStats"]
                if len(pss) > 0:
                        #theChans = []
                        for theseStats in pss:
                                theseStats["frequency"] = theseStats["rssiPlot"][0]["channel"]
                                theseStats["channel"] = sd2Utils.FrequencyToChannelNumber(theseStats["frequency"])
                                #theChans.append(theseStats["channel"])
                        #Now find the MAC for each channel.
                        for theChannel in theChans:
                                perChanPss = []
                                for thisPss in pss:
                                        if thisPss["channel"] == theChannel: perChanPss.append(thisPss)                                
                                theMax = perChanPss[0]["count"]
                                apSide = perChanPss[0]["transmitterAddress"]
                                for stats in perChanPss:
                                        if stats["count"] > theMax:
                                                theMax = stats["count"]
                                                apSide = stats["transmitterAddress"]
                                print("\n\nThe MAC on the AP side for channel {} is {}\n\n".format(theChannel,apSide))

                                if theChannel < 20: meshObject["boxa_24g"] = {"bssid":apSide}
                                elif theChannel > 20: meshObject["boxa_5g"] = {"bssid":apSide}
                                print("\n\nThe BSSID for box A is is {}\n\n".format(meshObject))

                sd2Utils.setAttenDirect(attenForBoxA, 90)
                '''
                for atten in range (1,90,2):
                        print("Ramping the attenuation to BoxA to {}".format(atten))
                        sd2Utils.setAttenDirect(attenForBoxA,atten)
                        time.sleep(1)
                '''

        if not assign_BoxB_AP_MAC:
                sd2Utils.setAttenDirect(attenForBoxB, 0)
                #Find the bssids using the sniffer.  This should be generic even if you are using a real client.
                sd2Utils.startSniffers(snifStartDictList)
                time.sleep(15)
                pcapFile = sd2Utils.stopSniffers()
                print("PCAP file used to get the BSSID is located here: " + pcapFile)
                parts = pcapFile.split("/")
                fileName = parts[len(parts)-1]
                pcapDir = ""
                for p in range(0,len(parts)-1): pcapDir += parts[p] + "/"
                api_endpoint = base_endpoint + "?action=getDataOfType"
                api_endpoint += "&filters=Beacon"
                api_endpoint += "&lastPacket=100000"
                api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
                print("The call is to:  " + api_endpoint)
                apiResponse = requests.get(url=api_endpoint)
                returnObject = json.loads(apiResponse.text)
                result = returnObject["result"]
                pss = result["perStreamStats"]
                if len(pss) > 0:
                        #theChans = []
                        for theseStats in pss:
                                theseStats["frequency"] = theseStats["rssiPlot"][0]["channel"]
                                theseStats["channel"] = sd2Utils.FrequencyToChannelNumber(theseStats["frequency"])
                                #theChans.append(theseStats["channel"])
                        #Now find the MAC for each channel.
                        for theChannel in theChans:
                                perChanPss = []
                                for thisPss in pss:
                                        if thisPss["channel"] == theChannel: perChanPss.append(thisPss)                                
                                theMax = perChanPss[0]["count"]
                                apSide = perChanPss[0]["transmitterAddress"]
                                for stats in perChanPss:
                                        if stats["count"] > theMax:
                                                theMax = stats["count"]
                                                apSide = stats["transmitterAddress"]
                                print("\n\nThe MAC on the AP side for channel {} is {}\n\n".format(theChannel,apSide))

                                if theChannel < 20: meshObject["boxb_24g"] = {"bssid":apSide}
                                elif theChannel > 20: meshObject["boxb_5g"] = {"bssid":apSide}
                                print("\n\nThe BSSID for box B is is {}\n\n".format(meshObject))


                #While we figure out how to distinguish 6 GHz channels from 5 GHz channels, ...
                meshObject["boxa_6g"] = meshObject["boxa_5g"]
                meshObject["boxb_6g"] = meshObject["boxb_5g"]

        #Move it back to the box A AP.
        sd2Utils.setAttenDirect(attenForBoxA, 0)
        sd2Utils.setAttenDirect(attenForBoxB, 90)
        
        '''
        for atten in range (1,90,2):
                print("Ramping the attenuation to BoxB to {}".format(atten))
                sd2Utils.setAttenDirect(attenForBoxB,atten)
                time.sleep(1)
        '''
        print("Take some time to settle back onto the AP in box A.")
        time.sleep(15)  #Some time to settle.        

if findDisconnectionPoints:
        
        #### FIND DISASSOCIATION POINT FOR BOX A, AND FOR BOX B
        sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
        thisBSSID = ""
        while len(thisBSSID) < 2:
                thisBSSID = globalsfile.palStatus["bssid"]
                boxAbssid = thisBSSID
        print("Online status is {}, connected to BSSID {}.".format(globalsfile.online,thisBSSID))
        for attenuation in range (0,90,1):
                sd2Utils.setAttenDirect(attenForBoxA, attenuation)
                sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
                if globalsfile.online:
                        print("Still connected to {}".format(globalsfile.palStatus["bssid"]))
                else:
                        disconnectPointA = attenuation
                        print("Disconnection point for box A is {}".format(disconnectPointA))
                        break

        sd2Utils.setAttenDirect(attenForBoxA, 90)
        '''
        for atten in range (1,90,2):
                print("Ramping the attenuation to BoxA to {}".format(atten))
                sd2Utils.setAttenDirect(attenForBoxA,atten)
                time.sleep(1)
        '''
        sd2Utils.setAttenDirect(attenForBoxB, 0)
        maxTries = 2
        tries = 0
        while tries < maxTries:
                retObj = sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)
                tries += 1
                if "returnStatus" in retObj:
                        if retObj["returnStatus"] == "failed":
                                print("waitForAssociation failed with: {}".format(retObj["reason"]))
                                if tries < maxTries:
                                        staDictList = cyclePalAndTryAgain(thisPal,stasAndConfigs,staDictList)
                                else:
                                        print("Failure of waitForAssociation {} times, for reason:{}.  Allowing termination of the script.".format(tries,retObj["reason"]))
                                        sys.exit(23)
        
        sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
        thisBSSID = globalsfile.palStatus["bssid"]
        while len(thisBSSID) < 2:
                print("Oh no.  The BSSID is {}, and the palStatus is {}".format(thisBSSID,globalsfile.palStatus))
                sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
                thisBSSID = globalsfile.palStatus["bssid"]
                boxBbssid = thisBSSID
        print("Online status is {}, connected to BSSID {}.".format(globalsfile.online,thisBSSID))
        for attenuation in range (0,90,1):
                sd2Utils.setAttenDirect(attenForBoxB, attenuation)
                sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
                if globalsfile.online:
                        print("Still connected to {}".format(globalsfile.palStatus["bssid"]))
                else:
                        disconnectPointB = attenuation
                        print("Disconnection point for box B is {}".format(disconnectPointA))
                        break
        sd2Utils.setAttenDirect(attenForBoxA, 0)
        sd2Utils.setAttenDirect(attenForBoxB, 90)
        '''
        for atten in range (1,90,2):
                print("Ramping the attenuation to BoxB to {}".format(atten))
                sd2Utils.setAttenDirect(attenForBoxB,atten)
                time.sleep(1)
        '''
        maxTries = 2
        tries = 0
        while tries < maxTries:
                retObj = sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)
                tries += 1
                if "returnStatus" in retObj:
                        if retObj["returnStatus"] == "failed":
                                print("waitForAssociation failed with: {}".format(retObj["reason"]))
                                if tries < maxTries:
                                        staDictList = cyclePalAndTryAgain(thisPal,stasAndConfigs,staDictList)
                                else:
                                        print("Failure of waitForAssociation {} times, for reason:{}.  Allowing termination of the script.".format(tries,retObj["reason"]))
                                        sys.exit(24)
        thisBSSID = ""
        while len(thisBSSID) < 2:
                thisBSSID = globalsfile.palStatus["bssid"]

print("\n")
print("{} The disconnection point for box A is {}db,  and for box B is {} dB. {}".format(cRed,disconnectPointA,disconnectPointB,cNormal))
print("\n")

#### FIND DISASSOCIATION POINT FOR BOX A, AND FOR BOX B

if isRealSta and not assign_STA_MAC:
        #You don't know the STA MAC address yet.  Find it out here.
        #Need some other way of finding the STA MAC address.  Again, let's use the sniffer.  Try running some traffic and getting the STA MAC from that.
        base_endpoint = "http://localhost:8080/pcapAPI"        
        sd2Utils.setAttenDirect(attenForBoxA, 0)
        sd2Utils.setAttenDirect(attenForBoxB, 90)
        '''
        for atten in range (1,90,2):
                print("Ramping the attenuation to BoxB to {}".format(atten))
                sd2Utils.setAttenDirect(attenForBoxB,atten)
                time.sleep(1)
        '''
        sd2Utils.startSniffers(snifStartDictList)
        print("\n\n STARTING AUTOTEST FOR MAC ID \n\n")
        sd2Utils.startAutotest()
        time.sleep(15)
        print("\n\n STOPPING AUTOTEST FOR MAC ID \n\n")
        json_path = sd2Utils.stopAutotest(unzip=False,saveCSV=False,saveTaJSON=False)
        pcapFile = sd2Utils.stopSniffers()
        
        print("PCAP file used to get the STA MAC is located here: " + pcapFile)
        parts = pcapFile.split("/")
        fileName = parts[len(parts)-1]
        pcapDir = ""
        for p in range(0,len(parts)-1): pcapDir += parts[p] + "/"
        api_endpoint = base_endpoint + "?action=getDataOfType"
        api_endpoint += "&filters=Beacon"
        api_endpoint += "&lastPacket=100000"
        api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
        print("The call is to:  " + api_endpoint)
        apiResponse = requests.get(url=api_endpoint)
        returnObject = json.loads(apiResponse.text)
        result = returnObject["result"]
        pss = result["perStreamStats"]
        if len(pss) > 0:
                theMax = pss[0]["count"]
                apSide = pss[0]["transmitterAddress"]
                for stats in pss:
                        if stats["count"] > theMax:
                                theMax = stats["count"]
                                apSide = stats["transmitterAddress"]
        print("\n\nThe MAC on the AP side is {}\n\n".format(apSide))

        api_endpoint = base_endpoint + "?action=getDataOfType"
        api_endpoint += "&filters=QoS Data,TCP,UDP,Probe response"
        api_endpoint += "&lastPacket=100000"
        api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
        print("The call is to:  " + api_endpoint)
        apiResponse = requests.get(url=api_endpoint)
        returnObject = json.loads(apiResponse.text)
        result = returnObject["result"]
        pss = result["perStreamStats"]
        if len(pss) > 0:
                thePSS = json.loads(json.dumps(pss[0]))
                theMax = pss[0]["count"]
                for stats in pss:
                        if stats["count"] > theMax:
                                thePSS = json.loads(json.dumps(stats))
                                theMax = stats["count"]
                staSide = None
                bssid = None
                if thePSS["transmitterAddress"] == apSide:
                        staSide = thePSS["receiverAddress"]
                        bssid =   thePSS["transmitterAddress"]
                if thePSS["receiverAddress"]    == apSide:
                        staSide = thePSS["transmitterAddress"]
                        bssid =   thePSS["receiverAddress"]
        else:
                #Need to try again.
                retried = 0
                while len(pss) == 0:
                        retried += 1
                        print("\n\n RETRYING TO FIND MAC ADDRESS #{}\n\n".format(retried))
                        sd2Utils.startSniffers(snifStartDictList)
                        print("\n\n STARTING AUTOTEST FOR MAC ID \n\n")
                        sd2Utils.startAutotest()
                        time.sleep(15)
                        print("\n\n STOPPING AUTOTEST FOR MAC ID \n\n")
                        json_path = sd2Utils.stopAutotest(unzip=False,saveCSV=False,saveTaJSON=False)
                        pcapFile = sd2Utils.stopSniffers()
                        parts = pcapFile.split("/")
                        fileName = parts[len(parts)-1]
                        pcapDir = ""
                        for p in range(0,len(parts)-1): pcapDir += parts[p] + "/"
                        api_endpoint = base_endpoint + "?action=getDataOfType"
                        api_endpoint += "&filters=QoS Data,TCP,UDP,Probe response"
                        api_endpoint += "&lastPacket=100000"
                        api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
                        print("The call is to:  " + api_endpoint)
                        apiResponse = requests.get(url=api_endpoint)
                        returnObject = json.loads(apiResponse.text)
                        result = returnObject["result"]
                        pss = result["perStreamStats"]
                thePSS = json.loads(json.dumps(pss[0]))
                theMax = pss[0]["count"]
                for stats in pss:
                        if stats["count"] > theMax:
                                thePSS = json.loads(json.dumps(stats))
                                theMax = stats["count"]
                staSide = None
                bssid = None
                if thePSS["transmitterAddress"] == apSide:
                        staSide = thePSS["receiverAddress"]
                        bssid =   thePSS["transmitterAddress"]
                if thePSS["receiverAddress"]    == apSide:
                        staSide = thePSS["transmitterAddress"]
                        bssid =   thePSS["receiverAddress"]

        print("\n\nThe MAC on the STA side is {}\n\n".format(staSide))
        globalsfile.palStatus = {}
        globalsfile.palStatus["macAddress"] = staSide
        globalsfile.palStatus["bssid"] = bssid
        assigned_STA_MACs = [{"MAC":staSide, "tag":paramsDict["endpointTag"]["val"]}]

logDict = {"palMAC": globalsfile.palStatus["macAddress"]}
sd2Utils.logToJSON(globalsfile.resultsPath, logDict)
        
if boxAbssid == None or boxBbssid == None:
        base_endpoint = "http://localhost:8080/pcapAPI"
        
        sd2Utils.setAttenDirect(attenForBoxA, 0)
        sd2Utils.setAttenDirect(attenForBoxB, 90)
        '''
        for atten in range (1,90,2):
                print("Ramping the attenuation to BoxB to {}".format(atten))
                sd2Utils.setAttenDirect(attenForBoxB,atten)
                time.sleep(1)
        '''
        #Find the bssids using the sniffer.  This should be generic even if you are using a real client.
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(15)
        pcapFile = sd2Utils.stopSniffers()
        print("PCAP file used to get the BSSID is located here: " + pcapFile)
        parts = pcapFile.split("/")
        fileName = parts[len(parts)-1]
        pcapDir = ""
        for p in range(0,len(parts)-1): pcapDir += parts[p] + "/"
        api_endpoint = base_endpoint + "?action=getDataOfType"
        #api_endpoint += "&filters=Beacon"
        api_endpoint += "&filters=Association response,Reassociation response"
        api_endpoint += "&lastPacket=100000"
        api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
        print("The call is to:  " + api_endpoint)
        apiResponse = requests.get(url=api_endpoint)
        returnObject = json.loads(apiResponse.text)
        result = returnObject["result"]
        pss = result["perStreamStats"]
        if len(pss) > 0: boxAbssid = pss[0]["transmitterAddress"]
        print("\n\nThe BSSID for box A is is {}\n\n".format(boxAbssid))
        theBSSID = boxAbssid
        if boxAbssid == None:
                api_endpoint = base_endpoint + "?action=getDataOfType"
                api_endpoint += "&filters=Beacon"
                api_endpoint += "&lastPacket=100000"
                api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
                print("The call is to:  " + api_endpoint)
                apiResponse = requests.get(url=api_endpoint)
                returnObject = json.loads(apiResponse.text)
                result = returnObject["result"]
                pss = result["perStreamStats"]
                if len(pss) > 0: boxAbssid = pss[0]["transmitterAddress"]
                print("\n\nThe BSSID for box A is is {}\n\n".format(boxAbssid))
                theBSSID = boxAbssid
                if theBSSID == None:
                        print("\n Yikes. \n")
                        sys.exit(12)
                

        sd2Utils.setAttenDirect(attenForBoxA, 90)
        '''
        for atten in range (1,90,2):
                print("Ramping the attenuation to BoxA to {}".format(atten))
                sd2Utils.setAttenDirect(attenForBoxA,atten)
                time.sleep(1)
        '''
        sd2Utils.setAttenDirect(attenForBoxB, 0)
        #Find the bssids using the sniffer.  This should be generic even if you are using a real client.
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(15)
        pcapFile = sd2Utils.stopSniffers()
        print("PCAP file used to get the BSSID is located here: " + pcapFile)
        parts = pcapFile.split("/")
        fileName = parts[len(parts)-1]
        pcapDir = ""
        for p in range(0,len(parts)-1): pcapDir += parts[p] + "/"
        api_endpoint = base_endpoint + "?action=getDataOfType"
        #api_endpoint += "&filters=Beacon"
        api_endpoint += "&filters=Association response,Reassociation response"
        api_endpoint += "&lastPacket=100000"
        api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
        print("The call is to:  " + api_endpoint)
        apiResponse = requests.get(url=api_endpoint)
        returnObject = json.loads(apiResponse.text)
        result = returnObject["result"]
        pss = result["perStreamStats"]
        if len(pss) > 0: boxBbssid = pss[0]["transmitterAddress"]
        print("\n\nThe BSSID for box B is is {}\n\n".format(boxBbssid))
        if boxBbssid == None:
                api_endpoint = base_endpoint + "?action=getDataOfType"
                api_endpoint += "&filters=Beacon"
                api_endpoint += "&lastPacket=100000"
                api_endpoint += "&fileName=" + fileName + "&pcapDir=" + pcapDir
                print("The call is to:  " + api_endpoint)
                apiResponse = requests.get(url=api_endpoint)
                returnObject = json.loads(apiResponse.text)
                result = returnObject["result"]
                pss = result["perStreamStats"]
                if len(pss) > 0: boxABssid = pss[0]["transmitterAddress"]
                print("\n\nThe BSSID for box B is is {}\n\n".format(boxBbssid))
                if boxBbssid == None:
                        print("\n Eek. \n")
                        sys.exit(13)

        #Move it back to the box A AP.
        sd2Utils.setAttenDirect(attenForBoxA, 0)
        #sd2Utils.setAttenDirect(attenForBoxB, 90)
        for atten in range (90,91,2):
                print("Ramping the attenuation to BoxB to {}".format(atten))
                sd2Utils.setAttenDirect(attenForBoxB,atten)
                sleepFor = 1
                sleptFor = 0
                while sleptFor < sleepFor:
                        print("Have slept for {} out of {}".format(sleptFor,sleepFor))
                        time.sleep(1)
                        sleptFor += 1
        print("Take some time to settle back onto the AP in box A.")
        #time.sleep(15)  #Some time to settle.
        

######### CREATE MESHINFO FILE
#Make a small meshinfo file.
meshinfo = {
        "boxa_24g":{"bssid":boxAbssid}, "boxa_5g":{"bssid":boxAbssid}, "boxa_6g":{"bssid":boxAbssid},
        "boxb_24g":{"bssid":boxBbssid}, "boxb_5g":{"bssid":boxBbssid}, "boxb_6g":{"bssid":boxBbssid}
}
if meshObject != None: meshinfo = meshObject

try:
        f = open(directory_name + "../../../mesh/meshinfo.json")
        MIJ = json.load(f)
        #print(MIJ)
        meshinfo = {
                "boxa_24g":MIJ["root_24g"],
                "boxa_5g" :MIJ["root_5g"],
                "boxa_6g" :MIJ["root_6g"],
                "boxb_24g":MIJ["extender1_24g"],
                "boxb_5g" :MIJ["extender1_5g"],
                "boxb_6g" :MIJ["extender1_6g"]
        }
except:
        print("No pre-existing meshinfo file to use")
        
miPath = os.path.join(globalsfile.outputDirPath,"meshinfo.json")

# Serializing json
json_object = json.dumps(meshinfo, indent=4)
 
# Writing
with open(miPath, "w") as outfile:
    outfile.write(json_object)                
######### CREATE MESHINFO FILE
print("\n{}\n".format(cGreen))
print("The mesh info file is {}".format(meshinfo))
print("The BSSIDs for box A and B are: A:({}), B:({})".format(boxAbssid,boxBbssid))
print("\n{}\n".format(cNormal))

roamLowSide = paramsDict["roamLowSide"]["val"]
roamHighSide = paramsDict["roamHighSide"]["val"]
secondsPerAttenuationStep = paramsDict["secondsPerAttenuationStep"]["val"]

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

urlIP = paramsDict["oBox_server"]["val"]["publicip"]
serverExec =  "http://" + urlIP + ":8383/exec?command="
serverSpawn = "http://" + urlIP + ":8383/spawn?command="

sd2Utils.startSniffers(snifStartDictList)
time.sleep(3)
staQueries = {}
countRoams = 0
roamSet = 0
staQueries[roamSet] = {}
sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})
roamData = {}

#Get the STA information from the STApals themselves.  Useful, maybe required, for MLO roaming analysis.  Do this just after PCAP is started.
if not isRealSta:
        for thePal in palsToUseSTA:
                palName = thePal["name"]
                if "staPal" in paramsDict[palName]["val"]["devType"]:
                        ipAddress = paramsDict[palName]["val"]["address"]
                        staQuery = querySTA.main(ipAddress)
                        staQueries[roamSet][palName] = {"ipAddress":ipAddress,"staQuery":{"before":staQuery}}
                        sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})

doKick = paramsDict["doKick"]["val"]

if palsAsAPs and doKick:
        macToKick = globalsfile.palStatus["macAddress"]
        print("\nTry to kick {} out of the association tables.\n".format(macToKick))
        palIPs = [paramsDict["Pal-6A"]["val"]["address"], paramsDict["Pal-6B"]["val"]["address"]]
        #Send commands to both Pals to remove the station mac address from its association table.
        for palMgmtIP in palIPs:
                curlExec = "curl http://"+palMgmtIP+":8383/exec?command="
                command = "iwpriv ath0 kickmac " + macToKick
                url = serverExec+curlExec+command
                print("\n>>> For Pal {}, kicking {} off of ath0 with command {}".format(palMgmtIP,macToKick,url))
                resp = requests.get(url=url, timeout=REST_TIMEOUT)
                jsn = json.loads(resp.text)
                print("Return result: {}".format(jsn))
                command = "iwpriv ath1 kickmac " + macToKick
                url = serverExec+curlExec+command
                print("\n>>> For Pal {}, kicking {} off of ath1 with command {}".format(palMgmtIP,macToKick,url))
                resp = requests.get(url=url, timeout=REST_TIMEOUT)
                jsn = json.loads(resp.text)
                print("Return result: {}".format(jsn))
                                

sd2Utils.startAutotest()
time.sleep(5)
if not isRealSta:
        print('getting PAL status:using PAL:'+palToUseSTA+ ' target radio='+ targetRadio)
        sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
        if globalsfile.online:
                startBSSID = globalsfile.palStatus["bssid"]
                try: startBSSID = startBSSID.replace(".","").replace(":","")
                except: startBSSID = theBSSID

#startBSSID = theBSSID
try: startBSSID = startBSSID.replace(".","").replace(":","")
except: startBSSID = startBSSID

newBSSID = None
afterRoam = 0
print("Roaming from {} to {} in steps of {}".format(roamLowSide,roamHighSide,2))
for steps in range (roamLowSide,roamHighSide,2):
        attenuation = max(0,disconnectPointA + steps)
        #otherAttenuation = max(0,disconnectPointB - steps -10)
        otherAttenuation = 0
        #otherAttenuation = max(0,disconnectPointB - 30)
        sd2Utils.setAttenDirect(attenForBoxA, attenuation)
        sd2Utils.setAttenDirect(attenForBoxB, otherAttenuation)
        print("{} At attenuations {}: {}, and {}: {} {}".format(cRed,attenForBoxA,attenuation,attenForBoxB,otherAttenuation,cNormal))
        if afterRoam > 0: afterRoam += 1
        if not isRealSta:
                sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
                if globalsfile.online:
                        thisBSSID = globalsfile.palStatus["bssid"]
                        try: thisBSSID = thisBSSID.replace(".","").replace(":","")
                        except: thisBSSID = thisBSSID
                        if thisBSSID != startBSSID and len(thisBSSID)>2 and afterRoam==0:
                                newBSSID = thisBSSID
                                print("You roamed! From {} to {}.  At {}={}dB, and {}={}dB.".format(startBSSID,newBSSID,attenForBoxA,attenuation,attenForBoxB,otherAttenuation))
                                afterRoam = 1
                        else:
                                print("L1==========> Currently on BSSID:   {}".format(thisBSSID))
                                time.sleep(secondsPerAttenuationStep)
                else:
                        print("Your current association status is {}".format(globalsfile.online))
        else:
                print("Your current association status is {}".format(globalsfile.online))
                time.sleep(secondsPerAttenuationStep)
                
        if afterRoam >= 4 and allowEarlyRampStop:
                print("L1==========> Breaking due to afterRoam = {}, on BSSID = {}".format(afterRoam,thisBSSID))
                break  #Let it continue ramping for a few steps after the roam happens.

print("Stopping sniffers at L1")
pcapFile = sd2Utils.stopSniffers()

command = "cp {} /home/octoscope/Documents/analytics/pcapDirectory/".format(pcapFile);
print("Move PCAP file with {}".format(command))
os.system(command)

#Get the STA information from the STApals themselves.  Useful, maybe required, for MLO roaming analysis.  Do this just after PCAP is saved.
if not isRealSta:
        for thePal in palsToUseSTA:
                palName = thePal["name"]
                if "staPal" in paramsDict[palName]["val"]["devType"]:
                        ipAddress = paramsDict[palName]["val"]["address"]
                        staQuery = querySTA.main(ipAddress)
                        staQueries[roamSet][palName]["staQuery"]["after"] = staQuery
                        sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})

json_path = sd2Utils.stopAutotest(unzip=False,saveCSV=False,saveTaJSON=False)
print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))
#Get rid of the CSV zip file.
theCSV = json_path.replace(".zip","_CSV.zip")
command = "rm " + theCSV
print("Removing the CSV zip file using this command: {}".format(command))
os.system(command)
#Lock STA to current location so that it doesn't randomly roam back.
sd2Utils.setAttenDirect(attenForBoxA,90)
sd2Utils.setAttenDirect(attenForBoxB,00)


testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')

import createReport
endpointTag = paramsDict["endpointTag"]["val"]
for thisMAC in assigned_STA_MACs:
        logDict = {"palMAC": thisMAC["MAC"]}
        print("Placing {} into the log file for palMAC".format(thisMAC))
        sd2Utils.logToJSON(globalsfile.resultsPath, logDict)
        endpointTag = thisMAC["tag"]
        etc = {"endpointTag":endpointTag, "countRoams":countRoams, "roamSet":roamSet,"upOrDown":upOrDown}
        #roams,allFTtimes,appGap,EAPOL_groups,throughputs,roamReport = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,endpointTag,countRoams,roamSet)
        roams,allFTtimes,appGap,EAPOL_groups,throughputs,roamReport = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,etc)
        testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
        roams["FTtimes"] = allFTtimes
        roams["appGap"] = appGap
        roams["EAPOL_groups"] = EAPOL_groups
        roams["throughputs"] = throughputs

        if kafkaBrokerFound:
                try:
                        my_producer.send('plotStream', value = roamReport)
                except:
                        print("The Kafka broker doesn't seem to be responding.")
                        kafkaBrokerFound = False

        roamData["{}".format(countRoams)] = roams
        logDict = {"roamData": roamData}
        #print("To roamData writing {}".format(logDict))
        sd2Utils.logToJSON(globalsfile.resultsPath, logDict)
        countRoams += 1

backAndForthRoaming = paramsDict["backAndForthRoaming"]["val"]
if backAndForthRoaming:

        roamSet += 1
        staQueries[roamSet] = {}
        sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})
        
        globalsfile.fileSuffix = '_ReverseRoam'	# Set pcap filename suffix
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(5)
        #Get the STA information from the STApals themselves.  Useful, maybe required, for MLO roaming analysis.  Do this just after PCAP is started.
        if not isRealSta:
                for thePal in palsToUseSTA:
                        palName = thePal["name"]
                        if "staPal" in paramsDict[palName]["val"]["devType"]:
                                ipAddress = paramsDict[palName]["val"]["address"]
                                staQuery = querySTA.main(ipAddress)
                                staQueries[roamSet][palName] = {"ipAddress":ipAddress,"staQuery":{"before":staQuery}}
                                sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})                                
        
        if palsAsAPs and doKick:
                #Send commands to both Pals to remove the station mac address from its association table.
                for palMgmtIP in palIPs:
                        curlExec = "curl http://"+palMgmtIP+":8383/exec?command="
                        command = "iwpriv ath0 kickmac " + macToKick
                        url = serverExec+curlExec+command
                        print("\n>>> For Pal {}, kicking {} off of ath0 with command {}".format(palMgmtIP,macToKick,url))
                        resp = requests.get(url=url, timeout=REST_TIMEOUT)
                        jsn = json.loads(resp.text)
                        print("Return result: {}".format(jsn))
                        command = "iwpriv ath1 kickmac " + macToKick
                        url = serverExec+curlExec+command
                        print("\n>>> For Pal {}, kicking {} off of ath1 with command {}".format(palMgmtIP,macToKick,url))
                        resp = requests.get(url=url, timeout=REST_TIMEOUT)
                        jsn = json.loads(resp.text)
                        print("Return result: {}".format(jsn))
        
        sd2Utils.startAutotest()
        time.sleep(5)

        if not isRealSta:
                sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
                if globalsfile.online:
                        startBSSID = globalsfile.palStatus["bssid"]
                        try: startBSSID = startBSSID.replace(".","").replace(":","")
                        except: startBSSID = boxBbssid

        #startBSSID = boxBbssid
        try: startBSSID = startBSSID.replace(".","").replace(":","")
        except: startBSSID = startBSSID.lower()
        theBSSID = startBSSID.lower()
        newBSSID = None
        afterRoam = 0        
        for steps in range (roamLowSide,roamHighSide,2):
                attenuation = max(0,disconnectPointB + steps)
                #otherAttenuation = max(0,disconnectPointA - steps -10)
                otherAttenuation = 0
                sd2Utils.setAttenDirect(attenForBoxB, attenuation)
                sd2Utils.setAttenDirect(attenForBoxA, otherAttenuation)
                print("{} At attenuations {}: {}, and {}: {} {}".format(cRed,attenForBoxA,attenuation,attenForBoxB,otherAttenuation,cNormal))
                if afterRoam > 0: afterRoam += 1
                if not isRealSta:
                        sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
                        if globalsfile.online:
                                thisBSSID = globalsfile.palStatus["bssid"].lower()
                                try: thisBSSID = thisBSSID.replace(".","").replace(":","").lower()
                                except: thisBSSID = thisBSSID.lower()
                                if thisBSSID != startBSSID and len(thisBSSID)>2 and afterRoam==0:
                                        newBSSID = thisBSSID
                                        print("You roamed! From {} to {}.  At {}={}dB, and {}={}dB.".format(startBSSID,newBSSID,attenForBoxA,attenuation,attenForBoxB,otherAttenuation))
                                        afterRoam = 1
                                else:
                                        print("L2==========> Currently on BSSID:   {}".format(thisBSSID))
                                        time.sleep(secondsPerAttenuationStep)
                        else:
                                print("Your current association status is {}".format(globalsfile.online))
                else:
                        print("Your current association status is {}".format(globalsfile.online))
                        time.sleep(secondsPerAttenuationStep)

                if afterRoam >= 4 and allowEarlyRampStop:
                        print("L1==========> Breaking due to afterRoam = {}, on BSSID = {}".format(afterRoam,thisBSSID))
                        break  #Let it continue ramping for a few steps after the roam happens.

        print("Stopping sniffers at L2")
        pcapFile = sd2Utils.stopSniffers()

        #Get the STA information from the STApals themselves.  Useful, maybe required, for MLO roaming analysis.  Do this just after PCAP is saved.
        if not isRealSta:
                for thePal in palsToUseSTA:
                        palName = thePal["name"]
                        if "staPal" in paramsDict[palName]["val"]["devType"]:
                                ipAddress = paramsDict[palName]["val"]["address"]
                                staQuery = querySTA.main(ipAddress)
                                staQueries[roamSet][palName]["staQuery"]["after"] = staQuery
                                sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})                                

        command = "cp {} /home/octoscope/Documents/analytics/pcapDirectory/".format(pcapFile);
        print("Move PCAP file with {}".format(command))
        os.system(command)

        json_path = sd2Utils.stopAutotest(unzip=False,saveCSV=False,saveTaJSON=False)
        print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))
        #Get rid of the CSV zip file.
        theCSV = json_path.replace(".zip","_CSV.zip")
        command = "rm " + theCSV
        print("Removing the CSV zip file using this command: {}".format(command))
        os.system(command)        
        #Lock STA to current location so that it doesn't randomly roam back.
        sd2Utils.setAttenDirect(attenForBoxA,00)
        sd2Utils.setAttenDirect(attenForBoxB,90)

        testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
        print()
        print('#########################################')
        print('>>> Getting test results')
        print('#########################################')

        for thisMAC in assigned_STA_MACs:
                logDict = {"palMAC": thisMAC["MAC"]}
                print("Placing {} into the log file for palMAC".format(thisMAC))
                sd2Utils.logToJSON(globalsfile.resultsPath, logDict)
                endpointTag = thisMAC["tag"]
                etc = {"endpointTag":endpointTag, "countRoams":countRoams, "roamSet":roamSet,"upOrDown":upOrDown}    
                #roams,allFTtimes,appGap,EAPOL_groups,throughputs,roamReport = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,endpointTag,countRoams,roamSet)
                roams,allFTtimes,appGap,EAPOL_groups,throughputs,roamReport = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,etc)
                testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
                roams["FTtimes"] = allFTtimes
                roams["appGap"] = appGap
                roams["EAPOL_groups"] = EAPOL_groups
                roams["throughputs"] = throughputs

                if kafkaBrokerFound:
                        try:
                                my_producer.send('plotStream', value = roamReport)
                        except:
                                print("The Kafka broker doesn't seem to be responding.")
                                kafkaBrokerFound = False
        

                roamData["{}".format(countRoams)] = roams
                logDict = {"roamData": roamData}
                #print("To roamData writing {}".format(logDict))
                sd2Utils.logToJSON(globalsfile.resultsPath, logDict)
                countRoams += 1

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

AdditionalRoams = paramsDict["AdditionalRoams"]["val"]

print("\n\n The Number of Additional Roams to be Performed is: {}".format(AdditionalRoams))

for AR in range (0,AdditionalRoams):
        #Let's do this a few more times, if desired.

        thisStartTime = time.time()

        print("\n{}Additional Roam Item #{} out of {}{}\n".format(cRed,AR+1,AdditionalRoams,cNormal))
        globalsfile.fileSuffix = '_{}'.format(roamSet)

        roamSet += 1
        staQueries[roamSet] = {}
        sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})
        

        if not backAndForthRoaming:
                # Reset the attenuation to the start        
                checkStart = time.time()
                sd2Utils.setAttenDirect(attenForBoxA,0)
                #sd2Utils.setAttenDirect(attenForBoxB,90)
                for atten in range (90,91,2):
                        print("Ramping the attenuation to BoxB to {}".format(atten))
                        sd2Utils.setAttenDirect(attenForBoxB,atten)
                        sleepFor = 1
                        sleptFor = 0
                        while sleptFor < sleepFor:
                                print("Have slept for {} out of {}".format(sleptFor,sleepFor))
                                time.sleep(1)
                                sleptFor += 1
                #sd2Utils.setAttenDirect('QA-F',90)
                #sd2Utils.setAttenDirect('QA-D',90)
                checkStop = time.time()
                print("\n{} The time it took to initialize the attenuators was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))
        
                # Let the station move back to the start.
                checkStart = time.time()
                if not isRealSta:
                        thisBSSID = None
                        count = 0
                        while thisBSSID!=startBSSID:
                                maxTries = 2
                                tries = 0
                                while tries < maxTries:
                                        retObj = sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio,quitOnFail=False)
                                        tries += 1
                                        if "returnStatus" in retObj:
                                                if retObj["returnStatus"] == "failed":
                                                        print("getPalStatus failed with: {}".format(retObj["reason"]))
                                                        if tries < maxTries:
                                                                staDictList = cyclePalAndTryAgain(palToUseSTA,stasAndConfigs,staDictList)
                                                        else:
                                                                print("Failure of getPalStatus {} times, for reason:{}.  Allowing termination of the script.".format(tries,retObj["reason"]))
                                                                sys.exit(33)
                                
                                thisBSSID = globalsfile.palStatus["bssid"].lower()
                                try: thisBSSID = thisBSSID.replace(".","").replace(":","").lower()
                                except: thisBSSID = thisBSSID.lower()
                                count += 1
                                if count > 30 and thisBSSID!=startBSSID:
                                        print("You are not moving back to the original BSSID for some reason.  Starting BSSID should be {}, but you are on {}".format(startBSSID,thisBSSID))
                                        sys.exit(77)
                else:
                        print("Wait and hope that your STA moves back to the original AP.")
                        #time.sleep(10)
                checkStop = time.time()
                print("\n{} The time it took to move the STA back to the starting position was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))

        # Start up sniffer
        checkStart = time.time()
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(5)
        checkStop = time.time()
        print("\n{} The time it took to start the sniffers was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))
        #Get the STA information from the STApals themselves.  Useful, maybe required, for MLO roaming analysis.  Do this just after PCAP is started.
        if not isRealSta:
                for thePal in palsToUseSTA:
                        palName = thePal["name"]
                        if "staPal" in paramsDict[palName]["val"]["devType"]:
                                ipAddress = paramsDict[palName]["val"]["address"]
                                staQuery = querySTA.main(ipAddress)
                                staQueries[roamSet][palName] = {"ipAddress":ipAddress,"staQuery":{"before":staQuery}}
                                sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})                                
                
        if palsAsAPs and doKick:
                checkStart = time.time()
                macToKick = globalsfile.palStatus["macAddress"]
                print("\nTry to kick {} out of the association tables.\n".format(macToKick))
                palIPs = [paramsDict["Pal-6A"]["val"]["address"], paramsDict["Pal-6B"]["val"]["address"]]
                #Send commands to both Pals to remove the station mac address from its association table.
                for palMgmtIP in palIPs:
                        curlExec = "curl http://"+palMgmtIP+":8383/exec?command="
                        command = "iwpriv ath0 kickmac " + macToKick
                        url = serverExec+curlExec+command
                        print("\n>>> For Pal {}, kicking {} off of ath0 with command {}".format(palMgmtIP,macToKick,url))
                        resp = requests.get(url=url, timeout=REST_TIMEOUT)
                        jsn = json.loads(resp.text)
                        print("Return result: {}".format(jsn))
                        command = "iwpriv ath1 kickmac " + macToKick
                        url = serverExec+curlExec+command
                        print("\n>>> For Pal {}, kicking {} off of ath1 with command {}".format(palMgmtIP,macToKick,url))
                        resp = requests.get(url=url, timeout=REST_TIMEOUT)
                        jsn = json.loads(resp.text)
                        print("Return result: {}".format(jsn))
                checkStop = time.time()
                print("\n{} The time it took to kick the roaming STA MAC off the Pal APs was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))
                                                
        # Start up test
        checkStart = time.time()
        sd2Utils.startAutotest()
        time.sleep(5)
        checkStop = time.time()
        print("\n{} The time it took to start up the test was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))

        checkStart = time.time()
        afterRoam = 0

        if not isRealSta:
                sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
                if globalsfile.online:
                        startBSSID = globalsfile.palStatus["bssid"]
                        try: startBSSID = startBSSID.replace(".","").replace(":","")
                        except: startBSSID = boxAbssid.lower()
        
        
        #startBSSID = boxAbssid.lower()
        try: startBSSID = startBSSID.replace(".","").replace(":","").lower()
        except: startBSSID = startBSSID.lower()
        theBSSID = startBSSID.lower()
        newBSSID = None
        #for attenuation in range (25,90,5):
        #       otherAttenuation = 90 - attenuation - 40
        for steps in range (roamLowSide,roamHighSide,2):
                attenuation = max(0,disconnectPointA + steps)
                #otherAttenuation = max(0,disconnectPointB - steps -10)
                otherAttenuation = 0
                #otherAttenuation = disconnectPointB - 30 
                sd2Utils.setAttenDirect(attenForBoxA, attenuation)
                sd2Utils.setAttenDirect(attenForBoxB, otherAttenuation)
                print("{} At attenuations {}: {}, and : {} {} {}".format(cRed,attenForBoxA,attenuation,attenForBoxB,otherAttenuation,cNormal))
                if afterRoam > 0: afterRoam += 1
                if not isRealSta:
                        maxTries = 2
                        tries = 0
                        while tries < maxTries:                        
                                retObj = sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio,quitOnFail=False)
                                tries += 1
                                if "returnStatus" in retObj:
                                        if retObj["returnStatus"] == "failed":
                                                print("getPalStatus failed with: {}".format(retObj["reason"]))
                                                if tries < maxTries:
                                                        staDictList = cyclePalAndTryAgain(palToUseSTA,stasAndConfigs,staDictList)
                                                else:
                                                        print("Failure of getPalStatus {} times, for reason:{}.  Allowing termination of the script.".format(tries,retObj["reason"]))
                                                        sys.exit(34)
                        if globalsfile.online:
                                thisBSSID = globalsfile.palStatus["bssid"].lower()
                                try: thisBSSID = thisBSSID.replace(".","").replace(":","").lower()
                                except: thisBSSID = thisBSSID.lower()
                                if thisBSSID != startBSSID and len(thisBSSID)>2 and afterRoam==0:
                                        newBSSID = thisBSSID.lower()
                                        print("{} You roamed! From {} to {}.  At {}={}dB, and {}={}dB.{}".format(cRed,startBSSID,newBSSID,attenForBoxA,attenuation,attenForBoxB,otherAttenuation,cNormal))
                                        afterRoam = 1
                                else:
                                        print("L3==========> Currently on BSSID:   {}".format(thisBSSID))
                                        time.sleep(secondsPerAttenuationStep)
                        else:
                                print("Your current association status is {}".format(globalsfile.online))
                else:
                        print("Your current association status is {}".format(globalsfile.online))
                        time.sleep(secondsPerAttenuationStep)

                if afterRoam >= 4 and allowEarlyRampStop:
                        print("L1==========> Breaking due to afterRoam = {}, on BSSID = {}".format(afterRoam,thisBSSID))
                        break  #Let it continue ramping for a few steps after the roam happens.
        checkStop = time.time()
        print("\n{} The time it took to run the complete roaming test  was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))

        #Stop the sniffer
        checkStart = time.time()
        print("Stopping sniffers at L3")
        pcapFile = sd2Utils.stopSniffers()
        checkStop = time.time()
        print("\n{} The time it took to stop the sniffers was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))

        command = "cp {} /home/octoscope/Documents/analytics/pcapDirectory/".format(pcapFile);
        print("Move PCAP file with {}".format(command))
        os.system(command)
        #Get the STA information from the STApals themselves.  Useful, maybe required, for MLO roaming analysis.  Do this just after PCAP is saved.
        if not isRealSta:
                for thePal in palsToUseSTA:
                        palName = thePal["name"]
                        if "staPal" in paramsDict[palName]["val"]["devType"]:
                                ipAddress = paramsDict[palName]["val"]["address"]
                                staQuery = querySTA.main(ipAddress)
                                staQueries[roamSet][palName]["staQuery"]["after"] = staQuery
                                sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})                                
                
        #Stop the test
        checkStart = time.time()
        json_path = sd2Utils.stopAutotest(unzip=False,saveCSV=False,saveTaJSON=False)
        print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))
        #Get rid of the CSV zip file.
        theCSV = json_path.replace(".zip","_CSV.zip")
        command = "rm " + theCSV
        print("Removing the CSV zip file using this command: {}".format(command))
        os.system(command)
        #Lock STA to current location so that it doesn't randomly roam back.
        sd2Utils.setAttenDirect(attenForBoxA,90)
        sd2Utils.setAttenDirect(attenForBoxB,00)        
        checkStop = time.time()
        print("\n{} The time it took to stop the test and deal with the JSON and CSV files was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))
        
        #Analyze the pcap
        checkStart = time.time()
        for thisMAC in assigned_STA_MACs:
                logDict = {"palMAC": thisMAC["MAC"]}
                print("Placing {} into the log file for palMAC".format(thisMAC))
                sd2Utils.logToJSON(globalsfile.resultsPath, logDict)
                endpointTag = thisMAC["tag"]
                etc = {"endpointTag":endpointTag, "countRoams":countRoams, "roamSet":roamSet,"upOrDown":upOrDown}
                #roams,allFTtimes,appGap,EAPOL_groups,throughputs,roamReport = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,endpointTag,countRoams,roamSet)
                roams,allFTtimes,appGap,EAPOL_groups,throughputs,roamReport = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,etc)
                checkStop = time.time()
                print("\n{} The time it took to do createReport.main was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))
                
                if kafkaBrokerFound:
                        try:
                                my_producer.send('plotStream', value = roamReport)
                        except:
                                print("The Kafka broker doesn't seem to be responding.")
                                kafkaBrokerFound = False        
        
                roams["FTtimes"] = allFTtimes
                roams["appGap"] = appGap
                roams["EAPOL_groups"] = EAPOL_groups
                roams["throughputs"] = throughputs

                roamData["{}".format(countRoams)] = roams        
                logDict = {"roamData": roamData}
                #print("To roamData writing {}".format(logDict))
                sd2Utils.logToJSON(globalsfile.resultsPath, logDict)
                countRoams += 1

        checkStart = time.time()
        roamSummary = createReport.roamPlot(directory_name,globalsfile.outputDirPath,outlierLow,outlierHigh)
        checkStop = time.time()
        print("\n{} The time it took to run createReport.roamPlot was {:.3} seconds. {} \n".format(cRed,checkStop-checkStart,cNormal))

        if kafkaBrokerFound:
                try:
                        my_producer.send('plotStream', value = roamSummary)
                except:
                        print("The Kafka broker doesn't seem to be responding.")
                        kafkaBrokerFound = False
        

        if backAndForthRoaming:
                sd2Utils.startSniffers(snifStartDictList)
                time.sleep(3)

                roamSet += 1
                staQueries[roamSet] = {}
                sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})
                
                
                #Get the STA information from the STApals themselves.  Useful, maybe required, for MLO roaming analysis.  Do this just after PCAP is started.
                if not isRealSta:
                        for thePal in palsToUseSTA:
                                palName = thePal["name"]
                                if "staPal" in paramsDict[palName]["val"]["devType"]:
                                        ipAddress = paramsDict[palName]["val"]["address"]
                                        staQuery = querySTA.main(ipAddress)
                                        staQueries[roamSet][palName] = {"ipAddress":ipAddress,"staQuery":{"before":staQuery}}
                                        sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})
                        
                if palsAsAPs and doKick:
                        #Send commands to both Pals to remove the station mac address from its association table.
                        for palMgmtIP in palIPs:
                                curlExec = "curl http://"+palMgmtIP+":8383/exec?command="
                                command = "iwpriv ath0 kickmac " + macToKick
                                url = serverExec+curlExec+command
                                print("\n>>> For Pal {}, kicking {} off of ath0 with command {}".format(palMgmtIP,macToKick,url))
                                resp = requests.get(url=url, timeout=REST_TIMEOUT)
                                jsn = json.loads(resp.text)
                                print("Return result: {}".format(jsn))
                                command = "iwpriv ath1 kickmac " + macToKick
                                url = serverExec+curlExec+command
                                print("\n>>> For Pal {}, kicking {} off of ath1 with command {}".format(palMgmtIP,macToKick,url))
                                resp = requests.get(url=url, timeout=REST_TIMEOUT)
                                jsn = json.loads(resp.text)
                                print("Return result: {}".format(jsn))
                
                globalsfile.fileSuffix = '_ReverseRoam_{}'.format(roamSet)
                sd2Utils.startAutotest()
                time.sleep(5)

                if not isRealSta:
                        sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio)
                        if globalsfile.online:
                                startBSSID = globalsfile.palStatus["bssid"]
                                try: startBSSID = startBSSID.replace(".","").replace(":","")
                                except: startBSSID = boxBbssid.lower()
                
                #startBSSID = boxBbssid.lower()
                try: startBSSID = startBSSID.replace(".","").replace(":","").lower()
                except: startBSSID = startBSSID.lower()
                theBSSID = startBSSID.lower()
                newBSSID = None
                afterRoam = 0        
                for steps in range (roamLowSide,roamHighSide,2):
                        attenuation = max(0,disconnectPointB + steps)
                        #otherAttenuation = max(0,disconnectPointA - steps -10)
                        otherAttenuation = 0
                        sd2Utils.setAttenDirect(attenForBoxB, attenuation)
                        sd2Utils.setAttenDirect(attenForBoxA, otherAttenuation)
                        print("{} At attenuations {}: {}, and {}: {} {}".format(cRed,attenForBoxA,attenuation,attenForBoxB,otherAttenuation,cNormal))
                        if afterRoam > 0: afterRoam += 1
                        if not isRealSta:
                                maxTries = 2
                                tries = 0
                                while tries < maxTries:
                                        retObj = sd2Utils.getPalStatus(palToUseSTA,1,targetRadio=targetRadio,quitOnFail=False)
                                        tries += 1
                                        if "returnStatus" in retObj:
                                                if retObj["returnStatus"] == "failed":
                                                        print("getPalStatus failed with: {}".format(retObj["reason"]))
                                                if tries < maxTries:
                                                        staDictList = cyclePalAndTryAgain(palToUseSTA,stasAndConfigs,staDictList)
                                                else:
                                                        print("Failure of getPalStatus {} times, for reason:{}.  Allowing termination of the script.".format(tries,retObj["reason"]))
                                                        sys.exit(35)
                                if globalsfile.online:
                                        thisBSSID = globalsfile.palStatus["bssid"].lower()
                                        try: thisBSSID = thisBSSID.replace(".","").replace(":","").lower()
                                        except: thisBSSID = thisBSSID.lower()
                                        if thisBSSID != startBSSID and len(thisBSSID)>2 and afterRoam==0:
                                                newBSSID = thisBSSID.lower()
                                                print("You roamed! From {} to {}.  At {}={}dB, and {}={}dB.".format(startBSSID,newBSSID,attenForBoxA,attenuation,attenForBoxB,otherAttenuation))
                                                afterRoam = 1
                                        else:
                                                print("L4==========> Currently on BSSID:   {}".format(thisBSSID))
                                                time.sleep(secondsPerAttenuationStep)
                                else:
                                        print("Your current association status is {}".format(globalsfile.online))
                        else:
                                print("Your current association status is {}".format(globalsfile.online))
                                time.sleep(secondsPerAttenuationStep)

                        if afterRoam >= 4 and allowEarlyRampStop:
                                print("L1==========> Breaking due to afterRoam = {}, on BSSID = {}".format(afterRoam,thisBSSID))
                                break  #Let it continue ramping for a few steps after the roam happens.

                print("Stopping sniffers at L4")
                pcapFile = sd2Utils.stopSniffers()

                command = "cp {} /home/octoscope/Documents/analytics/pcapDirectory/".format(pcapFile);
                print("Move PCAP file with {}".format(command))
                os.system(command)
                #Get the STA information from the STApals themselves.  Useful, maybe required, for MLO roaming analysis.  Do this just after PCAP is saved.
                if not isRealSta:
                        for thePal in palsToUseSTA:
                                palName = thePal["name"]
                                if "staPal" in paramsDict[palName]["val"]["devType"]:
                                        ipAddress = paramsDict[palName]["val"]["address"]
                                        staQuery = querySTA.main(ipAddress)
                                        staQueries[roamSet][palName]["staQuery"]["after"] = staQuery
                                        sd2Utils.logToJSON(globalsfile.resultsPath, {"staQueries":staQueries})
                
                json_path = sd2Utils.stopAutotest(unzip=False,saveCSV=False,saveTaJSON=False)
                print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))
                #Get rid of the CSV zip file.
                theCSV = json_path.replace(".zip","_CSV.zip")
                command = "rm " + theCSV
                print("Removing the CSV zip file using this command: {}".format(command))
                os.system(command)        
                #Lock STA to current location so that it doesn't randomly roam back.
                sd2Utils.setAttenDirect(attenForBoxA,00)
                sd2Utils.setAttenDirect(attenForBoxB,90)

                testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
                print()
                print('#########################################')
                print('>>> Getting test results')
                print('#########################################')

                for thisMAC in assigned_STA_MACs:
                        logDict = {"palMAC": thisMAC["MAC"]}
                        print("Placing {} into the log file for palMAC".format(thisMAC))
                        sd2Utils.logToJSON(globalsfile.resultsPath, logDict)
                        endpointTag = thisMAC["tag"]
                        etc = {"endpointTag":endpointTag, "countRoams":countRoams, "roamSet":roamSet,"upOrDown":upOrDown} 
                        #roams,allFTtimes,appGap,EAPOL_groups,throughputs,roamReport = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,endpointTag,countRoams,roamSet)
                        roams,allFTtimes,appGap,EAPOL_groups,throughputs,roamReport = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,etc)
                        testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
                        roams["FTtimes"] = allFTtimes
                        roams["appGap"] = appGap
                        roams["EAPOL_groups"] = EAPOL_groups
                        roams["throughputs"] = throughputs

                        if kafkaBrokerFound:
                                try:
                                        my_producer.send('plotStream', value = roamReport)
                                except:
                                        print("The Kafka broker doesn't seem to be responding.")
                                        kafkaBrokerFound = False                

                        roamData["{}".format(countRoams)] = roams
                        logDict = {"roamData": roamData}
                        #print("To roamData writing {}".format(logDict))
                        sd2Utils.logToJSON(globalsfile.resultsPath, logDict)        
                        countRoams += 1
        
        thisEndTime = time.time()
        print("\n\n The total time it took to do additional run {} was {} seconds.\n\n".format(AR,thisEndTime-thisStartTime))

#Shouldn't be needed if you had any additional runs, but this is not too long so just do it again.
roamSummary = createReport.roamPlot(directory_name,globalsfile.outputDirPath,outlierLow,outlierHigh)

if kafkaBrokerFound:
        try:
                my_producer.send('plotStream', value = roamSummary)
        except:
                print("The Kafka broker doesn't seem to be responding.")
                kafkaBrokerFound = False
        
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
