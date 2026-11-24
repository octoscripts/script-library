'''
Test Description
================
Puncturing test using Pal as AP to set the puncture.
Point really is to expose the EA functionality for puncturing analysis.
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime
import random

import zipfile
from zipfile import ZipFile

import pprint
pp = pprint.PrettyPrinter(indent=4)


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
json_dir = globalsfile.outputDirPath

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

############################
# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

haveCreateReport = False
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
    print("I see a file called createReport.  So using it for report creation.")
    haveCreateReport = True
    import createReport
else:
    print("I do not see a file called createReport.")

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

time.sleep(5)
sd2Utils.isolateAllBoxes()

palToUse = paramsDict["palToUse"]["val"]
print('>>> palToUse: ', palToUse)
attensToUse = paramsDict["attensToUse"]["val"]
print('>>> attensToUse: ', attensToUse)
attenStart = paramsDict["quadAttenStart"]["val"]
attenStop = paramsDict["quadAttenStop"]["val"]
print('>>> attenStart: %s, attenStop: %s ' % (attenStart,attenStop))

palToUseSniffer = paramsDict["palToUseSniffer"]["val"]

#Setting attenuation values for attenuators or MPEs:
for atten in attensToUse:
	devType = sd2Utils.getAttenType(atten)
	sd2Utils.setAtten(atten,devType,attenStart,attenValueStop=attenStop)


#Setting up traffic pairs:
ulDlDrop = paramsDict["ulDl"]["val"]
for item in ulDlDrop:
    if item["selected"]:
        ulDl = item["value"]
if(ulDl == 'up'): upLink = True
else: upLink = False
if upLink: print(">>> Running uplink traffic")
else: print(">>> Running downlink traffic")
upOrDown = ulDl
if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"

iperfMode = paramsDict["iperfMode"]["val"]
if iperfMode!='tcp' and iperfMode!='udp':
    print(">>> {} is not a valid iperf mode.".format(iperfMode))
    iperfMode = None

trafficType = paramsDict["trafficType"]["val"]
trafficBW = paramsDict["trafficBW"]["val"]
parallel = paramsDict["parallel"]["val"]
length = paramsDict["length"]["val"]
try:        
        if int(length) == 0: length = ""
except:
        length = ""

usePalAsAP = paramsDict["usePalAsAP"]["val"].strip()
usingPalAsAP = False

thisDrop = paramsDict["band"]["val"]
for item in thisDrop:
        if item["selected"]:
                theBand = item["value"]
                break
if "24" in theBand or "2.4" in theBand: theRadio = "RADIO_24"
elif "5" in theBand: theRadio = "RADIO_5A"
elif "6" in theBand: theRadio = "RADIO_6"
#FYI, this should ALWAYS be RADIO_6 in this test.

vstaSettings = paramsDict["vstaSettings"]["val"]

nPairs = int(vstaSettings["vstaCount"])
        
tpDictList = []
for pair in range(0,nPairs):
    tpDictList = sd2Utils.setupTrafficPairs(palToUse, theBand, updn, tpDictList, useWANendpoint=False, measureCongestion=False, palAsAP=usePalAsAP, tType=trafficType, tMode=iperfMode, tBW=trafficBW, tParallel=parallel, tLength='', tWindow='',linkMonitor=False)

ifaceDrop = paramsDict["iface"]["val"]
for item in ifaceDrop:
    if item["selected"]:
        interface = item["value"]
        break

bwDrop = paramsDict["bw"]["val"]
for item in bwDrop:
    if item["selected"]:
        bandwidth = item["value"]
        break

streams = int(paramsDict["nss"]["val"])

chainRXMask = None
if "chainRXMask" in paramsDict: chainRXMask = paramsDict["chainRXMask"]["val"]
chainTXMask = None
if "chainTXMask" in paramsDict: chainTXMask = paramsDict["chainTXMask"]["val"]

#Setting up AP configurations:
apDictList = []
if usePalAsAP != "" and usePalAsAP in paramsDict:
        usingPalAsAP = True
        print("{} Going to use Pal {} as the AP. {}".format(cGreen,usePalAsAP,cNormal))
        apDictList = []
        palAPssid = paramsDict["palAPssid"]["val"]
        thisDrop = paramsDict["palAPsecurity"]["val"]
        for item in thisDrop:
                if item["selected"]:
                        palAPsecurity = item["value"]
                        break
        palAPpassword = paramsDict["palAPpassword"]["val"]
        palAPchannel = paramsDict["palAPchannel"]["val"]
        override = {"ssid":palAPssid,"security":palAPsecurity,"password":palAPpassword,"bandwidth":bandwidth}
        if chainRXMask != None: override["chainRXMask"] = chainRXMask
        if chainTXMask != None: override["chainTXMask"] = chainTXMask
        useStreams = 4 # = streams

        #Let's get the allow puncturing channels.
        api_endpoint = "http://{}:4000/api/v1/pal7s/320/{}/RADIO_6/AP/INTERFACE_BE".format(paramsDict["oBox_server"]["val"]["publicip"],palAPchannel)
        theResponse = requests.get(api_endpoint,timeout=REST_TIMEOUT)
        theJson = json.loads(theResponse.text)
        #print(theJson)
        allowedPunctures = theJson
        resultDict = {"allowedPunctures":allowedPunctures}
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)        
        if len(allowedPunctures)>0:
            #punctureOut = allowedPunctures[0]
            punctureOut = random.choice(allowedPunctures)
            punctureStrict = True
            override["punctureChannels"] = punctureOut
            resultDict = {"punctureSelected":punctureOut}
            sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)        
            
        #________________
        
        apDictList = sd2Utils.setupAP(usePalAsAP, theBand, apDictList, type = interface, channel=palAPchannel, streams=useStreams, apBridge= True, pushConfig=True, apDictOverride=override)        
        
#Setting up Pal (STA) configurations:
primaryChannel = paramsDict['primaryChannel']['val']
try:
        if primaryChannel.strip() == "": primaryChannel = 0
        else: primaryChannel = int(primaryChannel)
except:
        primaryChannel = int(primaryChannel)
        
ssidval = 'dutssid'+theBand.replace('g','')
securityval = 'dutsecurity'+theBand.replace('g','')
passwordval = 'dutpass'+theBand.replace('g','')
# ssid, security and password are taken from params_system['dut']
ssid = paramsDict['dut']['val'][ssidval]
# valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
security = paramsDict['dut']['val'][securityval]
password = paramsDict['dut']['val'][passwordval]

#But, if using Pal as AP, ....
if usePalAsAP != "" and usePalAsAP in paramsDict:
    ssid = palAPssid
    password = palAPpassword
    security = palAPsecurity

print('>>> ssid: %s, security: %s, password: %s, channel: %s, band: %s' % (ssid, security, password, primaryChannel, theBand))

if vstaSettings["vstaCount"] > 1:
    print('##############################################################')
    print("############ Setting up {} vSTAs for Pal {} on radio {}".format(vstaSettings["vstaCount"],palToUse,theRadio))
    print('##############################################################')

    vstaParams = {
        "interface_": vstaSettings["interface"],
        "bandwidth": vstaSettings["bandwidth"],
        "certFilename": '',
        "radiusIdentity": '',
        "radiusPassword": '',
        "security": security,
        "ssid": ssid,
        "streams": useStreams,
        "txAtten": vstaSettings["txAtten"]
    }

    (vstaConfigList,tpDictList) = sd2Utils.setupVsta(palToUse, theBand, primaryChannel, upOrDown, paramsDict['iperfMode']['val'], vstaSettings["vstaCount"],vstaParams,tpDictList, pushConfig=False,linkMonitor=False,palAsAP=usePalAsAP)


staDictList = []
override = {"bandwidth":bandwidth}
override["ssid"] = ssid
override["security"] = security
override["password"] = password
if usingPalAsAP: override = {"ssid":palAPssid,"security":palAPsecurity,"password":palAPpassword,"bandwidth":bandwidth}
if chainRXMask != None: override["chainRXMask"] = chainRXMask
if chainTXMask != None: override["chainTXMask"] = chainTXMask
if vstaSettings["vstaCount"] > 1:
    override["vstaCount"] = vstaSettings["vstaCount"]
    override["vstaConfig"] = vstaConfigList

#print(json.dumps(override,indent=2))
#sys.exit()

staDictList = sd2Utils.setupSTA(palToUse, theBand, staDictList, type=interface, channel=primaryChannel, bssid='', streams=streams, staDictOverride=override, pushConfig=True)

targetRadio = staDictList[0]['palRadio']

#Setting up sniffers.
#Is SnifferRelay running?
SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],True,args=paramsDict['oBox_server']['val']['publicip'])

snifSetDictList = []
snifDispDictList = []
snifStartDictList = []

snifferChannel = primaryChannel
if "6" in theRadio: snifferChannel += 190

(snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer, theBand, 160, snifferChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])

# Update sniffer Autotest configs and push
sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True) 

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

vstaWait = int(paramsDict["vstaWait"]["val"])
assocWaitTime = 40 + vstaWait

palsToUseSTA = [palToUse]
#for palToUseSTA in palsToUseSTA: sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)
for palToUseSTA in palsToUseSTA:
    if vstaSettings["vstaCount"] > 1:    
        associatedStatus = sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=assocWaitTime,vstasRequired=vstaSettings["vstaCount"])
    else:
        associatedStatus = sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

totalTests = paramsDict["totalTests"]["val"]
try:
        totalTests = int(totalTests)
except:
        totalTests = 1
if totalTests<1: totalTests = 1

for testNumber in range (0,totalTests):

        sd2Utils.startSniffers(snifStartDictList)

        jsonFile = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)

        globalsfile.fileSuffix = 'PCAP_{}'.format(testNumber)    # Set pcap filename suffix
        pcapFile = sd2Utils.stopSniffers()

        if haveCreateReport:
            packetAnalysis,Stats = createReport.dataAnalysis(directory_name,json_dir,pcapFile,jsonFile)
            resultDict = {"Test_{}".format(testNumber):{"pcap":packetAnalysis,"stats":Stats}}
            sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
        
        newPath = jsonFile.replace(".zip","_{}.zip".format(testNumber))
        command = "mv " + jsonFile + " " + newPath
        print("Renaming the json file using this command: {}".format(command))
        os.system(command)        
        print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,newPath,cNormal))
        

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))

print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')

if haveCreateReport:
    myReport = createReport.main(directory_name,json_dir)


testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("##### %s TEST DONE " % testName)
print("##### Test run time: %s. " % testRunTime)
print('##############################################################')	
