"""
MU-MIMO Test
Run traffic to 3 STApals, first in the same quadrant, then in different quadrants, then back in the same quadrant.  Measure aggregate throughput. Capture and analyze traffic to confirm MU-MIMO operation.
"""

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

#_________________###############  DO NOT MODIFY ANYTHING ABOVE THIS LINE ###############_______________________________

# ##################################################################################	
# ##################################################################################
#	                             Start of main test script
# ##################################################################################
# ##################################################################################

#cRed=   '\033[33m'
#cGreen= '\033[32m'
cRed=cGreen=cNormal='\033[m'
urlIP = paramsDict["oBox_server"]["val"]["publicip"]

# Get list of Pals and attens to use in test so we can check they are available
instList = []
palsToUse = []
n=0
for n in range (1,4):
        palsToUse.append(paramsDict['palToUse'+str(n)]['val'])
# Get Sniffer Pal
instList.append(paramsDict['palToUseSniffer']['val'])

(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]

testUses=paramsDict['testUses']['val']+instList+palsToUse+attenList

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses=testUses)

#Is SnifferRelay running?
SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],False,args=paramsDict['oBox_server']['val']['publicip'])

#Is Basic server running on octoBox server?
address = paramsDict['oBox_server']['val']['publicip']
mgmtport = paramsDict['basicServer_location']['val']['mgmtport']
basicServerRunning = sd2Utils.isWebServiceRunning(address,mgmtport)
if not basicServerRunning:
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    print('>>> ERROR! basic-server.js node server not running on octobox server.')
    print('>>> ERROR! Manually start the service and rerun this script. QUITTING.')
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    sys.exit(1) # Set for SM
else:
        print('>>> basic-server.js node server is running on octobox server.')
############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

scriptLoc = sd2Utils.whereIsScriptRunning()

#Get information about the server
serverMIp = paramsDict["oBox_server"]["val"]["address"]
serverIp  = paramsDict["oBox_server"]["val"]["defaultIp"]
serverParts = serverIp.split(".")

pieces = serverIp.split('.')
ipGateway = pieces[0] + "." + pieces[1] + "." + pieces[2] + "." + "1"

ssid = paramsDict["ssid"]["val"]

eaLocDrop = paramsDict["eaLocation"]["val"]
for item in eaLocDrop:
    if item["selected"]:
        eaLocation = item["value"]
        break

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

if interface != "INTERFACE_AX" and interface != "INTERFACE_AC":
    print("MU-MIMO is a feature of 802.11ac and 802.11ax, but not {}. Stopping.".format(iface))
    sys.exit(2)

bwdrop = paramsDict["bw"]["val"]
for item in bwdrop:
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

ulDlDrop = paramsDict["ulDl"]["val"]
for item in ulDlDrop:
    if item["selected"]:
        ulDl = item["value"]
if(ulDl == 'up'): upLink = True
else: upLink = False
if upLink:
    print(">>> Running uplink traffic")
    print("\nAt the moment, MU-MIMO is not supported in the uplink direction.\n")
    print(">>> STOPPING")
    sys.exit(3)
else: print(">>> Running downlink traffic")
upOrDown = ulDl

iperfMode = paramsDict["iperfMode"]["val"]
if iperfMode!='tcp' and iperfMode!='udp':
    print("{} is not a valid iperf mode.".format(iperfMode))
    iperfMode = None

bitrate = paramsDict["trafficBW"]["val"]
length  = paramsDict["length"]["val"]
parallel= int(paramsDict["parallel"]["val"])
window = paramsDict["window"]["val"]
dscp     = int(paramsDict["dscp"]["val"])
pingPayload = int(paramsDict["pingPayload"]["val"])

realStas = paramsDict['realStas']['val']

############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

############### START SECTION: BUILD THE TEST OBJECT #########################

# Disconnect all boxes in a stack
if 'STACK' in paramsDict['systemConfig']['val']['stackType']:
        sd2Utils.isolateAllBoxes()

time.sleep(5)

#Setting attenuation values for attenuators or MPEs:
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]["val"]["devType"],0,None,63)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseA]["val"]["devType"],0,None,63,pushConfig=True)

