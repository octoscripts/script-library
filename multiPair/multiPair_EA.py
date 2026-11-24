"""
Test description
Run traffic using multiple Pal endpoints. Supports triband and bidirectional modes. Can use real AP or Pal6A as AP.
"""
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime
import shutil

import pprint
pp = pprint.PrettyPrinter(indent=4)

import zipfile
from zipfile import ZipFile 

############### END SECTION: IMPORTS #########################s

#Get the location of the results directory, as far as script-manager is concerned
response = requests.get("http://localhost:5678/getResultsDirectory")
theJson = response.json()
resultsDirectory = theJson["resultsDirectory"]
    
print("[INFO]: The results directory is {}.".format(resultsDirectory))

############### START SECTION: BUILD DICTIONARY #########################

# Find working directory
try:
    directory_name=sys.argv[1]
    print("[INFO]: >>> The directory name passed in is {}".format(directory_name),flush=True)
except:
    directory_name = "./"
    #directory_name = os.getcwd()
    print('[INFO]: >>> No directory_name provided, so using {}'.format(directory_name),flush=True)

    
print("[INFO]: The local directory is here: " + directory_name)

# This line makes sure script can run from command line without SM
if directory_name[len(directory_name)-1] != "/": directory_name += "/"

sys.path.append(directory_name + '..')

import globalsfile	# MUST HAVE to be able to reference global variables stored in globalsfile.py
import sd2Utils		# MUST HAVE. Contains functions used in this script and other helpful functions

from stardust_socket_listen import StardustSocketListen # MUST HAVE if you are going to use any real time stats

# Reference params and base auto test dictionaries 
paramsDict = globalsfile.paramsDict

REST_TIMEOUT = paramsDict['rest_timeout']['val'] # Used by REST API calls
print('\n>>> REST_TIMEOUT: ' + str(REST_TIMEOUT))

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
palAsAPdrop = paramsDict["palAsAP"]["val"]
for item in palAsAPdrop:
	if item["selected"]:
		palAsAP = item["value"]
		break

pal6APbandConfig = paramsDict['pal6APbandConfig']['val']

(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]
attenToUse = attenToUseA	# For createReport

print(">>> There are {} quadAttens defined.".format(len(attenList)))

palStations = paramsDict["palStations"]["val"]
palsToUse = []
for pal in palStations: palsToUse.append(pal["name"])
if 'Pal' in palAsAP:
	palsToUse.append(palAsAP)

testUses=paramsDict['testUses']['val']+palsToUse+attenList
print(">>> testUses: {}".format(testUses))
# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)

############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

# Find where Expert Analysis is running for report generation
ea_root = sd2Utils.whereIsEA()

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

print('\n>>> Adding test information to testresults.json')
resultDict = {"testInfo": testInfoDict}
resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp })
resultDict['testInfo'].update({"scriptSuiteVersion":globalsfile.scriptSuiteVersion})
resultDict['testInfo'].update({"starDustVersion":globalsfile.starDustVersion})
resultDict['testInfo'].update({"palFWversions":globalsfile.palFWdict})
resultDict['testInfo'].update({"palAsAP":palAsAP,"pal6APbandConfig":pal6APbandConfig})
if test_param_alt_file:
	resultDict['testInfo'].update({"testParamAltFile":test_param_alt_file})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

time.sleep(5)

sd2Utils.isolateAllBoxes()

#Setting attenuation values for attenuators or MPEs:
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=True)

