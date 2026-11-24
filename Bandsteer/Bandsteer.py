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

#####START: Delete the previous results from results directory#####
try:
    for files in os.listdir(params.resultsDir):
        path = os.path.join(params.resultsDir, files)
        try:
            shutil.rmtree(path)
        except OSError:
            os.remove(path)
except:
    print("[INFO]: Not able to clean up the results directory")

#####END: Delete the previous results from results directory#####

############### START SECTION: PRINT PARAMS FROM MANIFEST #########################

############### END SECTION: PRINT PARAMS FROM MANIFEST #########################

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
    
print("[INFO]: The local directory is here: " + directory_name) # simpleExample folder

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

runPcapAnalysis = paramsDict["runPcapAnalysis"]["val"]

if runPcapAnalysis:
    sd2Utils.info("Script WILL use sniffers during the test.")
    sd2Utils.info('\n>>> Checking and stopping all active captures and Wireshark instances.')
    sd2Utils.stopSniffers(waitForPcap=False)
else:
    sd2Utils.info("Script WILL NOT use sniffers during the test.")
    

# Build list for config check
attenList = []
matches = ["MIN","MID","MAX","MESH"]
if any(x in paramsDict['systemConfig']['val']['stackType'] for x in matches):
    attenList = [paramsDict["pathAatten"],paramsDict["pathBatten"]]

thisDrop = paramsDict["palToUseSTA"]["val"]
for item in thisDrop:
    if item["selected"]:
        palToUseSTA = item["value"]
        break

thisDrop = paramsDict["palToUseSniffer"]["val"]
for item in thisDrop:
    if item["selected"]:
        palToUseSniffer = item["value"]
        break
thisDrop = paramsDict["palToUseSniffer2"]["val"]
for item in thisDrop:
    if item["selected"]:
        palToUseSniffer2 = item["value"]
        break
thisDrop = paramsDict["palToUseSniffer3"]["val"]
for item in thisDrop:
    if item["selected"]:
        palToUseSniffer3 = item["value"]
        break
snifferChannel = paramsDict["snifferChannel"]["val"]
snifferChannel2 = paramsDict["snifferChannel2"]["val"]
snifferChannel3 = paramsDict["snifferChannel3"]["val"]

testUses=paramsDict['testUses']['val']+[palToUseSTA]+[palToUseSniffer]+attenList
sd2Utils.info(">>> testUses: {}".format(testUses))
# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)
############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

# Find where Expert Analysis is running for report generation
ea_root = sd2Utils.whereIsEA()

primaryChannel = 0

if primaryChannel < 20:
    band = "2.4GHz"
    theBand = '24g'
    palRadio = "RADIO_24"
    ssid = paramsDict['dut']['val']['dutssid24']
    security = paramsDict['dut']['val']['dutsecurity24']
    password = paramsDict['dut']['val']['dutpass24']
if primaryChannel >= 36  and primaryChannel <= 165: 
    band = "5GHz"
    theBand = '5g'
    palRadio = "RADIO_5"
    ssid = paramsDict['dut']['val']['dutssid5']
    security = paramsDict['dut']['val']['dutsecurity5']
    password = paramsDict['dut']['val']['dutpass5']
elif primaryChannel >=191:
    band = '6GHz'
    theBand = '6g'
    ssid = paramsDict['dut']['val']['dutssid6']
    security = paramsDict['dut']['val']['dutsecurity6']
    password = paramsDict['dut']['val']['dutpass6']
        
ifaceDrop = paramsDict["iface"]["val"]
for item in ifaceDrop:
    if item["selected"]:
        interface = item["value"]
        break

bandwidth = "BANDWIDTH_ADAPT"

streams = paramsDict["nss"]["val"]
streams = int(streams)
  
ulDlDrop = paramsDict["ulDl"]["val"]
for item in ulDlDrop:
    if item["selected"]:
        ulDl = item["value"]
if(ulDl == 'up'): upLink = True
else: upLink = False
if upLink: sd2Utils.info(">>> Running uplink traffic")
else: sd2Utils.info(">>> Running downlink traffic")
upOrDown = ulDl

iperfMode = paramsDict["iperfMode"]["val"]
if iperfMode!='tcp' and iperfMode!='udp':
    sd2Utils.info(">>> {} is not a valid iperf mode.".format(iperfMode))
    iperfMode = None

############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

############### START SECTION: BUILD THE TEST OBJECT #########################

testPrefix = paramsDict['testPrefix']['val']   	# for test record filenames
sd2Utils.getTimestampS()	# for test record filenames

# Create the output folder
globalsfile.outputDirPath = resultsDirectory+paramsDict['topDirectory']+'/'+paramsDict['subDirectory']

if not os.path.exists(globalsfile.outputDirPath):
	os.makedirs(globalsfile.outputDirPath)
sd2Utils.info ('\n>>> Data will be stored in {}'.format(globalsfile.outputDirPath))
time.sleep(5)

#Restrict to Linux STApals for the time being

#palToUseSTA = paramsDict['palToUseSTA']['val']

#Doing your own ramping. Find the steps.
qaStart = paramsDict["quadAttenStart"]["val"]
qaStop = paramsDict["quadAttenStop"]["val"]
qaStep = paramsDict["step"]["val"]
qaDwell = paramsDict["stepDuration"]["val"]
qaDirection = 1
if qaStop < qaStart: qaDirection = -1
low = min(qaStart,qaStop)
hi = max(qaStart,qaStop)
val = low
qaValues = []
while val <= hi:
  qaValues.append(val)
  val += qaStep
if qaValues[len(qaValues)-1] != hi: qaValues.append(hi)
if qaDirection < 0: qaValues.reverse()
print("Quad-attens to be stepped using these values: {}".format(qaValues))