#Check to see if we are using the Pal as an AP.  If we are, use the settings for the Pal/AP for the Pal/STAs as well.   To avoid the pain of having to change things all the time.
usePalAsAP = paramsDict["usePalAsAP"]["val"]
palToUseAsAP = paramsDict["palToUseAsAP"]["val"]
paltoUseAsAP = palToUseAsAP.strip()
if usePalAsAP:

    palAsApChannel = paramsDict["palAsApChannel"]["val"]

    print("Going to use {} as the AP.  PalAsAP.".format(palToUseAsAP))

    ssid = paramsDict["palAsApSSID"]["val"]
    ssid = ssid.strip()

    # valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
    secDrop = paramsDict["palAsApSecurity"]["val"]
    for item in secDrop:
        if item["selected"]:
            security = item["value"]
            break

    password = paramsDict["palAsApPassword"]["val"]
    password = password.strip()

    apDictOverride = {"ssid":ssid}
    apDictOverride["security"]=security
    apDictOverride["password"]=password
    apDictOverride["bandwidth"]=bandwidth
    apDictOverride["streams"]=4
    apDictOverride["beamformeeMUEnable"]=True
    apDictOverride["beamformerMUEnable"]=True
    enableOFDMA = paramsDict["enableOFDMA"]["val"]
    apDictOverride["ofdmaDLEnable"] = enableOFDMA
    apDictOverride["ofdmaULEnable"] = enableOFDMA
    #Setting up AP configurations:
    apDictList = []
    apDictList = sd2Utils.setupAP(palToUseAsAP, theBand, apDictList, type=interface, channel=palAsApChannel, streams=streams, apBridge=True, pushConfig=False, apDictOverride=apDictOverride)


print('')
print('##############################################################')
print("########## Setting up Traffic pairs and STAs START ")
print('##############################################################')

#Setting up traffic pairs:
tpDictList = []

if ulDl == "up": updn = "up"
if ulDl == "down": updn = "dn"
tpDictList = sd2Utils.setupTrafficPairs(paramsDict['palToUse1']['val'], theBand, updn, tpDictList,pushConfig=False)
tpDictList = sd2Utils.setupTrafficPairs(paramsDict['palToUse2']['val'], theBand, updn, tpDictList,pushConfig=False)
tpDictList = sd2Utils.setupTrafficPairs(paramsDict['palToUse3']['val'], theBand, updn, tpDictList,pushConfig=True)

if len(realStas)>0:
    for entry in realStas:
        tpDictList = sd2Utils.setupTrafficPairs(entry["alias"], theBand, updn, tpDictList)


#Setting up Pal configurations:
staDictList = []
staoverride = {}
if usePalAsAP:
    staoverride={"ssid":ssid, "password": password, "security": security }
staoverride["bandwidth"] = bandwidth
staDictList = sd2Utils.setupSTA(paramsDict['palToUse1']['val'], theBand, staDictList, type=interface, streams=streams, channel=primaryChannel,staDictOverride=staoverride,pushConfig=False)
staDictList = sd2Utils.setupSTA(paramsDict['palToUse2']['val'], theBand, staDictList, type=interface, streams=streams, channel=primaryChannel,staDictOverride=staoverride,pushConfig=False)
staDictList = sd2Utils.setupSTA(paramsDict['palToUse3']['val'], theBand, staDictList, type=interface, streams=streams, channel=primaryChannel,staDictOverride=staoverride,pushConfig=True)
print('')
print('##############################################################')
print("############ Setting up Traffic pairs and STAs DONE ")
print('##############################################################')

#Setting up sniffers.
#Make a single sniffer for now.  Use group 3.  A sniffer can see everything in the DL, no matter what group, so should be OK.
#Form sniff capture filter
capFilter =''
#capFilter = 'wlan ta '+globalsfile.macAddressFound+' or wlan ra '+globalsfile.macAddressFound	#Look at only from/to STA
#capFilter = 'wlan src '+globalsfile.macAddressFound	#Look at only from/to STA
#capFilter = 'wlan src '+globalsfile.macAddressFound+' or wlan dst '+globalsfile.macAddressFound #Look at only from/to STA
#capFilter =  'not subtype beacon and (wlan src '+globalsfile.macAddressFound+' or wlan dst '+globalsfile.macAddressFound+' or wlan src '+bssid24g+' or wlan dst '+bssid24g+' or wlan src '+bssid5g+' or wlan dst '+bssid5g+')'

# And in other filter from params_test
if paramsDict['sniffFilter']['val'] != '':
        capFilter = capFilter+' and '+paramsDict['sniffFilter']['val']
        print('>>> capFilter: ', capFilter)

