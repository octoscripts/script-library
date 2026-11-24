'''
© Keysight Technologies 2001-2026
 
IMPORTANT: This file contains human readable or software in a source code format (“Source Files”), and such Source Files are subject to the terms and conditions
of the Keysight Software End-User License Agreement (“EULA”) www.Keysight.com/find/sweula and these Supplemental Terms.
BY USING THE SOURCE FILES, YOU AGREE TO BE BOUND BY THE TERMS AND CONDITIONS OF THE EULA INCLUDING THESE SUPPLEMENTAL TERMS.
IF YOU DO NOT AGREE TO THESE TERMS AND CONDITIONS, DO NOT COPY OR DISTRIBUTE THE SOURCE FILES.

    1. Additional Rights and Limitations. For Source Files Keysight grants you a limited, non-exclusive license, to sub-license, to copy, modify and distribute the Source Files.
       You own any such modifications and Keysight retains all right, title and interest in the underlying Software and Source Files. All rights not expressly granted are reserved by Keysight.
    2. Any distribution of the Source Files, unmodified or modified, to an external party shall be pursuant to an enforceable agreement that provides similar protections for Keysight
       and its suppliers as those contained in the EULA and these Supplemental Terms. 
    3. General. Capitalized terms used in these Supplemental Terms and not otherwise defined herein shall have the meanings assigned to them in the EULA.
       To the extent that any of these Supplemental Terms conflict with terms in the EULA, these Supplemental Terms control solely with respect to the Source Files.
'''

'''
Test Description
================
Example of turning on/off traffic pairs during a single run.
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

############################
# Set up some text coloring
cRed=   '\033[m'
cGreen= '\033[m'
cNormal='\033[m'

# Build list for config check

(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]

palToUseSTAs = ["W1C-STApal","L2C-STApal","L3C-STApal","L4C-STApal","L5C-STApal","L6C-STApal","L7C-STApal","W8C-STApal","W9C-STApal","L10C-STApal","L11C-STApal","L12C-STApal","L13C-STApal","L14C-STApal","L15C-STApal","W16C-STApal"]
palToUseSTAs = paramsDict["palToUseSTAs"]["val"]
testUses=paramsDict['testUses']['val']+palToUseSTAs+attenList
print(">>> testUses: ", testUses)

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)
############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

#Get information about the server
serverMIp = paramsDict["oBox_server"]["val"]["address"]
serverIp  = paramsDict["oBox_server"]["val"]["defaultIp"]
serverParts = serverIp.split(".")

pieces = serverIp.split('.')
ipGateway = pieces[0] + "." + pieces[1] + "." + pieces[2] + "." + "1"

primaryChannel = int(paramsDict["primaryChannel"]["val"])

if primaryChannel < 14: 
	theBand = '24g'
elif primaryChannel >=36 and globalsfile.channelFound <= 165: 
	theBand = '5g'
elif primaryChannel >=191:
	theBand = '6g'	

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

ssidval = 'dutssid'+theBand.replace('g','')
securityval = 'dutsecurity'+theBand.replace('g','')
passwordval = 'dutpass'+theBand.replace('g','')

# ssid, security and password are taken from params_system['dut']
ssid = paramsDict['dut']['val'][ssidval]
# valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
security = paramsDict['dut']['val'][securityval]
password = paramsDict['dut']['val'][passwordval]
print('>>> ssid: %s, security: %s, password: %s, channel: %s, band: %s' % (ssid, security, password, primaryChannel, theBand))
#print('### EXIT @ LINE 184')
#sys.exit()

ulDlDrop = paramsDict["ulDl"]["val"]
for item in ulDlDrop:
    if item["selected"]:
        ulDl = item["value"]
if(ulDl == 'up'): upLink = True
else: upLink = False
if upLink: print(">>> Running uplink traffic")
else: print(">>> Running downlink traffic")
upOrDown = ulDl

iperfMode = paramsDict["iperfMode"]["val"]
if iperfMode!='tcp' and iperfMode!='udp':
    print(">>> {} is not a valid iperf mode.".format(iperfMode))
    iperfMode = None

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
print('>>> attenToUseA: ', attenToUseA)
print('>>> attenToUseB: ', attenToUseB)

sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)

#Setting up traffic pairs:
tpDictList = []
if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"
override = {}
if paramsDict["trafficType"]["val"].lower() == "iperf2":
    #Then, the traffic pair
    override = {
        "histogram":True,
        "binCount": "50000",
        "binWidth": "20", #This is in usec.
        "lowerCi": "90",
        "upperCi": "99"
    }
for palToUseSTA in palToUseSTAs:
    pc = False
    if palToUseSTA == palToUseSTAs[len(palToUseSTAs)-1]: pc = True
    tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList,tpDictOverride=override,pushConfig=pc)

#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }
for palToUseSTA in palToUseSTAs:
    pc = False
    if palToUseSTA == palToUseSTAs[len(palToUseSTAs)-1]: pc = True
    staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=interface, channel=primaryChannel, pushConfig=pc)
targetRadio = staDictList[0]['palRadio']

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

for palToUseSTA in palToUseSTAs:
    sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

#Start by turning on only the first traffic pair
for x in range(0,len(tpDictList)):
    theTPdict = tpDictList[x]
    if x==0: theTPdict["active"] = True
    else: theTPdict["active"] = False
    print("---> Setting the traffic pair {} activity setting to {}".format(theTPdict["alias"],theTPdict["active"]))
    sd2Utils.updateTrafficPair(theTPdict)

#Start the test
sd2Utils.startAutotest()

#Wait 20 seconds and turn on each additional traffic pair
for x in range(1,len(tpDictList)):
    time.sleep(20)
    theTPdict = tpDictList[x]
    theTPdict["active"] = True
    print("---> Setting the traffic pair {} activity setting to {}".format(theTPdict["alias"],theTPdict["active"]))
    sd2Utils.updateTrafficPair(theTPdict)

#Wait 20 seconds and then turn off the traffic pairs one by one, starting from the first.
for x in range(0,len(tpDictList)-1):
    time.sleep(20)
    theTPdict = tpDictList[x]
    theTPdict["active"] = False
    print("---> Setting the traffic pair {} activity setting to {}".format(theTPdict["alias"],theTPdict["active"]))
    sd2Utils.updateTrafficPair(theTPdict)

#Wait 20 more seconds and end the test.
time.sleep(20)
json_path = sd2Utils.stopAutotest(unzip=False)

print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')
bandDir = theBand+'_'+upOrDown
resultDict = {bandDir:{}}


############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
resultDict = {}
resultDict = {'testRunTime':testRunTime}
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

#########Generating JSON reports

#Remove existing test report so that if there is a problem here, you don't get fooled into thinking that an old report is the new report.
rmResult = os.system("rm " + directory_name + "TestReport.json")
print("Removing any old TestReport.json: {}".format(rmResult))

print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))

print('')
print('##############################################################')
print("########## Creating HTML report ")
print('##############################################################')	

import createReport
if 'C' in palToUseSTA:
        attenToUse = attenToUseA
ea_root = sd2Utils.whereIsEA()
print(">>> Expert Analysis is at {}".format(ea_root))
createReport.main(directory_name,globalsfile.outputDirPath,attenToUse,ea_root=ea_root)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
