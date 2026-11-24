'''
Test Description
================
RvR test that can be run in any supported mode, i.e. RvR, RvRwR, RvOvR and RvRvO.
Uses linear attenuation ramp.
DUT must be in Box A.
'''

############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime

import pprint
pp = pprint.PrettyPrinter(indent=4)

import zipfile
from zipfile import ZipFile 

############### END SECTION: IMPORTS #########################

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

#Get the location of the results directory, as far as script-manager is concerned
response = requests.get("http://"+globalsfile.hostIpAddress+":5678/getResultsDirectory")
theJson = response.json()
resultsDirectory = theJson["resultsDirectory"]
print("The results directory is {}.".format(resultsDirectory))

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


############################
# Set up some text coloring
cRed=   '\033[m'
cGreen= '\033[m'
cNormal='\033[m'

############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

rvrModedrop = paramsDict["rvrMode"]["val"]
for item in rvrModedrop:
    if item["selected"]:
        rvrMode = item["value"]
        break

palToUsedrop = paramsDict["palToUse"]["val"]
for item in palToUsedrop:
    if item["selected"]:
        palToUse = item["value"]
        break

STAisPal = True
if "iperf" in palToUse: STAisPal = False

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

# Build list for config check
instList = []
if STAisPal:
    instList.append(palToUse)

(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]
instList = instList+attenList

if rvrMode != 'RvR':
	if 'TT-A' in paramsDict.keys():
		instList.append(paramsDict["TT-A"]["val"]["alias"])
	else:
		message = "System does not have a Turntable, but rvrMode "+rvrMode+" requires it.  Set params_test['rvrMode']['val'] == 'RvR'."
		sd2Utils.failHandler('MainScript',message)	


# Check that system can support the test
sd2Utils.checkSystemConfig(instList)

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

print(">>> Pulling in data from the test parameters file.")
                  
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
    
primaryChannel = paramsDict["primaryChannel"]["val"]

bwdrop = paramsDict["bw"]["val"]
for item in bwdrop:
    if item["selected"]:
        bandwidth = item["value"]
        break

if "24" in band and ("80" in bandwidth or "160" in bandwidth):
	print('')
	print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
	print('##### WARNING! %s bandwidth mode not supported in %s band.') 
	print('##### WARNING! Setting bandwidth mode to BANDWIDTH_40_ADAPT.')	
	print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
	bandwidth = "BANDWIDTH_40_ADAPT"

ifacedrop = paramsDict["iface"]["val"]
for item in ifacedrop:
    if item["selected"]:
        interface = item["value"]
        break

nssdrop = paramsDict["nss"]["val"]
for item in nssdrop:
    if item["selected"]:
        streams = item["value"]
        break

if "STA" in palToUse and streams > 3:
	print('')
	print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
	print('##### WARNING! STApal does not support %s streams. Setting streams = 2' % streams)	
	print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
	streams = 2

trafficdrop = paramsDict["trafficMode"]["val"]
for item in trafficdrop:
    if item["selected"]:
        trafficMode = item["value"]
        break

upOrDowndrop = paramsDict["upOrDown"]["val"]
for item in upOrDowndrop:
    if item["selected"]:
        upOrDown = item["value"]
        break

trafficAdvanced = paramsDict["trafficAdvanced"]["val"]
useNagles = paramsDict["useNagles"]["val"]
dscp = paramsDict["dscp"]["val"]
setMss = paramsDict["setMss"]["val"]
try: setMss = int(setMss)
except: setMss = None
if setMss == 0: setMss = None

print("{} >>> Pulling in data from the test parameters file. DONE. {}".format(cGreen,cNormal))

print('\n>>> Adding test information to testresults.json')
resultDict = {"testInfo": testInfoDict}
resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp, "security":security, "band":band, "primaryChannel":primaryChannel, "bandwidth":bandwidth, "interface":interface, "streams":streams, "trafficMode":trafficMode, "upOrDown": upOrDown })
resultDict['testInfo'].update({"scriptSuiteVersion":globalsfile.scriptSuiteVersion})
resultDict['testInfo'].update({"starDustVersion":globalsfile.starDustVersion})
resultDict['testInfo'].update({"palFWversions":globalsfile.palFWdict})
if test_param_alt_file:
	resultDict['testInfo'].update({"testParamAltFile":test_param_alt_file})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
#pp.pprint(resultDict)
#print('>>>> QUIT 260 ')
#sys.exit()

############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

 
############### START SECTION: BUILD THE TEST OBJECT #########################
print(">>> Creating the complete test object.")

print('')	
print('##############################################################')
print("##### RvR mode: %s ##########" % rvrMode)
print('##############################################################')	