print('')
print('##############################################################')
print('##########  Set up Sniffing START '   )
print('##########  sniffChan: ' , primaryChannel)
print('##########  capFilter: ' , capFilter)
print('##############################################################')
snifSetDictList = []
snifDispDictList = []
snifStartDictList = []

(snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(paramsDict['palToUseSniffer']['val'], theBand, bandwidth, primaryChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, mgmtFrames=paramsDict['sniffmgmt']['val'], headerFrames=paramsDict['sniffheader']['val'], filter=capFilter)
print('')
print('##############################################################')
print('##########  Set up Sniffing END '   )
print('##############################################################')
############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################
# Update sniffer Autotest configs and push
sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True) # This also associates STAs

print('')
print('##############################################################')
print('############ Associating STAs START ' )
print('##############################################################')
if theBand == "6g":
        assocWaitTime = 40	# 6 GHz takes longer to associate
else:
        assocWaitTime = 30

for pal in palsToUse:
    # Find radio type
    isApal = None
    try:
        thisPal = paramsDict[pal]["val"]
        if "staPal" in thisPal["devType"]: isApal = True
    except:
        isApal = False

    if "STApal" in pal or isApal:
        getSTA = 'STApal'
        palType = 'staPals'
        if thisPal["devType"] == "staPal7": palType = "staPal7s"
        if paramsDict[pal]['val']['isPal6E']:
            radioValue = "RADIO_2456"
        else:
            radioValue = "RADIO_245"
    else:
        if '24' in palbandDict[pal]:
            radioValue = 'RADIO_24'
        elif '5' in palbandDict[pal]:
            radioValue = 'RADIO_5'
        elif '6' in palbandDict[pal]:
            radioValue = 'RADIO_6'	

    associatedStatus = sd2Utils.waitForAssociation(pal,radioValue,timeToWait=assocWaitTime)
    if not associatedStatus:
        print(">>> Association not completed. Quitting.")
        sys.exit(1) # Set for SM
print('')
print('##############################################################')
print('############ Associating STAs DONE '  )
print('############ STAs associated to %s band.' % theBand)
print('##############################################################')
#print(">>> EXIT @ LINE 349")
#sys.exit()

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Put into a potential MU-MIMO configuration. <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
print('')
print('##############################################################')
updateDict = {"alias":tpDictList[1]["alias"] , "active":False}
print("{} Turn off the 2nd traffic pair {}".format(cGreen,cNormal))
print('>>> updateDict: ', updateDict)
sd2Utils.updateTrafficPair(updateDict)
print("{} Done {}".format(cRed,cNormal))
print('##############################################################')


sd2Utils.startSniffers(snifStartDictList)
# Save timestamp to testresultlog.json
resultDict = {}
resultDict = {'snifferStartTime1':globalsfile.snifferStartTime}
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)	

#print("{} Start the test {}".format(cGreen,cNormal))
sd2Utils.startAutotest()

sd2Utils.waitLoop(15,2)

#print("{} Stopping the test {}".format(cGreen,cNormal))
jsonZipPath = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False)
print(">>> Path to the zip file is " + jsonZipPath)
print(">>> Latest timestamp is " + globalsfile.timeStamp)

#Stop the capture
globalsfile.fileSuffix = 'forTriggers'	# Set pcap filename suffix
pcapFileName = sd2Utils.stopSniffers()
print('')
print('##############################################################')
print(">>> Full path to pcap file: " , pcapFileName)
print('##############################################################')
pcapFileName.rsplit('/',1)
pcapDir = pcapFileName.rsplit('/',1)[0]
pcapFile = pcapFileName.rsplit('/',1)[1]

# Put a copy of the pcap in EA pcapDirectory folder
command = 'echo octoscope | sudo -S cp '+pcapFileName+' '+paramsDict['expertAnalysis_server']['val']['dirpath']+'/pcapDirectory/forTriggers.pcap'
print('\n>>> COPY command: ', command)
os.popen(command)

#Clean up local PCAP files.
command = 'rm ' + directory_name + "*.pcap"
print('\n>>> CLEAN UP command: ', command)
os.popen(command)
command = 'echo octoscope | sudo -S cp '+pcapFileName+' ' + directory_name+'forTriggers.pcap'
print('\n>>> command: ', command)
command = 'echo octoscope | sudo -S chown octoscope:octoscope ' + directory_name+'forTriggers.pcap'
print('\n>>> command: ', command)
os.popen(command)


