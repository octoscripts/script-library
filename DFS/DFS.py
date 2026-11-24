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

#...................................................................
def freqToChannel(freq):
    # freq is in MHz, and we are converting to the channel number.
    freq = 1*freq
    if freq<3000:
        chNo = (freq-2412)/5 + 1
    else:
        chNo = (freq-5000)/5
    return chNo
#...................................................................
def channelToFreq(channel):
    if channel <= 14:
        freq = (channel-1) *5 + 2412
    else:
        freq = channel*5 + 5000
    return freq
#___________________________________________________________________

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

# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

# Build list for config check
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]

testUses=paramsDict['testUses']['val']+[paramsDict['palToUseSTA']['val'],paramsDict['palToUseSniffer']['val']]+attenList
print(">>> testUses: ", testUses)
# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)

############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

ssid = paramsDict["ssid"]["val"]
ssid = ssid.strip()

bandDrop = paramsDict["band"]["val"]
for item in bandDrop:
    if item["selected"]:
        theBand = item["value"]
        break

primaryChannel = int(paramsDict["primaryChannel"]["val"])
    
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

streams = paramsDict["nss"]["val"]
streams = int(streams)

# valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
secDrop = paramsDict["security"]["val"]
for item in secDrop:
    if item["selected"]:
        security = item["value"]
        break

password = paramsDict["password"]["val"]
password = password.strip()

# ssid, security and password may be taken from params_system['dut']
if ssid == "":
    ssidval = 'dutssid'+theBand.replace('g','')
    ssid = paramsDict['dut']['val'][ssidval]
if security == "FROM_PARAMS_SYSTEM":
    # valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
    securityval = 'dutsecurity'+theBand.replace('g','')
    security = paramsDict['dut']['val'][securityval]
if password == "":
    passwordval = 'dutpass'+theBand.replace('g','')
    password = paramsDict['dut']['val'][passwordval]
    
print('>>> ssid: %s, security: %s, password: %s, band: %s' % (ssid, security, password, theBand))
  
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

time.sleep(5)

usePalAsAp = paramsDict["usePalAsAp"]["val"]
#Use the Pal as the AP for testing purposes.  Not required.
if usePalAsAp:
    apDictOverride = {"ssid":ssid}
    apDictOverride["security"]=security
    apDictOverride["password"]=password
    apDictOverride["dfsEnable"]=True
    apDictList = []
    print("Setting up Pal-6A as an AP.  Override is {}".format(apDictOverride))
    apDictList = sd2Utils.setupAP("Pal-6A", theBand, apDictList, type = interface, channel=primaryChannel, streams= 4, apBridge=True, pushConfig=True, apDictOverride=apDictOverride)
    print("apDictList is is {}".format(apDictList))


#Restrict to Linux STApals for the time being

palToUseSTA = paramsDict['palToUseSTA']['val']

#Setting attenuation values for attenuators or MPEs:
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=True)

# Scan AP to find channels set in AP
'''
(scanDict,scanDictRaw,stapalRadio) = sd2Utils.scanAP(palToUseSTA)
if theBand in scanDict:
    primaryChannel = scanDict[theBand]['channel']
else:
    primaryChannel = primaryChannel  #Read in before from the params_test file
'''

#Setting up traffic pairs:
tpDictList = []
if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"
tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList)

#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }
staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=interface, channel=primaryChannel, staDictOverride=staoverride, pushConfig=True)
targetRadio = staDictList[0]['palRadio']

#Setting up sniffers.

#Is SnifferRelay running?
SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],True,args=paramsDict['oBox_server']['val']['publicip'])

#Make a single sniffer
palToUseSniffer = paramsDict['palToUseSniffer']['val']
snifSetDictList = []
snifDispDictList = []
snifStartDictList = []

(snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer, theBand, paramsDict['snifferBW']['val'], primaryChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=paramsDict['headersOnly']['val'], mgmtFrames=paramsDict['managementOnly']['val'])

# Update sniffer Autotest configs and push
sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True) 

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

sd2Utils.startSniffers(snifStartDictList)
sd2Utils.startAutotest()


#To control the iGen we have to use the basic-server, curl mechanism for now.
serverMgmtIp = paramsDict["oBox_server"]["val"]["publicip"]
execUrl = "http://" + serverMgmtIp + ":8383/exec?command="
spawnUrl = "http://" + serverMgmtIp + ":8383/spawn?command="

#Put iGen commands in here
iGenIP = paramsDict["iGen-A"]["val"]["address"]

URL = "http://" + iGenIP + "/api/wave"
curlPart = "curl http://"+iGenIP+"/api/wave"

URL = execUrl+curlPart
print("Getting iGen status with " + URL)
resp = requests.get(url=URL)
jsn = json.loads(resp.text)
#print(json.dumps(jsn, indent=4,sort_keys=True))

stdout = jsn["stdout"]
print(stdout)
iGenDict = json.loads(stdout)