if rvrMode == 'RvRwR' and paramsDict["stepDuration"]["val"] < 30:
	message = "Step duration "+str(params_test['stepDuration']['val'])+" is too short.  Set params_test['stepDuration']['val'] to at least 30."
	sd2Utils.failHandler('MainScript',message)	

if rvrMode != 'RvR':
	print ('\n>>> Adding turntable rotation to test.')
	turntable = {
		"active": True,
		"address": paramsDict["TT-A"]["val"]["address"],
		"alias": paramsDict["TT-A"]["val"]["alias"],
		"devType": "turntable",
		"start": int(paramsDict["ttStart"]["val"]),
		"step": int(paramsDict["ttStep"]["val"]),
		"stop": int(paramsDict["ttStop"]["val"]),
		"trainingInterval": int(paramsDict["ttTraining"]["val"]),
		"velocity": int(paramsDict["ttVelocity"]["val"])    
	}

	tmpdict ={}
	tmpdict.update({'turntables':[turntable]})
	tmpdict.update({'rvrMode':rvrMode})

	sd2Utils.updateAutotest(tmpdict, pushConfig=True)
	print ('>>> Adding turntable rotation to test DONE.')
else:
	print ('>>> No turntable required for test. Setting RvR mode to "RvR"')
	tmpdict={'rvrMode':'RvR'}
	sd2Utils.updateAutotest(tmpdict, pushConfig=True)

#print('EXIT LINE 293')
#sys.exit()

sd2Utils.isolateAllBoxes()

print('')
print('##############################################################')
print("##### Setting up Attenuators START ")
print('##############################################################')
# Figure out whether to use Box E or Box C attens to connect to Box A
if 'C' in palToUse:
	(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
	sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63)
	sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63)
	attenToUse = attenToUseA	# For createReport and avgData calls