if 'Pal' in palAsAP:
	# Set up Pal-6A as AP
	apDictList = []
	print('')
	print('##############################################################')
	print("########## Setting up %s as AP." % palAsAP)
	print('##############################################################')

	ssid     = paramsDict["pal6APssid"]["val"]
	security = paramsDict["pal6APsecurity"]["val"]
	password = paramsDict["pal6APpass"]["val"]

	# 2.4 GHz radio
	if paramsDict['pal6APchannel_24g']['val'] > 0:
		apDictList = sd2Utils.setupAP(palAsAP, '24g', apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel_24g']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_40_ADAPT", "ssid":ssid, "password": password, "security":security})
		resultDict['testInfo'].update({"2.4GHzChannelToTest":paramsDict['pal6APchannel_24g']['val']})

	# 5 GHz radio (dual-band)
	if pal6APbandConfig == 'BAND_DUAL':
		if paramsDict['pal6APchannel_5g']['val'] > 0:
			apDictList = sd2Utils.setupAP(palAsAP, '5g', apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel_5g']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT", "ssid":ssid, "password": password, "security":security})
			resultDict['testInfo'].update({"5GHzChannelToTest":paramsDict['pal6APchannel_5g']['val']})
		else:
			funcName = 'MainScript'
			message = "Dual band (5g) mode set but channel=0. Set paramsDict['pal6APchannel_5g']['val'] > 0."
			sd2Utils.failHandler(funcName,message)

	# 5 GHz A radio (tri-band)
	if pal6APbandConfig == 'BAND_TRI':
		if paramsDict['pal6APchannel_5Ag']['val'] > 0:
			apDictList = sd2Utils.setupAP(palAsAP, "5Ag", apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel_5Ag']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT", "ssid":ssid, "password": password, "security":security})
			resultDict['testInfo'].update({"5GHzAChannelToTest":paramsDict['pal6APchannel_5Ag']['val']})
		else:
			funcName = 'MainScript'
			message = "Tri band (5g) mode set but 5Ag channel=0. Set paramsDict['pal6APchannel_5Ag']['val'] > 0."
			sd2Utils.failHandler(funcName,message)

	# 5 GHz B radio (tri-band)
	if pal6APbandConfig == 'BAND_TRI':
		if paramsDict['pal6APchannel_5Bg']['val'] > 0:
			apDictList = sd2Utils.setupAP(palAsAP, "5Bg", apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel_5Bg']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT", "ssid":ssid, "password": password, "security":security})
			resultDict['testInfo'].update({"5GHzBChannelToTest":paramsDict['pal6APchannel_5Bg']['val']})
		else:
			funcName = 'MainScript'
			message = "Tri band (5g) mode set but 5Bg channel=0. Set paramsDict['pal6APchannel_5Bg']['val'] > 0."
			sd2Utils.failHandler(funcName,message)

	if paramsDict[palAsAP]['val']['isPal6E']:
		# 6 GHz radio
		if paramsDict['pal6APchannel6g']['val'] > 0:
			apDictList =sd2Utils.setupAP(palAsAP, "6g", apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel6g']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_160_ADAPT",  "ssid":ssid, "password": password, "security":security})
			#primaryChannel = paramsDict['pal6APchannel6g']['val']
			resultDict['testInfo'].update({"6GHzChannelToTest":paramsDict['pal6APchannel6g']['val']})

	pp.pprint(apDictList)
	#sys.exit()

	sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)	
	sd2Utils.updateAutotestInst(apDictList, 'pal6s', pushConfig=True) # update config and push
	print('')
	print('##############################################################')
	print("########## Setting up %s as AP. DONE." % palAsAP)
	print('##############################################################')

#Setting up traffic pairs:
tpDictList = []

trafficType = paramsDict["trafficType"]["val"]
trafficModeDrop = paramsDict["trafficMode"]["val"]
for item in trafficModeDrop:
    if item["selected"]:
        packetType = item["value"]
        break
pingInterval = paramsDict["pingInterval"]["val"]
upOrDowndrop = paramsDict["upOrDown"]["val"]
for item in upOrDowndrop:
    if item["selected"]:
        upOrDown = item["value"]
        break
if "u" in upOrDown: updn = "up"
if "d" in upOrDown: updn = "dn"
trafficBW = paramsDict["trafficBW"]["val"]
length = paramsDict["length"]["val"]
parallel = paramsDict["parallel"]["val"]
window = paramsDict["window"]["val"]
trafficAdvanced = paramsDict["trafficAdvanced"]["val"]
useNagles = paramsDict["useNagles"]["val"]
setMss = paramsDict["setMss"]["val"]
dscp = paramsDict["dscp"]["val"]
isochronous = paramsDict["isochronous"]["val"]
iso_gap = paramsDict["iso_gap"]["val"]
iso_mean = paramsDict["iso_mean"]["val"]
iso_mean_units_drop = paramsDict["iso_mean_units"]["val"]
for item in iso_mean_units_drop:
    if item["selected"]:
        iso_mean_units = item["value"]
        break
iso_mean = str(iso_mean) + iso_mean_units
iso_stdev = paramsDict["iso_stdev"]["val"]
iso_fps = paramsDict["iso_fps"]["val"]
    
trafficPairs = paramsDict["trafficPairs"]["val"]
i = 0
for pair in trafficPairs:
    i += 1
    doPush = False
    if i==len(trafficPairs): doPush = True
    if "2" in pair["band"]: theBand = "24g"
    if "5g" in pair["band"]: theBand = "5g"
    if "5Ag" in pair["band"]: theBand = "5Ag"
    if "5Bg" in pair["band"]: theBand = "5Bg"
    if "6" in pair["band"]: theBand = "6g"
    if "u" in pair["updn"]: updn = "up"
    if "d" in pair["updn"]: updn = "dn"
    tpDictOverride = {}
    tpDictOverride["trafficType"] = trafficType
    if "trafficType" in pair: tpDictOverride["trafficType"] = pair["trafficType"]
    tpDictOverride["udp"] = packetType
    if "packetType"  in pair: tpDictOverride["udp"]         = pair["packetType"]
    tpDictOverride["bitrate"] = trafficBW
    if "trafficRate" in pair: tpDictOverride["bitrate"]     = pair["trafficRate"]
    tpDictOverride["length"] = length
    if "packetSize"  in pair: tpDictOverride["length"]      = pair["packetSize"]
    tpDictOverride["ipStreams"] = parallel
    if "trafficStreams"  in pair: tpDictOverride["ipStreams"]= pair["trafficStreams"]
    tpDictOverride["window"] = window
    if "windowSize"  in pair: tpDictOverride["window"]      = pair["windowSize"]
    tpDictOverride["interval"] = pingInterval
    if "pingInterval" in pair: tpDictOverride["interval"]   = pair["pingInterval"]
    tpDictOverride["advanced"] = trafficAdvanced
    if "advanced"    in pair: tpDictOverride["advanced"]    = pair["advanced"]
    if tpDictOverride["advanced"]:
        tpDictOverride["isochronous"] = isochronous
        if "isochronous" in pair: tpDictOverride["isochronous"] = pair["isochronous"]
        tpDictOverride["dscp"] = dscp
        if "dscp"        in pair: tpDictOverride["dscp"]        = pair["dscp"]
        tpDictOverride["ipg"] = iso_gap
        if "iso_gap"     in pair: tpDictOverride["ipg"]         = pair["iso_gap"]
        tpDictOverride["mean"] = iso_mean
        if "iso_mean"    in pair: tpDictOverride["mean"]        = pair["iso_mean"]
        tpDictOverride["stdev"] = iso_stdev
        if "iso_stdev"   in pair: tpDictOverride["stdev"]       = pair["iso_stdev"]
        tpDictOverride["fps"] = iso_fps
        if "iso_fps"     in pair: tpDictOverride["fps"]         = pair["iso_fps"]
        
    tpDictList = sd2Utils.setupTrafficPairs(pair["whichPal"], theBand, updn, tpDictList, tpDictOverride=tpDictOverride, pushConfig=doPush)


#Setting up Pal configurations:
staDictList = []
palStations = paramsDict["palStations"]["val"]
i = 0
for pal in palStations:
	i += 1
	doPush = False
	if i == len(palStations): doPush = True
	if 'Pal' in palAsAP:
		ssid     = paramsDict["pal6APssid"]["val"]
		security = paramsDict["pal6APsecurity"]["val"]
		password = paramsDict["pal6APpass"]["val"]
		if "2" in pal["band"]:
			theBand = "24g"
		elif pal["band"] == '5g':
			theBand = "5g"
		elif pal["band"] == '5Ag':
			theBand = "5Ag"
		elif pal["band"] == '5Bg':
			theBand = "5Bg"
		elif "6" in pal["band"]:
			theBand = "6g"
	else:
		if "2" in pal["band"]:
			theBand = "24g"
			ssid     = paramsDict["dut"]["val"]["dutssid24"]
			security = paramsDict["dut"]["val"]["dutsecurity24"]
			password = paramsDict["dut"]["val"]["dutpass24"]
		elif pal["band"] == '5g':
			theBand = "5g"
			ssid     = paramsDict["dut"]["val"]["dutssid5"]
			security = paramsDict["dut"]["val"]["dutsecurity5"]
			password = paramsDict["dut"]["val"]["dutpass5"]
		elif pal["band"] == '5Ag':
			theBand = "5Ag"
			ssid     = paramsDict["dut"]["val"]["dutssid5"]
			security = paramsDict["dut"]["val"]["dutsecurity5"]
			password = paramsDict["dut"]["val"]["dutpass5"]
		elif pal["band"] == '5Bg':
			theBand = "5Bg"
			ssid     = paramsDict["dut"]["val"]["dutssid5"]
			security = paramsDict["dut"]["val"]["dutsecurity5"]
			password = paramsDict["dut"]["val"]["dutpass5"]
		elif "6" in pal["band"]:
			theBand = "6g"
			ssid     = paramsDict["dut"]["val"]["dutssid6"]
			security = paramsDict["dut"]["val"]["dutsecurity6"]
			password = paramsDict["dut"]["val"]["dutpass6"]
	staoverride={"ssid":ssid, "password": password, "security": security }
	if "type"    in pal: staoverride["interface_"] = pal["type"]
	if "channel" in pal: staoverride["primaryChannel"] = pal["channel"]
	if "bandConfig" in pal: staoverride["bandConfig"] = pal["bandConfig"]
	if "streams" in pal: staoverride["streams"] = pal["streams"]
	if "ssid"    in pal: staoverride["ssid"] = pal["ssid"]
	if "security" in pal: staoverride["security"] = pal["security"]
	if "password" in pal: staoverride["password"] = pal["password"]
	if "bandwidth" in pal:
		useBandwidth = "BANDWIDTH_ADAPT"
		if "20" in pal["bandwidth"]: useBandwidth = "BANDWIDTH_20_FIXED"
		if "40" in pal["bandwidth"]: useBandwidth = "BANDWIDTH_40_ADAPT"
		if "80" in pal["bandwidth"]: useBandwidth = "BANDWIDTH_80_ADAPT"
		if "160" in pal["bandwidth"]: useBandwidth = "BANDWIDTH_160_ADAPT"
		if "24" in theBand and ("80" in pal["bandwidth"] or "160" in pal["bandwidth"]):
			print('')
			print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
			print('########## WARNING! %s bandwidth mode not supported in %s band.') 
			print('########## WARNING! Setting bandwidth mode to BANDWIDTH_40_ADAPT.')	
			print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
			useBandwidth = "BANDWIDTH_40_ADAPT"
		staoverride["bandwidth"] = useBandwidth
	print('### staoverride:')
	pp.pprint(staoverride)
	# Setting extra long timeoutOverride. Pushing config to Pal with "bandConfig":"BAND_TRI" takes a LONG time
	staDictList = sd2Utils.setupSTA(pal["name"], theBand, staDictList, staDictOverride=staoverride, timeoutOverride= 120, pushConfig=doPush)
	pal["targetRadio"] = staDictList[i-1]['palRadio']

resultDict['testInfo'].update({"palStations":palStations, "trafficPairs":paramsDict["trafficPairs"]["val"]})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

for pal in palStations:
    sd2Utils.waitForAssociation(pal["name"],pal["targetRadio"],timeToWait=45)

#print('>>> EXIT at LINE 418. Check associations.')
#sys.exit()
############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

jsonZipPath = sd2Utils.runAutotest(sleepTime=2,skipTimeoutCheck=True)

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED #########################
testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
resultDict = {}
resultDict = {'testRunTime':testRunTime}
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)


import createReport_EA
print('')
print('##############################################################')
print("########## Creating report ")
print('##############################################################')	
createReport_EA.main(directory_name,globalsfile.outputDirPath,ea_root)

print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
