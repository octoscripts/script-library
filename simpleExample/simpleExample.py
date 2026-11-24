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

attenList = []
matches = ["MIN","MID","MAX","MESH"]
if any(x in paramsDict['systemConfig']['val']['stackType'] for x in matches):
    attenList = [paramsDict["pathAatten"],paramsDict["pathBatten"]]

testUses=paramsDict['testUses']['val']+[palToUseSTA]+attenList
if paramsDict["runPcapAnalysis"]["val"]:
        testUses.append(palToUseSniffer)
print(">>> testUses: ", testUses)

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)
############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

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
#print('### EXIT @ LINE 173')
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
sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=True)

palsInTestMgmtIPs = []
palSnifferMgmtIPs = []
if paramsDict["runPcapAnalysis"]["val"]: palSnifferMgmtIPs.append(paramsDict[palToUseSniffer]["val"]["address"])

usePalAsAP = paramsDict["usePalAsAP"]["val"].strip()
usingPalAsAP = False

#Setting up traffic pairs:
tpDictList = []
if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"
tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList,palAsAP=usePalAsAP)

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
    #if chainRXMask != None: override["chainRXMask"] = chainRXMask
    #if chainTXMask != None: override["chainTXMask"] = chainTXMask
    useStreams = 4 # = streams
    if paramsDict[usePalAsAP]["val"]["address"] in palSnifferMgmtIPs: override["captureEnable"] = True
    sd2Utils.setupAP(usePalAsAP, '5g', apDictList, type = interface, channel=palAPchannel, streams=useStreams, apBridge= True, pushConfig=False, apDictOverride=override)
    palsInTestMgmtIPs.append(paramsDict[usePalAsAP]["val"]["address"])


#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }
if usingPalAsAP: staoverride = {"ssid":palAPssid,"security":palAPsecurity,"password":palAPpassword,"bandwidth":bandwidth}
if paramsDict[palToUseSTA]["val"]["address"] in palSnifferMgmtIPs: staoverride["captureEnable"] = True
staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=interface, channel=primaryChannel, pushConfig=True,staDictOverride=staoverride)
targetRadio = staDictList[0]['palRadio']
palsInTestMgmtIPs.append(paramsDict[palToUseSTA]["val"]["address"])


if paramsDict["runPcapAnalysis"]["val"]:
        #Setting up sniffers.
        #Is SnifferRelay running?
        SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],True,args=paramsDict['oBox_server']['val']['publicip'])

        #Make a single sniffer
        snifSetDictList = []
        snifDispDictList = []
        snifStartDictList = []

        (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer, theBand, paramsDict['snifferBW']['val'], primaryChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])

        #Only set sniffers if they are NOT existing endpoints.
        for object in snifSetDictList:
            if object["palAddress"] in palsInTestMgmtIPs:
                print("Remove this object with address {} from the snifSetDictList:\n {}".format(object["palAddress"],object))
                snifSetDictList.remove(object)
        '''
        print('')
        print('#################################')
        print('>>> snifSetDictList:')
        pp.pprint(snifSetDictList)
        print('>>> snifDispDictList:')
        pp.pprint(snifDispDictList)
        print('>>> snifStartDictList:')
        pp.pprint(snifStartDictList)
        sys.exit()
        '''
        
        # Update sniffer Autotest configs and push
        sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
        sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True) 

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################


if paramsDict["runPcapAnalysis"]["val"]:
        sd2Utils.startSniffers(snifStartDictList)

json_path = sd2Utils.runAutotest(sleepTime=2)

if paramsDict["runPcapAnalysis"]["val"]:
        globalsfile.fileSuffix = 'FirstPCAP'	# Set pcap filename suffix
        pcapFile = sd2Utils.stopSniffers()

print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')
bandDir = theBand+'_'+upOrDown
resultDict = {bandDir:{}}

filter ={"want": "avg"}
type = 'THROUGHPUT'
result = sd2Utils.avgDataPost(type,filter,tpDictList[0],multival=True,attenName=attenToUseA)
if result:
    resultDict[bandDir].update({filter['want']:result})
    print('#########################################')
    print('>>> resultDict ', (resultDict))	
    print('#########################################')
    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
else:
	message = "Results for "+type+", "+filter['want']+" not found."
	failHandler('MainScript',message, errCode=0)

filter ={"want": "rssiMgmtMean"}
type = 'PALSTATS'
result = sd2Utils.avgDataPost(type,filter,tpDictList[0],multival=True,attenName=attenToUseA)
if result:
    resultDict[bandDir].update({filter['want']:result})
    print('#########################################')
    print('>>> resultDict ', (resultDict))
    print('#########################################')
    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
else:
	message = "Results for "+type+", "+filter['want']+" not found."
	failHandler('MainScript',message, errCode=0)

if paramsDict["runPcapAnalysis"]["val"]:
    if paramsDict["doSecondCapture"]["val"]:
        #As another example, start the sniffing again, wait, capture, store, and stop.
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(10)
        globalsfile.fileSuffix = 'SecondPCAP'	# Set pcap filename suffix
        pcapFile = sd2Utils.stopSniffers()

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
resultDict = {}
resultDict = {'testRunTime':testRunTime}
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

######### Generating JSON reports

#Remove existing test report so that if there is a problem here, you don't get fooled into thinking that an old report is the new report.
try:
	rmResult = os.system("rm " + directory_name + "TestReport.json")
	print(">>> Removed all old TestReport.json: {}".format(rmResult))
except:
	print(">>> No TestReport.json found. No file removed.")

print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))

# Export time aligned JSON file
URL = "http://" + "{}:4000".format(paramsDict["oBox_server"]["val"]["publicip"]) + "/api/v1/reports/json/timeAligned/{}".format(testName)
response = requests.get(URL,timeout=REST_TIMEOUT)
if response.status_code != 200:
    print("reports/timeAligned/ GET FAILED")
else:
    print("reports/timeAligned/ GET SUCCEEDED")
if response.iter_content:
    TAJpath = json_path.replace(".zip","-TAJ.zip")
    with open(TAJpath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    print('>>>: Saving zip of autotest time aligned JSONs SUCCESS.')

    print('>>>: Unzipping and saving autotest time-aligned JSONs.')
    with ZipFile(TAJpath, 'r') as zipObj:
        zipObj.extractall(path = globalsfile.outputDirPath)
    print('>>> getAutotestResults: Unzipping and saving autotest time-aligned JSONs SUCCESS.')

if paramsDict["doPDF"]["val"]:
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

print('')
print('##############################################################')
print("##### Creating HTML report ")
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
print("##### %s TEST DONE " % testName)
print("##### Test run time: %s. " % testRunTime)
print('##############################################################')
