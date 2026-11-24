'''
Test Description
================
Simple test to set up one traffic pair and one sniffer and run traffic while doing packet capture.\n Illustrates all the basic functions of setting up results file folder and names, setting attenuators, settting up traffic pairs, setting up and associating STA and setting up, starting and stopping sniffing.
NOTE! This test requires an AP in Box A.
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

haveCreateReport = False
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
	haveCreateReport = True
	import createReport

# Find where Expert Analysis is running for report generation
ea_root = sd2Utils.whereIsEA()        

# Build list for config check
attensToUse = paramsDict["attensToUse"]["val"]
attenList = attensToUse

thisDrop = paramsDict["palToUse"]["val"]
for item in thisDrop:
    if item["selected"]:
        palToUse = item["value"]
        break

print("Pal to use: {}".format(palToUse))

STAisPal = True
if "iperf2" in palToUse or "iperf3" in palToUse:
    STAisPal = False
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


testUses=paramsDict['testUses']['val']+attenList
if STAisPal: testUses += [palToUse]
print(">>> testUses: ", testUses)
# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)

############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

#Based on the settings, create a set of tests to run.
testsToRun = []
packetSizes = paramsDict["packetSizes"]["val"]
doUplink = paramsDict["doUplink"]["val"]
doDownlink = paramsDict["doDownlink"]["val"]
loadingLevels = paramsDict["loadingLevels"]["val"]
interfaces = ["11n","11ac","11ax"]
for interface in interfaces:
    switch = "do{}".format(interface)
    switch = paramsDict[switch]["val"]
    print("Interface {}? {}".format(interface,switch))
    if switch:
        Settings = paramsDict["Settings{}".format(interface)]["val"]
        sd2Utils.logToJSON(globalsfile.resultsPath, {interface:Settings})
        for band in Settings:
            thisTest = {"interface":interface,"band":band,"channel":Settings[band]["channel"]}
            for BW in Settings[band]["BWs"]:
                thisTest["BW"] = BW
                api_endpoint = "http://localhost:8080/getMCS"
                standard = interface
                RSSI = "0"
                BW = BW
                streams = Settings[band]["streams"]
                thisTest["streams"] = streams
                api_endpoint += "?" + "standard=" + standard
                api_endpoint += "&" + "RSSI=" + RSSI
                api_endpoint += "&" + "BW=" + str(BW)
                api_endpoint += "&" + "streams=" + str(streams)
                r = requests.get(url=api_endpoint)
                y = eval(r.text)
                status = y["status"]
                MCS    = y["MCS"]
                #print("Returned with status {}".format(status))
                #print("MCS found is {}".format(MCS))
                thisTest["theory"] = {"mcs":MCS}
                api_endpoint = "http://localhost:8080/getDRate"
                GI = "400"
                if "ax" in standard: GI = "800"
                api_endpoint += "?" + "standard=" + standard
                api_endpoint += "&" + "MCS=" + str(MCS)
                api_endpoint += "&" + "BW=" + str(BW)
                api_endpoint += "&" + "streams=" + str(streams)
                api_endpoint += "&" + "GI=" + GI
                r = requests.get(url=api_endpoint)
                y = eval(r.text)
                status = y["status"]
                rate    = y["rate"]
                #print("Returned with status {}".format(status))
                #print("Rate found is {}".format(rate))
                thisTest["theory"]["rate"] = rate
                for packetSize in packetSizes:
                    thisTest["packetSize"] = packetSize
                    if doUplink:
                        thisTest["direction"] = "up"
                        for level in loadingLevels:
                            thisTest["load"] = level
                            thisTest["offer"] = int(float(level)/100*float(thisTest["theory"]["rate"]))
                            testsToRun.append(thisTest.copy())
                    if doDownlink:
                        thisTest["direction"] = "dn"
                        for level in loadingLevels:
                            thisTest["load"] = level
                            thisTest["offer"] = int(float(level)/100*float(thisTest["theory"]["rate"]))
                            testsToRun.append(thisTest.copy())
#for test in testsToRun:print(test)
print("Total number of tests to run = {}".format(len(testsToRun)))

sd2Utils.logToJSON(globalsfile.resultsPath, {"doUplink":doUplink})
sd2Utils.logToJSON(globalsfile.resultsPath, {"doDownlink":doDownlink})
sd2Utils.logToJSON(globalsfile.resultsPath, {"loadingLevels":loadingLevels})
sd2Utils.logToJSON(globalsfile.resultsPath, {"packetSizes":packetSizes})

iperfMode = paramsDict["iperfMode"]["val"]
if iperfMode!='tcp' and iperfMode!='udp':
    print(">>> {} is not a valid iperf mode.".format(iperfMode))
    iperfMode = None

#Get the blank test
emptyTest = json.dumps(globalsfile.autotest_dict)
print(emptyTest)

currentInterface = None
currentBW = None

loggedResults = []
count = 0
for thisTest in testsToRun:

    count += 1
    print("Running this test:  {}, which is {} of {}\n\n".format(thisTest,count,len(testsToRun)))
    thisName = "{}_{}_{}_{}__{}_{}_{}_{}".format(thisTest["interface"],thisTest["band"],thisTest["channel"],thisTest["BW"],thisTest["streams"],thisTest["packetSize"],thisTest["direction"],thisTest["offer"])

    newInterface = thisTest["interface"]
    newBW = thisTest["BW"]
    settingsChange = False
    if (newInterface != currentInterface) or (newBW != currentBW): settingsChange = True
    
    theChannel = thisTest["channel"]    
    theBand = thisTest["band"]
    theStreams = thisTest["streams"]
    currentInterface = newInterface
    currentBW = newBW

    if settingsChange:
        print("Settings have changed.  Going to reset the whole test configuration.")
        # Reset the autotest_dict.
        globalsfile.autotest_dict = json.loads(emptyTest)
        print("HERE IS THE EMPTY TEST CONFIG")
        print(globalsfile.autotest_dict)
        autotest_dict = sd2Utils.initializeAutotest()

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

        # ssid, security and password may be taken from params_system['dut']
        ssidval = 'dutssid'+theBand.replace('g','')
        ssid = paramsDict['dut']['val'][ssidval]

        # valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
        securityval = 'dutsecurity'+theBand.replace('g','')
        security = paramsDict['dut']['val'][securityval]

        passwordval = 'dutpass'+theBand.replace('g','')
        password = paramsDict['dut']['val'][passwordval]

        print('>>> ssid: %s, security: %s, password: %s, band: %s' % (ssid, security, password, theBand))

        if   thisTest["BW"] == 20 : bandwidth = "BANDWIDTH_20_FIXED"
        elif thisTest["BW"] == 40 : bandwidth = "BANDWIDTH_40_ADAPT"
        elif thisTest["BW"] == 80 : bandwidth = "BANDWIDTH_80_ADAPT"
        elif thisTest["BW"] == 160: bandwidth = "BANDWIDTH_160_ADAPT"
        elif thisTest["BW"] == 320: bandwidth = "BANDWIDTH_320_ADAPT"

        if thisTest["interface"] == "11ax": interface = "INTERFACE_AX"
        if thisTest["interface"] == "11ac": interface = "INTERFACE_AC"
        if thisTest["interface"] == "11n" : interface = "INTERFACE_N"

        print("Test of {} for {} MHz bandwidth.".format(interface,bandwidth))

        ############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

        ############### START SECTION: BUILD THE TEST OBJECT #########################

        time.sleep(5)

        #See if you are using a Pal as the AP
        if paramsDict['usePalAsAP']['val']:
            palToUseAsAP = paramsDict['palToUseAsAP']['val']
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
            apDictList = sd2Utils.setupAP(palToUseAsAP, theBand, apDictList, type=interface, channel=theChannel, streams=theStreams, pushConfig=False, apDictOverride=apDictOverride)

        #Setting attenuation values for attenuators or MPEs:
        for atten in attensToUse:
            #sd2Utils.setAtten(atten,paramsDict[atten]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)
            sd2Utils.setAtten(atten,paramsDict[atten]['val']['devType'],paramsDict["quadAttenStart"]["val"],mpeBypassValue=63)

        debuggingWithAPal = False
        if STAisPal: debuggingWithAPal = False
        tpDictList = []
        updn = thisTest["direction"]
        if STAisPal or debuggingWithAPal:
            #Setting up traffic pairs:
            usePal = palToUse
            if debuggingWithAPal: usePal = "L3C-STApal"
            tpDictList = sd2Utils.setupTrafficPairs(usePal, theBand, updn,tpDictList,tMode=iperfMode,tLength=thisTest["packetSize"],tBW="{}M".format(thisTest["offer"]))

            #Setting up Pal configurations:
            staDictList = []
            staoverride={"ssid":ssid, "password": password, "security": security }
            staoverride["bandwidth"] = bandwidth
            staDictList = sd2Utils.setupSTA(usePal, theBand, staDictList, streams=theStreams, type=interface, channel=theChannel, staDictOverride=staoverride, pushConfig=True)
            targetRadio = staDictList[0]['palRadio']
            
        if not STAisPal:  #STA is not Pal.  It is a generic iperf client.
            serverSide = {"alias": "Server","managementAddress": paramsDict['oBox_server']['val']['address'],"trafficAddress": paramsDict['oBox_server']['val']['defaultIp'],
                          "devType": "server","radio": "","linkMonitor":False}
            otherSide = {"alias": customAlias,"managementAddress": customIP,"trafficAddress": customIP,"devType": palToUse + "Endpoint","radio": "",
                         "iperfPort": customPort,"linkMonitor":False}
            if updn == "up":
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
                "bitrate": "{}M".format(thisTest["offer"]),
                "trafficType": paramsDict['trafficType']['val'],
                "udp": iperfMode,
                "ipVersion": "ipv4",
                "ipStreams": paramsDict['parallel']['val'],
                "window": paramsDict['window']['val'],
                "length": paramsDict['length']['val'],
                "dscp": paramsDict["dscp"]["val"]
            }

            tpDictList.append(updateDict.copy())
            sd2Utils.updateAutotestInst(tpDictList, "trafficPairs", pushConfig=True)

            if debuggingWithAPal:
                tpDictList[0]['active'] = False
                updateDict = {"alias":tpDictList[0]['alias'] , "active": False}
                sd2Utils.updateTrafficPair(updateDict)                            

    else:  #This means that you are not changing the settings.  So just update the traffic pair.
        print("Settings have not significantly changed.  Going to modify only the traffic pair.")
        if len(tpDictList) < 1:
            print("I expect there to be a traffic pair, yet there is not.")
            sys.exit(8)
        #Get the active pair.  Not usually necessary, but if you are testing with a Pal running as an iPerf client it might be.
        for pair in tpDictList:
            if pair["active"]:
                thisPair = pair
                break
        #thisPair = tpDictList[0]
        thisPair["bitrate"] = "{}M".format(thisTest["offer"])
        thisPair["length"] = thisTest["packetSize"]
        if "Server" in thisPair["to"]["alias"]:
            serverSide = json.dumps(thisPair["to"])
            otherSide =  json.dumps(thisPair["from"])
        else:
            serverSide = json.dumps(thisPair["from"])
            otherSide =  json.dumps(thisPair["to"])
        if thisTest["direction"] == "up":
            thisPair["from"] = json.loads(otherSide)
            thisPair["to"]   = json.loads(serverSide)
        else:
            thisPair["from"] = json.loads(serverSide)
            thisPair["to"]   = json.loads(otherSide)
        sd2Utils.updateTrafficPair(thisPair)                                   

    ############### END SECTION: BUILD THE TEST OBJECT #########################

    ############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

    if STAisPal: sd2Utils.waitForAssociation(palToUse,targetRadio,timeToWait=45)
    else: time.sleep(10)  #Wait and hope that the device is associated after 10 seconds.

    ############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

    ############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

    ################################# Capture and run. #################################

    jsonZipPath = sd2Utils.runAutotest(sleepTime=2,unzip=False,saveCSV=False,saveTaJSON=False,triesLimit=60)

    #Rename the JSON zip file.
    newPath = globalsfile.outputDirPath + "/" + thisName + ".zip"
    command = "mv " + jsonZipPath + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)
    
    if haveCreateReport:
        retObj = createReport.analyze(directory_name,globalsfile.outputDirPath,ea_root)
        thisData = {"config":thisTest,"data":retObj}
        loggedResults.append(thisData.copy())
        sd2Utils.logToJSON(globalsfile.resultsPath, {"testData":loggedResults})

    #Clear the directory of zip files
    command = "rm {}/*.zip".format(globalsfile.outputDirPath)
    print("removing the json archives using this command: {}".format(command))
    os.system(command)
    
    ############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED #########################

# NOTE! Report creation requires a createReport.py file. 
if haveCreateReport:
	print('')
	print('##############################################################')
	print("########## Creating report ")
	print('##############################################################')	

	createReport.report(directory_name,globalsfile.outputDirPath,ea_root) # Actual arguments depend on createReport script

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