'''
Here is the curl command to set the iGen
curl -X PUT -d '{"attenuation": 50, "channelWidth": 80, "gapUnit": "microseconds", "gapValue": 100, "guardInterval": "short", "inputFile": "16_TCPPackets.pcap", "interface": "ac", "loop": true, "mode": "playback", "primaryChannel": 36, "priority": "bestEffort", "rate": "9", "secondaryChannel": "40, 44, 48"}' http://172.16.25.1/api/traffic
'''

'''
Let's try using the API to set the waveform generator
curl -X PUT -d 
'{
    "mode":                 "waveform",
    "waveform_mode":        "radar",
    "ZigBeeChannel":        11,
    "frequency":            5400,
    "attenuation":          0,  
    "pulseWidth":           10,
    "pulseWidthUnit":       "nanoseconds",
    "pri":                  16,
    "priUnit":              "microseconds",
    "bri":                  50,
    "briUnit":              "milliseconds",
    "pulsesPerBurst":        1,
    "bursts":                50,
    "continuousBursting":    false,
    "continuousRadar":       false,
    "loop":                  0,
    "loopDelay":             10,
    "loopDelayUnit":         "seconds",
    "sweepStart":            2412,
    "sweepEnd":              2472,
    "swepStep":              5,
    "dwell":                 500,
    "dwellUnit":             "microseconds",
    "csvFile":               "/waveform/bluetooth_low_energy.csv",
    "RadarType":             "radar0"
}' http://172.16.25.1/api/wave


mode value can be one of the following values:

startup - waveform interference is running
standby - nothing is running, device is idle
waveform - initialization phase
playback - 802.11 interference is running
attenuation value in dB. Determines the power level of the emitted signal.

waveform_mode denotes the type of interference and can be one of the following values:

btle Bluetooth low energy (BTLE)
babymonitor baby monitor
uwaveoven microvawe oven
802_11FHSS 802.11FHSS
zigbee ZigBee
csv custom waveform profile from the csvFile
radar radar
pulse pulse
cw continuous wave
sweep frequency sweep
frequency - Frequency of signal being generated, in megahertz. Applies to radar, pulse and cw modes.

'''

apChannel = paramsDict["primaryChannel"]["val"]
apFreq = channelToFreq(apChannel)
print("The AP channel is {}, and so the frequency is {}".format(apChannel,apFreq))

#To get the string version of the dictionary, use json.dumps
iGenString = json.dumps(iGenDict)
print(iGenString)

iGenDict["mode"] = "waveform"
iGenDict["waveform_mode"] = "radar"
iGenDict["frequency"] = apFreq
iGenDict["attenuation"] = 0
iGenDict["RadarType"] = "radar1"

iGenString = json.dumps(iGenDict)
curlPart = "curl -X PUT -d '" + iGenString + "' " + "http://"+iGenIP+"/api/wave"

URL = execUrl + curlPart
    
#print("Putting URL {} with data {}".format(URL,iGenUpdate))
#resp = requests.put(URL,json=iGenUpdate)
#jsn = json.loads(resp.text)
#print(jsn)
print("Putting iGen data using URL {}".format(URL))
resp = requests.get(url=URL)
jsn = json.loads(resp.text)
print(json.dumps(jsn, indent=4,sort_keys=True))

#Give it time for the iGen start up, and for the DFS to take hold.
modeNow = "WhoCares"
URL = "http://" + iGenIP + "/api/wave"
curlPart = "curl http://"+iGenIP+"/api/wave"
URL = execUrl+curlPart
print("Getting iGen status with " + URL)
while modeNow != "waveform":
    resp = requests.get(url=URL)
    jsn = json.loads(resp.text)
    stdout = jsn["stdout"]
    #print(stdout)
    iGenNow = json.loads(stdout)
    modeNow = iGenNow["mode"]
    time.sleep(1)

print("The iGen mode is finally {}".format(modeNow))

#Give a little more time for the DFS to kick in.
time.sleep(10)

jsonZipPath = sd2Utils.stopAutotest()
pcapFile = sd2Utils.stopSniffers()

#Don't forget to shut off the iGen
curlPart = "curl -X PUT -d '{\"mode\":\"standby\"}' http://172.16.25.1/api/traffic"
URL = execUrl + curlPart
print("Putting iGen data using URL {}".format(URL))
resp = requests.get(url=URL)
jsn = json.loads(resp.text)
print(json.dumps(jsn, indent=4,sort_keys=True))

print("PCAP file is located here: " + pcapFile)

haveCreateReport = False
if os.path.isfile(directory_name + "createReport.py"): haveCreateReport = True
if haveCreateReport:
    import createReport
    eaLocation = paramsDict["eaLocation"]["val"]
    ea_root = "http://octapi.tech/"
    if eaLocation == "local": ea_root = "http://localhost:8080/"
    createReport.main(directory_name,jsonZipPath,pcapFile,ea_root)



############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED #########################


testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
