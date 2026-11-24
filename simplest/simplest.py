'''
Test Description
================
Simplest example of all.  A single traffic pair, not ramping.
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
        
tpDictList = []
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
        sd2Utils.setupAP(usePalAsAP, theBand, apDictList, type = interface, channel=palAPchannel, streams=useStreams, apBridge= True, pushConfig=True, apDictOverride=override)
        
        
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

staDictList = []
override = {"bandwidth":bandwidth}
override["ssid"] = ssid
override["security"] = security
override["password"] = password
if usingPalAsAP: override = {"ssid":palAPssid,"security":palAPsecurity,"password":palAPpassword,"bandwidth":bandwidth}
if chainRXMask != None: override["chainRXMask"] = chainRXMask
if chainTXMask != None: override["chainTXMask"] = chainTXMask
staDictList = sd2Utils.setupSTA(palToUse, theBand, staDictList, type=interface, channel=primaryChannel, bssid='', streams=streams, staDictOverride=override, pushConfig=True)

targetRadio = staDictList[0]['palRadio']

#Setting up AP configurations:
apDictList = []

print('\n>>> Adding test information to testresults.json')
resultDict = {"testInfo": testInfoDict}
resultDict['testInfo'].update({
        "timeStamp":globalsfile.timeStamp,
        "security":security, "ssid":ssid, "password":password,
        "band":theBand, "primaryChannel":primaryChannel, "bandwidth":bandwidth,
        "interface":interface, "streams":streams, "upOrDown": upOrDown
})
resultDict['testInfo'].update({"scriptSuiteVersion":globalsfile.scriptSuiteVersion})
resultDict['testInfo'].update({"starDustVersion":globalsfile.starDustVersion})
resultDict['testInfo'].update({"palFWversions":globalsfile.palFWdict})
if test_param_alt_file:
        resultDict['testInfo'].update({"testParamAltFile":test_param_alt_file})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

palsToUseSTA = [palToUse]
for palToUseSTA in palsToUseSTA: sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

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

        json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False)
        newPath = json_path.replace(".zip","_{}.zip".format(testNumber))
        command = "mv " + json_path + " " + newPath
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

#Place a PDF export in the same location
'''
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
'''

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
resultDict = {'testRunTime':testRunTime}
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

print('')
print('##############################################################')
print("##### Creating HTML report ")
print('##############################################################')
import createReport
ea_root = sd2Utils.whereIsEA()
print(">>> Expert Analysis is at {}".format(ea_root))
createReport.main(directory_name,globalsfile.outputDirPath,ea_root=ea_root)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("##### %s TEST DONE " % testName)
print("##### Test run time: %s. " % testRunTime)
print('##############################################################')	