################################# Put into a potential MU-MIMO configuration. <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

################################# Check to see if from this data you can find evidence of triggers and do a mapping. <<<<<<<<<<<<<<<<<<<
#Use EA to extract the AID list.  Use at most 20K packets for this.  More should not be needed.

baseURL = "http://localhost:8080/pcapAPI"
api_endpoint = baseURL + "?fileName="+pcapFile+"&pcapDir="+pcapDir+"&firstPacket=1&lastPacket=20000&action=getAIDlist"

print('')
print('##############################################################')
print(">>> Running the captured file through a PCAP analysis.  Get the AID list.")
print(">>>This is the API call: {}".format(api_endpoint))
apiResponse = requests.get(api_endpoint,timeout=REST_TIMEOUT)
returnObject = json.loads(apiResponse.text)
#print(returnObject)
apiListResult = returnObject["result"]
#print(apiListResult)
aidsPerBssid = apiListResult["aidsPerBssid"]
#print(aidsPerBssid)
print('')
print('##############################################################')
if len(aidsPerBssid) > 0:
    thisBssid = aidsPerBssid[0]["bssid"]
    #print(thisBssid)
    theseAIDs = aidsPerBssid[0]["AIDs"]
    #print(theseAIDs)

    print(">>> {} For BSSID {} the list of AIDs found is {} {}".format(cGreen,thisBssid,theseAIDs,cNormal))

else:
        print(">>> No AIDs found")
        print('##############################################################')
        sys.exit(12)
print('##############################################################')

AID = "NoAID"
if len(theseAIDs)>0:
        #Set the sniffer to shadow one of the AIDs.
        #Need to be able to control the oBox server, and the staPal.
        serverExec =  "http://" + urlIP + ":8383/exec?command="
        serverSpawn = "http://" + urlIP + ":8383/spawn?command="

        #Configure the sniffer with the desired AIDs
        palMgmtIP = paramsDict[paramsDict['palToUseSniffer']['val']]['val']['address']           
        parts = palMgmtIP.split(".")
        snID = str(parts[len(parts)-1])
        AID = theseAIDs[0]
        BSSID = thisBssid
        curlExec = "curl http://"+palMgmtIP+":8383/exec?command="
        command = "echo octoScope-customer-key-201504271520 | sudo -S octosniff.sh AID " + str(AID) + " " + BSSID + " " + "sn"+snID+"a"+str(AID)
        url = serverExec+curlExec+command
        #print('>>>url: ', url)
        print(">>> For sniffer {}, setting AID to {} and BSSID to {} with command {}".format(paramsDict['palToUseSniffer']['val'],AID,BSSID,url))
        try:
                resp = requests.get(url=url,timeout=REST_TIMEOUT)
                jsn = json.loads(resp.text)
                print('>>>jsn: ', jsn)
        except:
                #print('>>> Failed to change STApal AID. Check port 8383 is in /opt/octobox/network/config-iptables.sh')
                #print('>>> INTERNAL_PORTS or EXTERNAL_PORTS list. Also make sure basic server is running on sniffer STApal.')
                print('>>> Manually execute node basic-server.js on octoBox server from basic-server folder')
                sys.exit(1)

#####################################################################################################################

#Now go in and out of MU-MIMO operation modes, while also capturing in a way that should be able to see HE-MU frames.

print('')
print('##############################################################')
print(">>> {} Turning off the 3rd traffic pair {}".format(cGreen,cNormal))
updateDict = {"alias":tpDictList[2]["alias"] , "active":False}
sd2Utils.updateTrafficPair(updateDict)
print(">>> {} Done {}".format(cRed,cNormal))
print(">>> {} Turning on the 2nd traffic pair {}".format(cGreen,cNormal))
updateDict = {"alias":tpDictList[1]["alias"] , "active":True}
sd2Utils.updateTrafficPair(updateDict)
print(">>> {} Done {}".format(cRed,cNormal))
print(">>> MU-MIMO SHOULD NOT WORK IN THIS MODE")
print('##############################################################')


sd2Utils.startSniffers(snifStartDictList)
# Save timestamp to testresultlog.json
resultDict = {}
resultDict = {'snifferStartTime2':globalsfile.snifferStartTime}
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)	

sd2Utils.startAutotest()
sd2Utils.waitLoop(30,2)