else:
	attenToUse =sd2Utils.whichVatten('boxa')
	sd2Utils.setVatten(attenToUse, paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"])
print('')
print('##############################################################')
print("##### Setting up Attenuators DONE ")
print('##############################################################')
print('')


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
    apDictList = []
    apDictList = sd2Utils.setupAP(palToUseAsAP, band, apDictList, type = interface, channel=palToUseAsAPChannel, pushConfig=False, apDictOverride=apDictOverride)


print('##############################################################')
print("##### Setting up Traffic pairs START ")
print('##############################################################')

debuggingWithL3C = False

tpDictList = []
override = {}
override = {"advanced":trafficAdvanced, "naglesAlgo":useNagles, "dscp":dscp}
if setMss: override["setMss"] = setMss
override["advanced"] = paramsDict["trafficAdvanced"]["val"]
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

if STAisPal:
    tpDictList = sd2Utils.setupTrafficPairs(palToUse, band, upOrDown, tpDictList, tMode=trafficMode, tpDictOverride=override)
if debuggingWithL3C:
    tpDictList = sd2Utils.setupTrafficPairs("L3C-STApal", band, upOrDown, tpDictList, tMode=trafficMode, tpDictOverride=override)
    shadowPair = 0
    
print('')
print('##############################################################')
print("##### Setting up Traffic pairs DONE ")
print('##############################################################')

print('')
print('##############################################################')
print("##### Set up and associate STA ")
print('##############################################################')
overrideDict = {
    "bandwidth": bandwidth,
    "interface_": interface,
	"ssid": ssid,
	"password": password,
	"security":security
}

if STAisPal:
    staPalDictList = []
    staPalDictList = sd2Utils.setupSTA(palToUse,band, staPalDictList, streams=streams, channel=primaryChannel,staDictOverride=overrideDict, pushConfig=True)
    #print('>>> staPalDictList: ' )
    #pp.pprint(staPalDictList)
    palRadio = staPalDictList[0]['palRadio']
    palAlias = staPalDictList[0]['alias']
			
    print('')
    print('##############################################################')
    print("##### Setting up STAs DONE ")
    print('##############################################################')

if debuggingWithL3C:
    staPalDictList = []
    staPalDictList = sd2Utils.setupSTA("L3C-STApal",band, staPalDictList, streams=streams, channel=primaryChannel,staDictOverride=overrideDict, pushConfig=True)

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
        "devType": palToUse + "Endpoint",
        "radio": "",
        "iperfPort": customPort,
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
    updateDict = {
        "to": toSide,
        "from": fromSide,
        "settlingTime": paramsDict['settlingTime']['val'],
        "active": True,
        "alias": pairalias,
        "bitrate": paramsDict['trafficBW']['val'],
        "interval": override["interval"],
        "trafficType": paramsDict['trafficType']['val'],
        "udp": trafficMode,
        "ipVersion": "ipv4",
        "ipStreams": paramsDict['parallel']['val'],
        "window": paramsDict['window']['val'],
        "length": paramsDict['length']['val'],
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

if debuggingWithL3C:
    tpDictList[shadowPair]['active'] = False
    updateDict = {"alias":tpDictList[shadowPair]['alias'] , "active": False}
    sd2Utils.updateTrafficPair(updateDict)

    

############### END SECTION: BUILD THE TEST OBJECT #########################

if STAisPal:
    ############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################
    print('')
    print('##############################################################')
    print("##### Associating STAs ")
    print('##############################################################')
    associatedStatus = False
    assocWaitTime = 30
    #print('>>> band: ', band)
    if band: # Make sure not None
            if '6' in band:
                    assocWaitTime = 40	# 6 GHz takes longer to associate

    associatedStatus = sd2Utils.waitForAssociation(palToUse,palRadio,timeToWait=assocWaitTime)
    if not associatedStatus:
            print(">>> runRvR: Association not completed. Quitting.")
            sys.exit(1) # Set for SM

    print('')
    print('##############################################################')
    print("##### runRvR: Associating STAs DONE ")
    print('##############################################################')
    print('')
    #print('EXIT LINE 379')
    #sys.exit()
    ############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################
                    
############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

print (">>> Starting Autotest...")
Timestamp = sd2Utils.getTimestamp()

with open(directory_name + 'directories.json') as f:
    directories = json.load(f)
newpath = directory_name + "../../results/" + directories["topDirectory"] + "/" + directories["subDirectory"]
print(">>> The path to the test results is {}".format(newpath))

if not os.path.exists(newpath):
    os.makedirs(newpath)

json_path = sd2Utils.runAutotest(skipTimeoutCheck=True)

print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')
bandDir = band+'_'+upOrDown
resultDict = {bandDir:{}}

useThisTP = None
for tp in tpDictList:
    if tp['active']:
        useThisTP = tp
        break

print('Using traffic pair {}'.format(useThisTP['alias']))
filter ={"want": "avg"}
type = 'THROUGHPUT'
result = sd2Utils.avgDataPost(type,filter,useThisTP,multival=True,attenName=attenToUse)
if result:
	resultDict[bandDir].update({filter['want']:result})
	print('#########################################')
	print('>>> resultDict ', (resultDict))	
	print('#########################################')
	sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
else:
	message = "Results for "+type+", "+filter['want']+" not found."
	failHandler('MainScript',message, errCode=0)

if STAisPal:
    filter ={"want": "rssiMgmtMean"}
    type = 'PALSTATS'
    result = sd2Utils.avgDataPost(type,filter,useThisTP,multival=True,attenName=attenToUse)
    if result:
            resultDict[bandDir].update({filter['want']:result})
            print('#########################################')
            print('>>> resultDict ', (resultDict))
            print('#########################################')
            sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
    else:
            message = "Results for "+type+", "+filter['want']+" not found."
            failHandler('MainScript',message, errCode=0)

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

########### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###################

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
resultDict = {}
resultDict = {'testRunTime':testRunTime}
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

#########Generating JSON reports

#Remove existing test report so that if there is a problem here, you don't get fooled into thinking that an old report is the new report.
try:
	rmResult = os.system("rm " + directory_name + "TestReport.json")
	print(">>> Removed all old TestReport.json: {}".format(rmResult))
except:
	print(">>> No TestReport.json found. No file removed.")

print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))

#Place a PDF export in the same location
pdf_dict = {
"showAll": False,
"plotList": []
}
URL = "http://" + "{}:4000".format(paramsDict["oBox_server"]["val"]["publicip"]) + "/api/v1/reports/pdf/{}".format(testName)
pdf_report = requests.post(URL,json=pdf_dict,timeout=REST_TIMEOUT)
pdf_path = json_path.replace(".zip",".pdf")
with open(pdf_path, 'wb') as f:
	for chunk in pdf_report.iter_content(chunk_size=1024):
		if chunk:
			f.write(chunk)
print("\n>>> {} PDF file at: {} {}".format(cGreen,pdf_path,cNormal))

if paramsDict['runCreateReport']['val']:
	print('')
	print('##############################################################')
	print("##### Creating HTML report ")
	print('##############################################################')	
	import createReport
	if 'C' in palToUse:
		attenToUse = attenToUseA
	ea_root = sd2Utils.whereIsEA()
	print(">>> Expert Analysis is at {}".format(ea_root))
	createReport.main(directory_name,globalsfile.outputDirPath,attenToUse,STAisPal,ea_root=ea_root)
    
print('')
print('##############################################################')
print("##### %s TEST DONE " % testName)
print('##### Test run time: %s.' % testRunTime)
print('##############################################################')
