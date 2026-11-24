'''
Test Description
================
https://www.bufferbloat.net/projects/bloat/wiki/Tests_for_Bufferbloat/.
Quick: Test for Bufferbloat
If you want to observe latency under load (“bufferbloat”) for yourself, try this:
Start a ping to google.com. You’ll see a series of lines, one per ping, typically with times in the 20-100 msec range.
Start a speed test from one of the speed test services below while the pings continue:
http://fast.com
http://speedtest.net
Watch the ping times while the speed test is running. If the times jump up when uploading or downloading, then your router is probably bloated.
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
import createReport

# Build list for config check

drop = paramsDict["eaLocation"]["val"]
for item in drop:
    if item["selected"]:
        eaLocation = item["value"]
if eaLocation == "remote": ea_root = "http://www.octapi.tech/"
elif eaLocation == "local": ea_root = "http://localhost:8080/"

palToUseSTAdrop = paramsDict["palToUseSTA"]["val"]
for item in palToUseSTAdrop:
    if item["selected"]:
        palToUseSTA = item["value"]
        break

usePalAsAp = paramsDict["usePalAsAp"]["val"]

palToUsePingdrop = paramsDict["palToUsePing"]["val"]
for item in palToUsePingdrop:
    if item["selected"]:
        palToUsePing = item["value"]
        break

(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]

testUses=paramsDict['testUses']['val']+[palToUseSTA,palToUsePing]+attenList
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

trafficBWstart = int(paramsDict["trafficBWstart"]["val"])
trafficBWend = int(paramsDict["trafficBWend"]["val"])
trafficBWstep = int(paramsDict["trafficBWstep"]["val"])

ssidval = 'dutssid'+theBand.replace('g','')
securityval = 'dutsecurity'+theBand.replace('g','')
passwordval = 'dutpass'+theBand.replace('g','')

# ssid, security and password are taken from params_system['dut']
ssid = paramsDict['dut']['val'][ssidval]
# valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
security = paramsDict['dut']['val'][securityval]
password = paramsDict['dut']['val'][passwordval]
print('>>> ssid: %s, security: %s, password: %s, channel: %s, band: %s' % (ssid, security, password, primaryChannel, theBand))

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

useIperfHistograms = paramsDict["useIperfHistograms"]["val"]

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

#Set all attenuators to max
sd2Utils.isolateAllBoxes()

if usePalAsAp:
    #First of all, set up Pal6A as the AP to use.
    apDictList = []
    palToUseAsAP = "Pal-6A"
    apDictOverride = {"ssid":ssid, "security":security, "password":password}
    sd2Utils.setupAP(palToUseAsAP, theBand, apDictList, type = interface, channel=primaryChannel, streams=streams, apBridge= False, pushConfig=False, apDictOverride=apDictOverride)
else:
    palToUseAsAP = None

#Setting attenuation values for attenuators or MPEs:
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
print('>>> attenToUseA: ', attenToUseA)
print('>>> attenToUseB: ', attenToUseB)

sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=True)

#Setting up traffic pairs:
tpDictList = []
if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"

#First, the ping pair.
tpDictList = sd2Utils.setupTrafficPairs(palToUsePing, theBand, updn, tpDictList, tType="ping", palAsAP=palToUseAsAP)

override = {}
if useIperfHistograms:
    #Then, the traffic pair
    override = {
        "histogram":True,
        "binCount": "50000",
        "binWidth": "20", #This is in usec.
        "lowerCi": "90",
        "upperCi": "99"
    }
    
tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList, palAsAP=palToUseAsAP,tpDictOverride=override)
sd2Utils.logToJSON(globalsfile.resultsPath, {"histInfo":override})

#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }

staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=interface, channel=primaryChannel, pushConfig=False)
trafficStaAlias = staDictList[0]["alias"]
print("The stations alias for the traffic pair is " + trafficStaAlias)

staDictList = sd2Utils.setupSTA(palToUsePing, theBand, staDictList, type=interface, channel=primaryChannel, pushConfig=True)
pingStaAlias = staDictList[1]["alias"]
print("The stations alias for the ping pair is " + pingStaAlias)

targetRadio = staDictList[0]['palRadio']



############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

delayVsRate = {"delayVsRate":{}}

listToDo = []
listToDo.append({"active":False,"rate":"1K"})
for bRate in range (trafficBWstart, trafficBWend, trafficBWstep): listToDo.append({"active":True, "rate": str(bRate)+"M"})
listToDo.append({"active":True,"rate":"1200M"})

for item in listToDo:
    theTPdict = tpDictList[1]
    theTPdict["active"] = item["active"]
    theTPdict["bitrate"] = item["rate"]
    sd2Utils.updateTrafficPair(theTPdict)
    json_path = sd2Utils.runAutotest(sleepTime=2,unzip=False)

    #Place a CSV export in the same location
    URL = "http://" + "{}:4000".format(paramsDict["oBox_server"]["val"]["publicip"]) + "/api/v1/reports/csv/{}".format(testName)
    csv_report = requests.get(URL,timeout=REST_TIMEOUT)
    csv_path = json_path.replace(".zip","-csv.zip")
    with open(csv_path, 'wb') as f:
        for chunk in csv_report.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    print("\n>>> {} CSV file at: {} {}".format(cGreen,csv_path,cNormal))

    ############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

    ############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

    testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
    resultDict = {}
    resultDict = {'testRunTime':testRunTime}
    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
    retObj = createReport.extract(json_path,ea_root)
    delayVsRate["delayVsRate"][item["rate"]] = retObj
    sd2Utils.logToJSON(globalsfile.resultsPath, delayVsRate)

#########Generating JSON reports

#Remove existing test report so that if there is a problem here, you don't get fooled into thinking that an old report is the new report.
rmResult = os.system("rm " + directory_name + "TestReport.json")
print("Removing any old TestReport.json: {}".format(rmResult))

print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))

#Place a PDF export in the same location
'''
pdf_dict = {
"showAll": True,
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

print('')
print('##############################################################')
print("########## Creating HTML report ")
print('##############################################################')	

createReport.plot(directory_name,globalsfile.outputDirPath,useIperfHistograms)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	


