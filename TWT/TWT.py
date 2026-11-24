'''
Test Description
================
Test Target Wake Time functionality.  Allow the use of either a real AP, or Pal6-A.
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime
import math

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

palToUseSTAdrop = paramsDict["palToUseSTA"]["val"]
for item in palToUseSTAdrop:
    if item["selected"]:
        palToUseSTA = item["value"]
        break

palToUseSnifferdrop = paramsDict["palToUseSniffer"]["val"]
for item in palToUseSnifferdrop:
    if item["selected"]:
        palToUseSniffer = item["value"]
        break


isJims = False

attensToUse = paramsDict["attensToUse"]["val"]
#(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
if isJims:
    attenList = ["MPE"]  #Jim's
else:
    #attenList = [attenToUseA,attenToUseB]
    attenList = attensToUse

testUses=paramsDict['testUses']['val']+[palToUseSTA]+attenList
if paramsDict["runPcapAnalysis"]["val"]:
        testUses.append(palToUseSniffer)
print(">>> testUses: ", testUses)

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)
############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

"""
#Toggle the TWT stuff
urlIP = paramsDict["oBox_server"]["val"]["publicip"]
serverExec =  "http://" + urlIP + ":8383/exec?command="
print('\n>>> Checking that basic server is running on STApal %s.' % palToUseSTA)
palMgmtIP = paramsDict[palToUseSTA]['val']['address']
url = serverExec+"curl http://"+palMgmtIP+":8383/"
resp = requests.get(url=url, timeout=REST_TIMEOUT)
jsn = json.loads(resp.text)
#print('>>> jsn: ', jsn)
isRunning = False
if jsn["status"] and jsn["status"] =="OK" and "reached" in jsn["stdout"]:
    print('>>> basic-server is running on STApal %s @ %s.' % (palToUseSTA,palMgmtIP))
    isRunning = True

if not isRunning:
    print("{}basic-server is not running on the STApal.  At least, I can't reach it.{}".format(cRed,cNormal))
    sys.exit(41)
"""
sd2Utils.checkBasicServerOnOBox(timeout=10)

#Get information about the server
serverMIp = paramsDict["oBox_server"]["val"]["address"]
serverIp  = paramsDict["oBox_server"]["val"]["defaultIp"]
serverParts = serverIp.split(".")

pieces = serverIp.split('.')
ipGateway = pieces[0] + "." + pieces[1] + "." + pieces[2] + "." + "1"

primaryChannel = int(paramsDict["primaryChannel"]["val"])

(theBand,palRadio) = sd2Utils.findBandFromChannel(primaryChannel)

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

APisPal6 = False;
APtoUseDrop = paramsDict["APtoUse"]["val"]
for item in APtoUseDrop:
    if item["selected"]:
        APtoUse = item["value"]
        break
if "Pal-6" in APtoUse: APisPal6 = True
if APisPal6:
    ssid = paramsDict["Pal6APssid"]["val"]
    security = paramsDict["Pal6APsecurity"]["val"]
    password = paramsDict["Pal6APpassword"]["val"]

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
#(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
#print('>>> attenToUseA: ', attenToUseA)
#print('>>> attenToUseB: ', attenToUseB)

if isJims:
    sd2Utils.setAtten("MPE",paramsDict["MPE"]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=True) #Jim's
else:
    #sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)
    #sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=True)
    icnt = 0
    for atten in attensToUse:
        pc = False
        icnt += 1
        if icnt == len(attensToUse): pc = True
        sd2Utils.setAtten(atten,paramsDict[atten]['val']['devType'],paramsDict["quadAttenStart"]["val"],mpeBypassValue=63,pushConfig=pc)


if APtoUse == "Pal-6B":
    sd2Utils.setAtten("QA-D",paramsDict["QA-D"]['val']['devType'],0,pushConfig=True)


timingEvents = []


if paramsDict["runPcapAnalysis"]["val"]:

        #Setting up sniffers.
        #Is SnifferRelay running?
        SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],True,args=paramsDict['oBox_server']['val']['publicip'])

        #Make a single sniffer
        snifSetDictList = []
        snifDispDictList = []
        snifStartDictList = []

        (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer, theBand, paramsDict['snifferBW']['val'], primaryChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])

        # Update sniffer Autotest configs and push
        sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
        sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True) 

        #Start sniffer early to catch eapol in case you need to decode encrypted frames.
        sd2Utils.startSniffers(snifStartDictList)
        snifferStart = time.time()
        timingEvents.append({"event":"Sniffer Start", "time":snifferStart, "timeFromSnifferStart":0})
        time.sleep(3)
        sd2Utils.isolateAllBoxes()
        time.sleep(5)

#Setting up traffic pairs:
tpDictList = []
if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"
palToUseAP = None
if APisPal6: palToUseAP = APtoUse
#tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList, palAsAP=palToUseAP)
tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList)

#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }
staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=interface, channel=primaryChannel, pushConfig=True, staDictOverride=staoverride)
targetRadio = staDictList[0]['palRadio']

if APisPal6:
    palToUseAP = APtoUse
    apDictList = []
    apoverride = {"ssid":ssid, "password": password, "security": security }
    apDictList = sd2Utils.setupAP(palToUseAP, theBand, apDictList, type=interface, channel=primaryChannel, apBridge=False, pushConfig=True, apDictOverride=apoverride)

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################
for atten in attensToUse:
    sd2Utils.setAttenDirect(atten,0)

sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

if paramsDict["runPcapAnalysis"]["val"]:
    snifferStart = time.time()
    timingEvents.append({"event":"Sniffer Start", "time":snifferStart, "timeFromSnifferStart":0})
    time.sleep(3)
    
#json_path = sd2Utils.runAutotest(sleepTime=2)
sd2Utils.startAutotest()

#Unexplained issue setting attenuators correctly.  Force them.
for atten in attensToUse:    sd2Utils.setAttenDirect(atten,0)
sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

trafficStart = time.time()
timingEvents.append({"event":"Traffic Start", "time":trafficStart, "timeFromSnifferStart":math.floor((trafficStart-snifferStart))})

urlIP = paramsDict["oBox_server"]["val"]["publicip"]
serverExec =  "http://" + urlIP + ":8383/exec?command="
palMgmtIP = paramsDict[palToUseSTA]['val']['address']

if isJims:
    pwd = "admin123"   #Jim's
else:
    pwd = "octoScope-customer-key-201504271520"
    
doCurl = serverExec+"curl http://"+palMgmtIP+":8383/exec?command="

theCommand = "echo {} | sudo -S wpa_cli twt_setup exponent=10 mantissa=512 min_twt=255 setup_cmd=0 twt=0 requestor=1 trigger=1 implicit=1 flow_type=1 flow_id=0 protection=0 twt_channel=0 = Send TWT frame".format(pwd)
url = doCurl + theCommand
print("Running " + url)
commandTime = time.time()
timingEvents.append({"event":"TWT Command", "time":commandTime, "command":theCommand, "timeFromSnifferStart":math.floor((commandTime-snifferStart))})
resp = requests.get(url=url, timeout=REST_TIMEOUT)
jsn = json.loads(resp.text)
print("Response from this command:\n {}".format(jsn))
time.sleep(8)

theCommand = "echo {} | sudo -S wpa_cli twt_teardown flags=0 = Send TWT Teardown frame".format(pwd)
url = doCurl + theCommand
print("Running " + url)
commandTime = time.time()
timingEvents.append({"event":"TWT Command", "time":commandTime, "command":theCommand, "timeFromSnifferStart":math.floor((commandTime-snifferStart))})
resp = requests.get(url=url, timeout=REST_TIMEOUT)
jsn = json.loads(resp.text)
print("Response from this command:\n {}".format(jsn))
time.sleep(4)

theCommand = "echo {} | sudo -S wpa_cli twt_setup exponent=0 mantissa=51200 min_twt=255 setup_cmd=1 twt=0 requestor=1 trigger=1 implicit=1 flow_type=1 flow_id=5 protection=0 twt_channel=0 = Send TWT frame".format(pwd)
url = doCurl + theCommand
print("Running " + url)
commandTime = time.time()
timingEvents.append({"event":"TWT Command", "time":commandTime, "command":theCommand, "timeFromSnifferStart":math.floor((commandTime-snifferStart))})
resp = requests.get(url=url, timeout=REST_TIMEOUT)
jsn = json.loads(resp.text)
print("Response from this command:\n {}".format(jsn))
time.sleep(8)

theCommand = "echo {} | sudo -S wpa_cli twt_teardown flags=5 = Send TWT Teardown frame".format(pwd)
url = doCurl + theCommand
print("Running " + url)
commandTime = time.time()
timingEvents.append({"event":"TWT Command", "time":commandTime, "command":theCommand, "timeFromSnifferStart":math.floor((commandTime-snifferStart))})
resp = requests.get(url=url, timeout=REST_TIMEOUT)
jsn = json.loads(resp.text)
print("Response from this command:\n {}".format(jsn))
time.sleep(4)

theCommand = "echo {} | sudo -S wpa_cli twt_setup exponent=0 mantissa=32768 min_twt=255 setup_cmd=2 twt=0 requestor=1 trigger=1 implicit=1 flow_type=1 flow_id=7 protection=0 twt_channel=0 = Send TWT frame".format(pwd)
url = doCurl + theCommand
print("Running " + url)
commandTime = time.time()
timingEvents.append({"event":"TWT Command", "time":commandTime, "command":theCommand, "timeFromSnifferStart":math.floor((commandTime-snifferStart))})
resp = requests.get(url=url, timeout=REST_TIMEOUT)
jsn = json.loads(resp.text)
print("Response from this command:\n {}".format(jsn))
time.sleep(1)

theCommand = "echo {} | sudo -S wpa_cli twt_setup exponent=0 mantissa=32768 min_twt=255 setup_cmd=0 twt=0 requestor=1 trigger=1 implicit=1 flow_type=1 flow_id=7 protection=0 twt_channel=0 = Send TWT frame".format(pwd)
url = doCurl + theCommand
print("Running " + url)
commandTime = time.time()
timingEvents.append({"event":"TWT Command", "time":commandTime, "command":theCommand, "timeFromSnifferStart":math.floor((commandTime-snifferStart))})
resp = requests.get(url=url, timeout=REST_TIMEOUT)
jsn = json.loads(resp.text)
print("Response from this command:\n {}".format(jsn))
time.sleep(8)

theCommand = "echo {} | sudo -S wpa_cli twt_teardown flags=7 = Send TWT Teardown frame".format(pwd)
url = doCurl + theCommand
print("Running " + url)
commandTime = time.time()
timingEvents.append({"event":"TWT Command", "time":commandTime, "command":theCommand, "timeFromSnifferStart":math.floor((commandTime-snifferStart))})
resp = requests.get(url=url, timeout=REST_TIMEOUT)
print("Response from this command:\n {}".format(jsn))
jsn = json.loads(resp.text)

json_path = sd2Utils.stopAutotest()

if paramsDict["runPcapAnalysis"]["val"]:
        globalsfile.fileSuffix = '_capture'	# Set pcap filename suffix
        pcapFile = sd2Utils.stopSniffers()

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
sd2Utils.logToJSON(globalsfile.resultsPath, {"timingEvents":timingEvents})

#########Generating JSON reports

#Remove existing test report so that if there is a problem here, you don't get fooled into thinking that an old report is the new report.
rmResult = os.system("rm " + directory_name + "TestReport-TWT.json")
print("Removing any old TestReport.json: {}".format(rmResult))

print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))

#Get rid of the CSV zip file.
theCSV = json_path.replace(".zip","_CSV.zip")
command = "rm " + theCSV
print("Removing the CSV zip file using this command: {}".format(command))
os.system(command)        

'''
#Place a PDF export in the same location
print('')
print('##############################################################')
print("########## Creating and saving UI PDF report ")
print('##############################################################')	

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
print("########## Analyzing captures and creating HTML test report ")
print('##############################################################')	

import createReport
eaLocationDrop = paramsDict["eaLocation"]["val"]
for item in eaLocationDrop:
    if item["selected"]:
        eaLocation = item["value"]        
        break
ea_root = "http://localhost:8080"
if eaLocation == "remote": ea_root = "http://www.octapi.tech"

ssid_decode = paramsDict["ssidForDecode"]["val"]
pwd_decode = paramsDict["pwdForDecode"]["val"]

createReport.main(directory_name,json_path,ea_root,pcapFile,ssid_decode,pwd_decode)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