#Setting attenuation values for attenuators or MPEs:
attensToUse = paramsDict["attensToUse"]["val"]
attensForSniffers = paramsDict["attensForSniffers"]["val"]
for i in range (len(attensForSniffers)-1 , -1 , -1):
    if attensForSniffers[i] in attensToUse:
        print("Removing attenuator {} from the sniffer attenuator list because it's in the ramping attenuator list.".format(attensForSniffers[i]))
        attensForSniffers.pop(i)
print("The modified list of sniffing attenuators is {}".format(attensForSniffers))

#Setting up traffic pairs:
tpDictList = []
if "2.4" in band: theBand = "24g"
if "5" in band: theBand = "5g"
if "6" in band: theBand = "6g"

if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"
theTrafficBW = paramsDict["trafficBW"]["val"]
sd2Utils.info("Using the following as the traffic BW:  {}".format(theTrafficBW))
tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList, tBW=theTrafficBW)

#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }
staoverride["kEnable"] = True
staoverride["vEnable"] = True
staoverride["rFastTransitionEnable"] = True
staoverride["roamTargetThreshold"] = paramsDict["roamTargetThreshold"]["val"]
staoverride["roamThreshold"]       = paramsDict["roamThreshold"]["val"]
staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=interface, channel=primaryChannel, staDictOverride=staoverride, pushConfig=True)
targetRadio = staDictList[0]['palRadio']

#Don't do this anymore.  This assumes Sniffer Relay running on the same machine as the script.  That's not a good assumption.
#Setting up sniffers.
#Is sniffer relay running?
if runPcapAnalysis:
    SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],True,args=paramsDict['oBox_server']['val']['publicip'])        

#Make sniffers
snifSetDictList = []
snifDispDictList = []
snifStartDictList = []

if runPcapAnalysis:
    (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer, theBand, 160, snifferChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])    
    (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer2, theBand, 160, snifferChannel2, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])    
    (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer3, theBand, 160, snifferChannel3, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])    

if runPcapAnalysis:    
    # Update sniffer Autotest configs and push
    sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
    sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True)
    #print(snifSetDictList)
    #print(snifStartDictList)

sd2Utils.isolateAllBoxes()
#Remove the attenuators from the setup
print("Removing the attenuators from the test configuration.")
#updateDict =({"quadAttens": []})
#sd2Utils.updateAutotest(updateDict)
#updateDict =({"virtualAttens": []})
#sd2Utils.updateAutotest(updateDict)
#updateDict =({"mpes": []})
#sd2Utils.updateAutotest(updateDict)

totalTestLength = qaDwell * len(qaValues)
totalTestLength *= 5
print("Updating the test time to {} sec.".format(totalTestLength))
#updateDict =({"stepDuration": totalTestLength})
updateDict =({"quadAttens": [], "virtualAttens": [], "mpes": [], "stepDuration": totalTestLength})
sd2Utils.updateAutotest(updateDict)

print("Put the Pal into standby")
sd2Utils.setPalStandby(palToUseSTA, theBand, doStart=False)

print("Opening up sniffer paths, if appropriate")
#Open up the paths to the sniffers and just leave them open
for atten in attensForSniffers:
    print("For sniffing, setting {} to 0.".format(atten))
    devType = paramsDict[atten]["val"]["devType"]
    if "Atten" in devType: sd2Utils.setAttenDirect(atten,0)
    else: sd2Utils.setMpeDirect(atten,0,1)

print("Opening up ramp paths to associate the STA")
#Start with the ramping attenuators open
for atten in attensToUse:
    print("For association, setting {} to 0.".format(atten))
    devType = paramsDict[atten]["val"]["devType"]
    if "Atten" in devType: sd2Utils.setAttenDirect(atten,0)
    else: sd2Utils.setMpeDirect(atten,0,1)

time.sleep(4)

print("Take the Pal out of standby")
sd2Utils.setPalStandby(palToUseSTA, theBand, doStart=True)

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################
##commenting sniffer related section##
if runPcapAnalysis:
    sd2Utils.startSniffers(snifStartDictList)
    
#jsonZipPath = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,saveTaJSON=False)

qaValue = qaValues[0]
for atten in attensToUse:
    print("For starting, setting {} to {}.".format(atten,qaValue))
    devType = paramsDict[atten]["val"]["devType"]
    if "Atten" in devType: sd2Utils.setAttenDirect(atten,qaValue)
    else: sd2Utils.setMpeDirect(atten,qaValue,1)

sd2Utils.startAutotest()
for qaValue in qaValues:
    for atten in attensToUse:
        print("For ramping, setting {} to {}.".format(atten,qaValue))
        devType = paramsDict[atten]["val"]["devType"]
        if "Atten" in devType: sd2Utils.setAttenDirect(atten,qaValue)
        else: sd2Utils.setMpeDirect(atten,qaValue,1)
    time.sleep(qaDwell)

jsonZipPath = sd2Utils.stopAutotest(unzip=False,saveCSV=False,saveTaJSON=False)

if runPcapAnalysis:
    globalsfile.fileSuffix = 'Bandsteer'	# Set pcap filename suffix
    pcapFile = sd2Utils.stopSniffers(killWireshark=False)

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED #########################
import createReport

sd2Utils.info('')
sd2Utils.info('##############################################################')
sd2Utils.info("########## Creating report using createReport")
sd2Utils.info('##############################################################')	

args = {}
createReport.main(directory_name,globalsfile.outputDirPath,ea_root)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
sd2Utils.info('')
sd2Utils.info('##############################################################')
sd2Utils.info("########## TEST DONE ")
sd2Utils.info("########## Test run time: %s. " % testRunTime)
sd2Utils.info('##############################################################')	