print('')
print('##############################################################')
print(">>> {} Turning on the 3rd traffic pair {}".format(cGreen,cNormal))
updateDict = {"alias":tpDictList[2]["alias"] , "active":True}
sd2Utils.updateTrafficPair(updateDict)
print(">>>{} Done {}".format(cRed,cNormal))
print(">>>{} Turning off the 2nd traffic pair {}".format(cGreen,cNormal))
updateDict = {"alias":tpDictList[1]["alias"] , "active":False}
sd2Utils.updateTrafficPair(updateDict)
print(">>> {} Done {}".format(cRed,cNormal))
print(">>> MU-MIMO SHOULD BE WORKING IN THIS MODE")
print('##############################################################')
sd2Utils.waitLoop(15,2)

if len(theseAIDs) > 1:
        AID = theseAIDs[1]
        BSSID = thisBssid
        curlExec = "curl http://"+palMgmtIP+":8383/exec?command="
        command = "echo octoScope-customer-key-201504271520 | sudo -S octosniff.sh AID " + str(AID) + " " + BSSID + " " + "sn"+snID+"a"+str(AID)
        url = serverExec+curlExec+command
        print('')
        print('##############################################################')
        print(">>> For sniffer {}, setting AID to {} and BSSID to {} with command {}".format(paramsDict['palToUseSniffer']['val'],AID,BSSID,url))
        print('##############################################################')
        resp = requests.get(url=url)
        jsn = json.loads(resp.text)
        print(jsn)

sd2Utils.waitLoop(15,2)

print('')
print('##############################################################')
print(">>> {} Turning off the 3rd traffic pair {}".format(cGreen,cNormal))
updateDict = {"alias":tpDictList[2]["alias"] , "active":False}
sd2Utils.updateTrafficPair(updateDict)
print(">>> {} Done {}".format(cRed,cNormal))
print(">>> {} Turning on the 2nd traffic pair {}".format(cGreen,cNormal))
updateDict = {"alias":tpDictList[1]["alias"] , "active":True}
sd2Utils.updateTrafficPair(updateDict)
print(">>> {} Done {}".format(cRed,cNormal))
print(">>> MU-MIMO SHOULD NOT WORK IN THIS MODE")
print('##############################################################')

sd2Utils.waitLoop(30,2)

print(">>> {} Stopping the test {}".format(cGreen,cNormal))
jsonZipPath = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False)
print(">>> Path to the zip file is " + jsonZipPath)
print(">>> Latest timestamp is " + globalsfile.timeStamp)

#Stop the capture
globalsfile.fileSuffix = "captureWithAid"+str(AID)	# Set pcap filename suffix
pcapFileName = sd2Utils.stopSniffers()
print("\n>>> Full path to pcap file: " , pcapFileName)
pcapFileName.rsplit('/',1)
pcapDir = pcapFileName.rsplit('/',1)[0]
pcapFile = pcapFileName.rsplit('/',1)[1]


# Put a copy of the pcap in EA pcapDirectory folder
command = 'echo octoscope | sudo -S cp '+pcapFileName+' '+paramsDict['expertAnalysis_server']['val']['dirpath']+'/pcapDirectory/'+globalsfile.fileSuffix+'.pcap'
print('>>> command: ', command)
os.popen(command)
#Clean up local PCAP files.
command = 'rm ' + directory_name + "*.pcap";
os.popen(command)
command = 'echo octoscope | sudo -S cp '+pcapFileName+' ' + directory_name+globalsfile.fileSuffix+'.pcap'
print('>>> command: ', command)
os.popen(command)
command = 'echo octoscope | sudo -S chown octoscope:octoscope ' + directory_name+globalsfile.fileSuffix+'.pcap'
print('>>> command: ', command)
os.popen(command)

#print(">>> EXIT @ LINE 542")
#sys.exit()

sd2Utils.setSnifferStandby(paramsDict['palToUseSniffer']['val'], theBand)

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED #########################
import createReport
# Find where Expert Analysis is running for report generation
ea_root = sd2Utils.whereIsEA()

print(">>> Start the HTML report creation process.")
'''
someData = {
    "iface":iface,
    "bandwidth":bandwidth,
    "channel":primaryChannel,
    "upOrDown":upOrDown,
    "nss":streams
    }
'''
createReport.createReport(directory_name,globalsfile.outputDirPath,ea_root)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
