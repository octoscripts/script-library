'''
Test Description
================
Use a TCP stream to measure RTT.  Find the RTT from the TCP packets by using packet analysis.
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

usePalAsAP = paramsDict["usePalAsAP"]["val"]

if not usePalAsAP:
    # ssid, security and password may be taken from params_system['dut']
    ssidval = 'dutssid'+theBand.replace('g','')
    ssid = paramsDict['dut']['val'][ssidval]
    # valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
    securityval = 'dutsecurity'+theBand.replace('g','')
    security = paramsDict['dut']['val'][securityval]
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

#Restrict to Linux STApals for the time being

palToUseSTA = paramsDict['palToUseSTA']['val']

attensToUse = paramsDict["attensToUse"]["val"]
#Setting attenuation values for attenuators or MPEs:
icnt = 0
for atten in attensToUse:
    icnt += 1
    pc = False
    if icnt == len(attensToUse):pc=True
    sd2Utils.setAtten(atten,paramsDict[atten]['val']['devType'],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=pc)

# Scan AP to find channels set in AP
(scanDict,scanDictRaw,stapalRadio) = sd2Utils.scanAP(palToUseSTA)
if theBand in scanDict:
    primaryChannel = scanDict[theBand]['channel']
else:
    primaryChannel = primaryChannel  #Read in before from the params_test file

#Setting up traffic pairs:
tpDictList = []
if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"
tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, updn, tpDictList)

if usePalAsAP:
    #Use Pal as AP for testing.
    apDictList = []
    apoverride = {"ssid":ssid, "password": password, "security": security }
    apDictList = sd2Utils.setupAP("Pal-6A", theBand, apDictList, type=interface, channel=primaryChannel, apDictOverride=apoverride, pushConfig=False)



#Start sniffing early in order to capture the handshake for decryption
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

sd2Utils.startSniffers(snifStartDictList)

#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }
staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=interface, channel=primaryChannel, staDictOverride=staoverride, pushConfig=True)
targetRadio = staDictList[0]['palRadio']


############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

jsonZipPath = sd2Utils.runAutotest(sleepTime=2)
sd2Utils.stopSniffers()

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED #########################

# NOTE! Report creation requires a createReport.py file. 
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
        import createReport

        print('')
        print('##############################################################')
        print("########## Creating report ")
        print('##############################################################')

        ea_root = sd2Utils.whereIsEA()
        print(">>> Expert Analysis is at {}".format(ea_root))        

        ssid_decode = paramsDict["ssidForDecode"]["val"]
        pwd_decode = paramsDict["pwdForDecode"]["val"]

        createReport.main(directory_name,globalsfile.outputDirPath,ea_root,ssid_decode,pwd_decode)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
