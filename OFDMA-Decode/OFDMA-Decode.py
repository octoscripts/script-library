"""
OFDMA Decode Test
This test runs traffic to multiple STAs, checking for OFDMA operation. It first finds AIDs assigned to STAs, then matches AIDs to MAC addresses.  Sniffers (with associated AIDs) are then assigned to each STA.  Traffic is then simultaneously captured from all clients using the complete set of sniffers.
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
'''
markdict = {"Tom":67, "Tina": 54, "Akbar": 87, "Kane": 43, "Divya":73}
marklist = sorted(markdict.items(), key=lambda x:x[1])
sortdict = dict(marklist)
print('>>> sortdict: ',sortdict)
sys.exit()

theList = []
thebssdict = {}
bssidFoundList = [('80:cc:9c:2c:67:ae', -51),('80:cc:9c:2c:67:af', -55)]
print('>>> bssidFoundList: ', bssidFoundList)
for bss in bssidFoundList:
        print('>>> bss: ', bss)
        thebssdict = dict(bss)
        print('>>> thebssdict: ', thebssdict)
        theList.append(thebssdict)
        print('>>> theList: ', theList)
sys.exit()
'''
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
		sd2Utils.info('>>> test_params: ', test_params)
	paramsDict.update(test_params)
	
	if 'apToTest' in paramsDict:
		apToTest = paramsDict['apToTest']['val']
	else:
		sd2Utils.info('>>> No apToTest specified. Setting AP 1')
		apToTest = 1
	sd2Utils.info("\n>>>paramsDict apToTest: ", apToTest)
else:
	sd2Utils.info('>>> No apToTest specified. Setting AP 1')
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

#_____________________###############  DO NOT MODIFY ANYTHING ABOVE THIS LINE ###############____________________________________

# ##################################################################################	
# ##################################################################################
#	                            Start of main test script
# ##################################################################################
# ##################################################################################

cRed=   '\033[m'	#'\033[33m'
cGreen= '\033[m'	#'\033[32m'
cNormal='\033[m'

# Find where Expert Analysis is running for report generation
ea_root = sd2Utils.whereIsEA()
print("EA is at {}".format(ea_root))

# Get list of Pals and attens to use in test so we can check they are available
palsToUse = []
STApalPairs = paramsDict['STApalPairs']['val']
#print("The STApalPairs: {}".format(STApalPairs))

for i in range(len(STApalPairs)):
        #print('>>> pair:', STApalPairs[i])
        palsToUse.append(STApalPairs[i][0])
        palsToUse.append(STApalPairs[i][1])

#print("The pals to use {}".format(palsToUse))    

(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]
attensToUse = paramsDict["attensToUse"]["val"]
attenList = attensToUse

testUses=paramsDict['testUses']['val']+palsToUse+attenList

# Check that system can support the test
#sd2Utils.checkSystemConfig(testUses=testUses)

#Is SnifferRelay running?
SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],False,args=paramsDict['oBox_server']['val']['publicip'])


urlIP = paramsDict["oBox_server"]["val"]["publicip"]

#-----------------------------------------------------------------------------------------------------------------
def formatMAC(mac):
    fMAC = mac
    #fMAC = fMAC.replace(/\./g,":")
    while "." in fMAC: fMAC = fMAC.replace(".",":")
    fMAC = fMAC.upper()
    if fMAC[len(fMAC)-1]==":": fMAC = fMAC[:len(fMAC)-1]
    fMAC = fMAC.strip()

    return fMAC

startTime = time.time()

#The following are example sections that are appropriate for building automated test cases
############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

# Find where script is running.
scriptLoc = sd2Utils.whereIsScriptRunning()

bandDrop = paramsDict["band"]["val"]
for item in bandDrop:
    if item["selected"]:
        theBand = item["value"]
        break

primaryChannel = int(paramsDict["primaryChannel"]["val"])

streams = int(paramsDict["nss"]["val"])

ifaceDrop = paramsDict["iface"]["val"]
for item in ifaceDrop:
    if item["selected"]:
        interface = item["value"]
        break

bwdrop = paramsDict["bw"]["val"]
for item in bwdrop:
    if item["selected"]:
        bandwidth = item["value"]
        break

if "24" in theBand:
    ssid     = paramsDict["dut"]["val"]["dutssid24"]
    security = paramsDict["dut"]["val"]["dutsecurity24"]
    password = paramsDict["dut"]["val"]["dutpass24"]
elif "5" in theBand:
    ssid     = paramsDict["dut"]["val"]["dutssid5"]
    security = paramsDict["dut"]["val"]["dutsecurity5"]
    password = paramsDict["dut"]["val"]["dutpass5"]
elif "6" in theBand:
    ssid     = paramsDict["dut"]["val"]["dutssid6"]
    security = paramsDict["dut"]["val"]["dutsecurity6"]
    password = paramsDict["dut"]["val"]["dutpass6"]
    
ulDlDrop = paramsDict["ulDl"]["val"]
for item in ulDlDrop:
    if item["selected"]:
        updn = item["value"]

if updn == 'up': print(">>> Running uplink traffic")
else: print(">>> Running downlink traffic")

trafficTypeDrop = paramsDict["trafficType"]["val"]
for item in trafficTypeDrop:
    if item["selected"]:
        trafficType = item["value"]

iperfModeDrop = paramsDict["iperfMode"]["val"]
for item in iperfModeDrop:
    if item["selected"]:
        iperfMode = item["value"]

#Get information about the server
serverMIp = paramsDict["oBox_server"]["val"]["address"]
serverIp  = paramsDict["oBox_server"]["val"]["defaultIp"]

pingInterval = paramsDict["pingInterval"]["val"]
trafficBW = paramsDict["trafficBW"]["val"]
length = paramsDict["length"]["val"]
parallel = paramsDict["parallel"]["val"]
window = paramsDict["window"]["val"]
trafficAdvanced = paramsDict["trafficAdvanced"]["val"]
useNagles = paramsDict["useNagles"]["val"]
setMss = paramsDict["setMss"]["val"]
dscp = paramsDict["dscp"]["val"]
isochronous = paramsDict["isochronous"]["val"]
iso_gap = paramsDict["iso_gap"]["val"]
iso_mean = paramsDict["iso_mean"]["val"]
iso_mean_units_drop = paramsDict["iso_mean_units"]["val"]
for item in iso_mean_units_drop:
    if item["selected"]:
        iso_mean_units = item["value"]
        break
iso_mean = str(iso_mean) + iso_mean_units
iso_stdev = paramsDict["iso_stdev"]["val"]
iso_fps = paramsDict["iso_fps"]["val"]


############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

############### START SECTION: BUILD THE TEST OBJECT #########################

time.sleep(5)

#Setting attenuation values for attenuators or MPEs:
'''
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63)
#special case of using Pal-6B instead of Pal-6A.
sd2Utils.setAtten("QA-D",paramsDict["QA-D"]["val"]["devType"],0)
'''
for atten in attensToUse:
    sd2Utils.setAtten(atten,paramsDict[atten]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63)

#Restrict to Linux STApals for the time being
numSTApals = paramsDict["numSTApals"]["val"]
if numSTApals > len(STApalPairs):
    print(">>> Can only create {} OFDMA STApals with sniffers at this time.".format(len(STApalPairs)))
    numSTApals = len(STApalPairs)

staList = []
snifferList = [] 
for i in range(0,numSTApals):
        staList.append(STApalPairs[i][0])
        snifferList.append(STApalPairs[i][1])

print(">>> These are the STA STApals: ", staList)
print(">>> These are the sniffer STApals: ", snifferList)

realStaPairs = paramsDict["realStaPairs"]["val"]
realStaList = []
for entry in realStaPairs:
    realStaList.append(entry["alias"])
    snifferList.append(entry["sniffer"])
if len(realStaList)>0:
    print("Real STAs in the test are: {}".format(realStaList))
    print("Updated list of sniffers is: {}".format(snifferList))

#Is Basic server running on octoBox server?
sd2Utils.checkBasicServerOnOBox()

serverExec =  "http://" + urlIP + ":8383/exec?command="
for sniffer in snifferList:
        print('\n>>> Checking that basic server is running on sniffer STApal %s.' % sniffer)
        palMgmtIP = paramsDict[sniffer]['val']['address']
        url = serverExec+"curl http://"+palMgmtIP+":8383/"
        resp = requests.get(url=url, timeout=REST_TIMEOUT)
        jsn = json.loads(resp.text)
        print('>>> jsn: ', jsn)
        if jsn["status"] and jsn["status"] =="OK" and "reached" in jsn["stdout"]:
                print('>>> basic-server is running on STApal %s @ %s.' % (sniffer,palMgmtIP))
        else:
                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                print('>>> ERROR! basic-server.js node server not running on STApal %s @ %s.' % (sniffer,palMgmtIP))
                print('>>> ERROR! Manually start the service and rerun this script. QUITTING.')
                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                sys.exit(41)

print('')
print('##############################################################')
print("########## Setting up Traffic pairs START ")
print('##############################################################')
if "6" in theBand:
        assocWaitTime = 40	# 6 GHz takes longer to associate
else:
        assocWaitTime = 30

tpDictListSTA = []    
for sta in staList:
        print('>>> sta: ', sta)
        pc = False
        if sta == staList[len(staList)-1]: pc=True
        tpDict = {}
        tpDict["trafficType"] = trafficType
        tpDict["udp"] = iperfMode
        tpDict["bitrate"] = trafficBW
        tpDict["length"] = length
        tpDict["ipStreams"] = parallel
        tpDict["window"] = window
        tpDict["interval"] = pingInterval
        tpDict["advanced"] = trafficAdvanced
        if tpDict["advanced"]:
            tpDict["isochronous"] = isochronous
            tpDict["dscp"] = dscp
            tpDict["ipg"] = iso_gap
            tpDict["mean"] = iso_mean
            tpDict["stdev"] = iso_stdev
            tpDict["fps"] = iso_fps            
        tpDictListSTA = sd2Utils.setupTrafficPairs(sta, theBand, updn, tpDictListSTA, tpDictOverride=tpDict, pushConfig=pc, tType=trafficType)

if len(realStaList)>0:
    for entry in realStaPairs:
        serverSide={"alias":"Server","managementAddress":paramsDict['oBox_server']['val']['address'],"trafficAddress":paramsDict['oBox_server']['val']['defaultIp'],
                    "devType":"server","radio":"","linkMonitor":False}
        otherSide={"alias":entry["alias"],"managementAddress":entry["IP"],"trafficAddress":entry["IP"],"devType":entry["devType"]+"Endpoint",
                   "radio":"","iperfPort":entry["port"],"linkMonitor":False}
        if updn == "up":
            toSide = serverSide
            fromSide = otherSide
            pairalias = entry["alias"] + "2Server"
        else:
            toSide = otherSide
            fromSide = serverSide
            pairalias = "Server2" + entry["alias"]
        updateDict = {
            "to": toSide,
            "from": fromSide,
            "settlingTime": paramsDict['settlingTime']['val'],
            "active": True,
            "alias": pairalias,
            "bitrate": trafficBW,
            "interval": pingInterval,
            "trafficType": trafficType,
            "udp": iperfMode,
            "ipVersion": "ipv4",
            "ipStreams": parallel,
            "window": window,
            "length": length,
            "advanced": trafficAdvanced,
            "dscp": dscp,
            "isochronous": isochronous
        }
        if updateDict["isochronous"]:
            updateDict["ipg"] = iso_gap
            updateDict["mean"] = iso_mean
            updateDict["stdev"] = iso_stdev
            updateDict["fps"] = iso_fps

        print("Adding real traffic pair to list:  {}".format(updateDict))
        tpDictListSTA.append(updateDict.copy())
    print("Pushing latest copy of traffic pair list to the test configuration.")
    sd2Utils.updateAutotestInst(tpDictListSTA, "trafficPairs", pushConfig=True)
    
#print('>>> tpDictListSTA: ', tpDictListSTA)
print('')
print('##############################################################')
print("########## Setting up Traffic pairs DONE ")
print('##############################################################')
print('')
print('##############################################################')
print('############ Check for multiple APs. This test can be run on only one AP.' )
print('##############################################################')



usePalAsAP = paramsDict["usePalAsAP"]["val"]
if usePalAsAP:
    palToUse = paramsDict["PalToUseAsAP"]["val"]
    band = theBand
    ssid = paramsDict["PalAPssid"]["val"]    
    # valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
    secDrop = paramsDict["PalAPsecurity"]["val"]
    for item in secDrop:
        if item["selected"]:
            security = item["value"]
            break
    password = paramsDict["PalAPpassword"]["val"]    
    apDictList = []
    override = {"ssid":ssid,"security":security,"password":password,"bandwidth":bandwidth}
    sd2Utils.setupAP(palToUse, band, apDictList, type = "INTERFACE_AX", channel=primaryChannel, streams= 4, apBridge= True, pushConfig=False, apDictOverride=override)

#Scan with a LINUX stapal.  Find the first one in the staList.
#print("Here is staList {}".format(staList))
firstLinux = None
for s in range(0,len(staList)):
    #print("Checking {}".format(staList[s]))
    #print("What is it? {}".format(staList[s][0]))
    if staList[s][0] == "L":
        firstLinux = s
        break
print("The first Linux STApal in the list is {}, {}".format(firstLinux,staList[firstLinux]))

# Associate one STA for scanning
staDictList = []
override = {}
if usePalAsAP:
    override = {"ssid":ssid,"security":security,"password":password}
staDictList = sd2Utils.setupSTA(staList[firstLinux], theBand, staDictList, type=interface, streams=streams, channel=primaryChannel, staDictOverride=override, pushConfig=True)
radioValue = staDictList[0]['palRadio']
print('>>> staDictList: ', staDictList)
associatedStatus = sd2Utils.waitForAssociation(staList[firstLinux],radioValue,timeToWait=assocWaitTime)
if not associatedStatus:
        print(">>> Association not completed. QUITTING.")
        sys.exit(1) # Set for SM

theRssiLimit = -55
if "rssiLimit" in paramsDict: theRssiLimit = int(paramsDict["rssiLimit"]["val"])

bssidFoundDict = sd2Utils.findChannelBSSIDs(staList[firstLinux],staDictList[0]['palRadio'],primaryChannel,staDictList[0]['ssid'],rssiLimit=theRssiLimit)
print(bssidFoundDict)
bssidToUse = list(bssidFoundDict.keys())[0]
print('>>> bssidToUse: ', bssidToUse)

print('')
print('##############################################################')
print("########## Setting up STAs START ")
print('##############################################################')
#Setting up STAs:
override = {}
if usePalAsAP:
    override = {"ssid":ssid,"security":security,"password":password}
for sta in staList:
        pc = False
        if sta == staList[len(staList)-1]: pc=True
        print("Using override: {}".format(override))
        staDictList = sd2Utils.setupSTA(sta, theBand, staDictList, type=interface, streams=streams, channel=primaryChannel, bssid=bssidToUse, staDictOverride=override, pushConfig=pc)
#print('>>> staDictList: ', staDictList)
print('')
print('##############################################################')
print("############ Setting up STAs DONE ")
print('##############################################################')

#Setting up sniffers.
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

for sniffer in snifferList:
        (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(sniffer, theBand, bandwidth, primaryChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, mgmtFrames=paramsDict['sniffmgmt']['val'], headerFrames=paramsDict['sniffheader']['val'], filter=capFilter)
print('>>> snifSetDictList: ', snifSetDictList)

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

palBoxMACs = {}
for pal in staList:
        # Find radio type
        theType = None
        theType = paramsDict[pal]['val']['devType']
        if "STApal" in pal or "stapal" in theType.lower():
                getSTA = 'STApal'
                palType = 'staPals'
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
        #Make a list of all possible MACs that should be in these traces.  So all MACs in the palBox.

        #palBoxMACs.update({pal:globalsfile.macAddressFound})
        palBoxMACs.update({pal:{'macaddress':globalsfile.macAddressFound,'address':paramsDict[pal]['val']['address']}})
        if not associatedStatus:
                print(">>> Association not completed. QUITTING.")
                sys.exit(1) # Set for SM
print ('>>> palBoxMACs: ', palBoxMACs)
realMACs = {}
for entry in realStaPairs:
    realMACs[entry["alias"]] = {'macaddress':entry["MAC"],'address':entry["IP"]}
if len(realStaPairs)>0: print(">>> realMACs: {}".format(realMACs))

print('')
print('##############################################################')
print('############ Associating STAs DONE '  )
print('############ STAs associated to %s band.' % theBand)
print('##############################################################')

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### END SECTION: BUILD THE TEST OBJECT #########################

print('')
print('##############################################################')
print('############ RUN A TEST DESIGNED TO FIGURE OUT THE AIDS IN USE' )
print('##############################################################')

print(">>> Note that you can search for Triggers yourself in wireshark with wlan.fc.type_subtype == 0x0012")
# Set up a single sniffer.  All we need in order to find the AIDs.  Pick the first one.
print('>>> snifStartDictList: ', snifStartDictList)
globalsfile.fileSuffix = 'allAIDs'	# Set zip and pcap filename suffix
sd2Utils.startSniffers([snifStartDictList[0]])
sd2Utils.startAutotest()

sd2Utils.waitLoop(10,2)

jsonZipPath = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False)
print(">>> Path to the zip file is " + jsonZipPath)

pcapFileName = sd2Utils.stopSniffers()
#print("\n>>> Full path to pcap file: " , pcapFileName)
pcapFileName.rsplit('/',1)
pcapDir = pcapFileName.rsplit('/',1)[0]
print("\n>>> pcapDir: " , pcapDir)
pcapFile = pcapFileName.rsplit('/',1)[1]
print("\n>>> pcapFile: " , pcapFile)

# Put a copy of the pcap in EA pcapDirectory folder
command = 'echo octoscope | sudo -S cp '+pcapFileName+' '+paramsDict['expertAnalysis_server']['val']['dirpath']+'/pcapDirectory/'+pcapFile
print('\n>>> copy to EA pcapDirectory folder command: ', command)
os.popen(command)


print('')
print('##############################################################')
print('############ Use EA to extract the AID list' )
print('##############################################################')

################################# Check to see if from this data you can find evidence of triggers and do a mapping. <<<<<<<<<<<<<<<<<<<
#Use EA to extract the AID list.  Use at most 20K packets for this.  More should not be needed.

baseURL = ea_root+"pcapAPI"
api_endpoint = baseURL + "?fileName="+pcapFile+"&pcapDir="+pcapDir+"&firstPacket=1&lastPacket=10000&action=getAIDlist"

print(">>>Running the captured file through a PCAP analysis.  Get the AID list.")
print(">>>This is the API call: {}".format(api_endpoint))
apiResponse = requests.get(api_endpoint, timeout=REST_TIMEOUT)
returnObject = json.loads(apiResponse.text)
#print(returnObject)
apiListResult = returnObject["result"]
#print('\n>> apiListResult: ', apiListResult)
print('>> aidsPerBssid: ', apiListResult["aidsPerBssid"])

theseAIDs = []
for dict in apiListResult["aidsPerBssid"]:
        #print('>>> dict: ', dict)
        #print(">>> dict['bssid'].lower(): ", dict['bssid'].lower())
        if dict['bssid'].lower() == bssidToUse:
                theseAIDs = dict['AIDs']
                print('')
                print('##############################################################')
                print(">>> {} For BSSID {} the list of AIDs found is {} {}".format(cGreen,bssidToUse,theseAIDs,cNormal))
                print('##############################################################')
if not theseAIDs:
        print(">>> No AIDs found for BSSID %s. QUITTING." % bssidToUse)
        sys.exit(12)

print('')
print('##############################################################')
print('############ USING THE SAME CAPTURE, MAP AIDS TO MACS IF POSSIBLE' )
print('##############################################################')

#With the same capture, let's see how we are able to do at finding the AID-to-MAC mapping
Aid2MacMap = {}
for aid in theseAIDs: Aid2MacMap[aid] = None

#How many packets are there?
#api_endpoint = baseURL + "?fileName="+pcapFile+"&action=getTotalPacketCount"
api_endpoint = baseURL + "?fileName="+pcapFile+"&pcapDir="+pcapDir+"&action=getTotalPacketCount"
print(">>> Running the captured file through a PCAP analysis.  Get the packet count.")
#if paramsDict['debug']['val']:
print(">>> This is the API call: {}".format(api_endpoint))

apiResponse = requests.get(api_endpoint, timeout=REST_TIMEOUT)
returnObject = json.loads(apiResponse.text)
#print('\n>>> apiResponse: ',apiResponse )
print('\n>>> returnObject: ',returnObject )
totalPacketCount = int(returnObject["result"])
#totalPacketCount = 40000	# Four passes should be enough
print(">>> There are a total of {} packets in this capture.".format(totalPacketCount))

startAt = 0
step = 10000
endAt = startAt + step
done = False

#At some point it becomes obvious that using the existing capture is not going to cut it, and it would just be better to move on and do the focused sniffer.  Set that limit.
onlyTryThisMany = totalPacketCount
onlyTryThisMany = 50000

while not done:
        #In small chunks, look to see if you can get a good mapping.
        api_endpoint = baseURL + "?fileName="+pcapFile+"&pcapDir="+pcapDir+"&action=getAID2MAC&firstPacket=" + str(startAt) + "&lastPacket=" + str(endAt)
        print('')
        print('##############################################################')
        print(">>> Running the captured file through a PCAP analysis.  Get the AID2MAC map.")
        if paramsDict['debug']['val']:
                print(">>> This is the API call: {}".format(api_endpoint))

        apiResponse = requests.get(api_endpoint, timeout=REST_TIMEOUT)
        returnObject = json.loads(apiResponse.text)
        #thisBssid = thisBssid.upper()
        thisBssid = bssidToUse.upper()

        multiMap = returnObject["result"]["multiMap"]
        for map in multiMap:
                bssid = map["bssid"].upper()
                if bssid == thisBssid:
                    useMap = map["map"]
                    for mapping in useMap:
                        if mapping["aid"] in Aid2MacMap: Aid2MacMap[mapping["aid"]] = mapping["mac"]

        print("{}>>> Current AID to MAC map is {} {}".format(cGreen,Aid2MacMap,cNormal))

        done = True
        for key in Aid2MacMap:
                if Aid2MacMap[key] == None and endAt< totalPacketCount:
                        startAt += step
                        endAt += step
                        print(">>> No result yet for %s. Continue getAID2MAC analysis from packet %s to %s." % (key,startAt,endAt))
                        done = False
                        if startAt >= onlyTryThisMany: done = True            
                        break
print('##############################################################')

print('')
print('##############################################################')
print("############ USING ONE SNIFFER, CYCLE THROUGH AIDS TO GET" )
print("############ ANY MAPPING THAT HASN'T BEEN FOUND" )
print('##############################################################')

#Now, the next thing to do is to run a short test for each of those AIDs, and try to figure out the MAC address associated.
#But only do this for AIDs for which you don't have a map.

#Set the sniffer with the AIDs and the BSSID
#Need to be able to control the oBox server, and the staPal.

#serverExec =  "http://" + urlIP + ":8383/exec?command="
serverSpawn = "http://" + urlIP + ":8383/spawn?command="
sniffer = snifStartDictList[0]
palMgmtIP = sniffer["palAddress"]

pbm = []
for pal in palBoxMACs: pbm.append(formatMAC(palBoxMACs[pal]["macaddress"]))

for aid in Aid2MacMap:
        if Aid2MacMap[aid] != None:
                print("{}>>> Mapping already exists for AID {}, {}. {}".format(cGreen,aid,Aid2MacMap[aid],cNormal))
                continue
        else:
                #Configure the single sniffer with the desired AID
                id = 0
                #sniffer = snifStartDictList[0]
                #print('>>> sniffer: ', sniffer)
                print(">>> Need to find the mapping for AID {}. Using sniffer {} @ {}".format(aid,sniffer["probeID"],sniffer["palAddress"]))
                #palMgmtIP = sniffer["palAddress"]
                url = serverExec+"curl http://"+palMgmtIP+":8383/"
                resp = requests.get(url=url, timeout=REST_TIMEOUT)
                jsn = json.loads(resp.text)
                print('>>> jsn: ', jsn)
                if jsn["status"] and jsn["status"] =="OK" and "reached" in jsn["stdout"]:
                        print(">>> basic-server is running on STApal {}".format(palMgmtIP))
                else:
                        print(">>> basic-server is not running on STApal {}.  It needs to be. QUITTING.".format(palMgmtIP))
                        sys.exit(41)

                parts = palMgmtIP.split(".")
                snID = str(parts[len(parts)-1])
                AID = aid
                BSSID = thisBssid
                curlExec = "curl http://"+palMgmtIP+":8383/exec?command="
                command = "echo octoScope-customer-key-201504271520 | sudo -S octosniff.sh AID " + str(AID) + " " + BSSID + " " + "sn"+snID+"a"+str(AID)
                url = serverExec+curlExec+command
                print("\n>>> For sniffer {}, setting AID to {} and BSSID to {} with command {}".format(sniffer,AID,BSSID,url))
                resp = requests.get(url=url, timeout=REST_TIMEOUT)
                jsn = json.loads(resp.text)
                #print('>>> STApal GET result: ', jsn)

                globalsfile.fileSuffix = "_aid_"+str(aid)	# Set pcap and zip file suffix
                # Start up a single sniffer.  All we need in order to find the AIDs.  Pick the first one.
                sd2Utils.startSniffers([snifStartDictList[0]])
                sd2Utils.startAutotest()

                sd2Utils.waitLoop(10,2)

                jsonZipPath = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False)
                print('')
                print('##############################################################')
                print("{}>>> Test to find the MAC mapping for aid {} is done! {}".format(cGreen,aid,cNormal))
                print(">>> Path to the zip file is " + jsonZipPath)
                print('##############################################################')

                pcapFileName = sd2Utils.stopSniffers()
                #print("\n>>> Full path to pcap file: " , pcapFileName)
                pcapFileName.rsplit('/',1)
                pcapDir = pcapFileName.rsplit('/',1)[0]
                print("\n>>> pcapDir: " , pcapDir)
                pcapFile = pcapFileName.rsplit('/',1)[1]
                print("\n>>> pcapFile: " , pcapFile)

                # Put a copy of the pcap in EA pcapDirectory folder
                command = 'echo octoscope | sudo -S cp '+pcapFileName+' '+paramsDict['expertAnalysis_server']['val']['dirpath']+'/pcapDirectory/'+pcapFile
                print('\n>>> copy to EA pcapDirectory folder command: ', command)
                os.popen(command)

                # Use EA to find HE-MU and HE-TRIG packets
                api_endpoint = ea_root + "parsePCAP?fileName="+pcapFile+"&pcapDir="+pcapDir
                print('')
                print('##############################################################')
                print("##### Using EA to find HE-MU and HE-TRIG packets")
                print("##### Running the captured file through a PCAP analysis.  Get the packet list.")
                print("##### This is the API call: {}".format(api_endpoint))
                print('##############################################################')
                apiResponse = requests.get(api_endpoint, timeout=REST_TIMEOUT)
                returnObject = json.loads(apiResponse.text)
                #print('>>> returnObject: ')
                #pp.pprint(returnObject)

                totalPackets = returnObject["totalPackets"]
                print(">>> Total packets to analyze: {} ".format(totalPackets))
                thePackets = returnObject["fields"]
                heTrigs = []
                heMUs = []
                for packet in thePackets:
                        if "HEdata" in packet:
                                if packet["HEdata"] == None: continue
                                if "PPDUformat" in packet["HEdata"]:
                                    if packet["HEdata"]["PPDUformat"] == 2:
                                        if "receiverAddress" in packet:
                                            ra = formatMAC(packet["receiverAddress"])
                                            #print("Looking for {} in {}".format(ra,palBoxMACs))
                                            if ra in pbm:  #Only capture devices that are actually IN the palBox.  Not interested in other stuff.
                                                heMUs.append(packet["receiverAddress"])
                                    if packet["HEdata"]["PPDUformat"] == 3:
                                        if "transmitterAddress" in packet:
                                            ta = formatMAC(packet["transmitterAddress"])
                                            #print("Looking for {} in {}".format(ta,palBoxMACs))
                                            if ta in pbm:  #Only capture devices that are actually IN the palBox.  Not interested in other stuff.
                                                heTrigs.append(packet["transmitterAddress"])
        #print(heMUs)
        #print(heTrigs)

                heMUcount = {}
                for heMU in heMUs:
                        if heMU in heMUcount: heMUcount[heMU] += 1
                        else: heMUcount[heMU] = 1
                #print (heMUcount)
                max = -1
                maxMU = None
                for key in heMUcount:
                        if "..." in key: continue
                        if(heMUcount[key])>max:
                                maxMU = key
                                max = heMUcount[key]
                print(">>> Max of {} for {} ".format(max,maxMU))
                maxMUcnt = max

                heTRIGcount = {}
                for heTrig in heTrigs:
                        if heTrig in heTRIGcount: heTRIGcount[heTrig] += 1
                        else: heTRIGcount[heTrig] = 1
                        #print (heTRIGcount)
                max = -1
                maxTrig = None
                for key in heTRIGcount:
                        if "..." in key: continue
                        if(heTRIGcount[key])>max:
                                maxTrig = key
                                max = heTRIGcount[key]
                print(">>> Max of {} for {} ".format(max,maxTrig))
                maxTRIGcnt = max

                theMAC = maxMU
                if maxMUcnt>maxTRIGcnt: theMAC = maxMU
                elif maxTRIGcnt>maxMUcnt: theMAC = maxTrig

                print("{}>>> For AID {}, the MAC address is {} {}".format(cGreen,aid,theMAC,cNormal))
                Aid2MacMap[aid] = theMAC

print('')
print('##############################################################')
print("{}##### The final AID2MAC map is {} {}".format(cGreen,Aid2MacMap,cNormal))
print('##### palBoxMACs: ', palBoxMACs)
print('##############################################################')

#Put the AID info into palBoxMACs
for pal in palBoxMACs:
    theMAC = palBoxMACs[pal]["macaddress"]
    for aid in Aid2MacMap:
        if formatMAC(Aid2MacMap[aid]) == formatMAC(theMAC):            
            palBoxMACs[pal]["aid"] = aid
            break
print('\n##############################################################')
print('##### palBoxMACs: ', palBoxMACs)
print('##############################################################')

if len(realStaPairs)>0:
    for entry in realMACs:
        theMAC = realMACs[entry]["macaddress"]
        for aid in Aid2MacMap:
            if formatMAC(Aid2MacMap[aid]) == formatMAC(theMAC):
                realMACs[entry]["aid"] = aid
                break
    print("\n###############################################");
    print("#######  realMACs: {}".format(realMACs))
    print("###############################################\n");

#Put the associated sniffer into palBoxMACs
for pal in palBoxMACs:
    for i in range(len(STApalPairs)):
        if STApalPairs[i][0] == pal:
            palBoxMACs[pal]["snifferName"] = STApalPairs[i][1]
            break
print('\n##############################################################')
print('##### palBoxMACs: ', palBoxMACs)
print('##############################################################')

if len(realStaPairs)>0:
    for entry in realMACs:
        for i in range(len(realStaPairs)):
            if realStaPairs[i]["alias"] == entry:
                realMACs[entry]["snifferName"] = realStaPairs[i]["sniffer"]
    print("\n###############################################");
    print("#######  realMACs: {}".format(realMACs))
    print("###############################################\n");

Aid2MgmtMap = {}
print('')
print('##############################################################')
index = 0
for palname,dict in palBoxMACs.items():
    snifname = snifferList[index]
    #print('>>> dict: ', dict)
    palmacaddress = dict['macaddress'].lower().replace(".","").replace(":","")
    palmgmtaddress = dict['address']
    #print(">>> palmacaddress: ", palmacaddress)
    #print(">>> palmgmtaddress: ", palmgmtaddress)
    for aid,macval in Aid2MacMap.items():
        if macval.lower().replace(".","").replace(":","") == palmacaddress:
            #print("MAC {} is pal {}, and it got AID {}".format(palmacaddress,palname,aid))
            #print('>>> Will set STApal %s @ %s to sniff AID %s.' % (palname,dict['address'],aid))
            print('>>> Will set STApal %s @ %s to sniff AID %s.' % (snifname,snifSetDictList[index]['palAddress'],aid))
            Aid2MgmtMap.update({aid:snifSetDictList[index]['palAddress']})
            palBoxMACs[palname]["snifferaddress"] = snifSetDictList[index]['palAddress']
            palBoxMACs[palname]["snifferAID"] = aid
            break
    index += 1
print(">>> Aid2MgmtMap: ", Aid2MgmtMap)
print('##############################################################')

print('\n##############################################################')
print('##### palBoxMACs: ', json.dumps(palBoxMACs,indent=3))
print('##############################################################')

if len(realStaPairs) > 0:
    for entry in realMACs:
        snifname = realMACs[entry]["snifferName"]
        realMACs[entry]["snifferaddress"] = paramsDict[snifname]["val"]["address"]
        realMACs[entry]["snifferAID"] = realMACs[entry]["aid"]
        aid = realMACs[entry]["aid"]
        address = paramsDict[snifname]["val"]["address"]
        Aid2MgmtMap.update({aid:address})
    print("\n###############################################");
    print("#######  realMACs: {}".format(realMACs))
    print("###############################################\n");
    print("\n Aid2MgmtMap: {}\n".format(Aid2MgmtMap))        

print('')
print('##############################################################')
print("##### ASSIGN FOUND BSSID AND AID PARAMETERS TO SNIFFERS" )
print('##############################################################')

#And now, set whatever sniffer AIDs you were able to figure out.
sniffer_capture_array = []
for aid in Aid2MgmtMap:
        AID = aid
        mgmtIP = Aid2MgmtMap[aid]
        BSSID = thisBssid
        parts = mgmtIP.split(".")
        snID = str(parts[len(parts)-1])
        print('\n>>> Checking for basic-server running on STApal @ %s.' % mgmtIP)
        url = serverExec+"curl http://"+mgmtIP+":8383/"
        resp = requests.get(url=url, timeout=REST_TIMEOUT)
        jsn = json.loads(resp.text)
        #print('>>> jsn: ', jsn)
        if jsn["status"] and jsn["status"] =="OK" and "reached" in jsn["stdout"]:
                print(">>> basic-server is running on STApal {}".format(mgmtIP))
        else:
                print(">>> basic-server is not running on STApal {}.  It needs to be. QUITTING.".format(palMgmtIP))
                sys.exit(41)

        #print('>>> Tuning STApal to sniff BSSID: %s, AID: %s.' % (BSSID,str(AID)))
        curlExec = "curl http://"+mgmtIP+":8383/exec?command="
        command = "echo octoScope-customer-key-201504271520 | sudo -S octosniff.sh AID " + str(AID) + " " + BSSID + " " + "sn"+snID+"a"+str(AID)
        url = serverExec+curlExec+command
        print("{}>>> For sniffer {}, setting AID to {} and BSSID to {} with command {}{}".format(cGreen,sniffer,AID,BSSID,url,cNormal))
        print('>>> This takes about 15 seconds.')
        resp = requests.get(url=url, timeout=REST_TIMEOUT)
        jsn = json.loads(resp.text)
        print(">>> Response from STApal command: {}".format(jsn))

print('')
print('##############################################################')
print("############ START ALL SNIFFERS" )
print('##############################################################')

#Start up all of the sniffers.
print('>>> snifStartDictList: ', snifStartDictList)
sd2Utils.startSniffers(snifStartDictList)

#And, now that you have tuned all possible sniffers to their AIDs and started those sniffers, run the test

print('')
print('##############################################################')
print("##### RUN THE TEST WITH ALL OF THE SNIFFERS IN 5 SECONDS" )
print('##############################################################')
time.sleep (5)

globalsfile.fileSuffix = "All_Sniffers"	# Set pcap and zip file suffix
sd2Utils.startAutotest()
sd2Utils.waitLoop(10,2)
jsonZipPath = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False)
print("{}\n>>> Test to find the MAC mapping for aid {} is done! {}".format(cGreen,aid,cNormal))
print('')
print('##############################################################')
print("##### TEST WITH ALL OF THE SNIFFERS -- DONE" )
print("##### Path to the zip file is " + jsonZipPath)
print('##############################################################')


pcapFileName = sd2Utils.stopSniffers(delay_after_capture=10)
#print("\n>>> Full path to pcap file: " , pcapFileName)
pcapFileName.rsplit('/',1)
pcapDir = pcapFileName.rsplit('/',1)[0]
print("\n>>> pcapDir: " , pcapDir)
pcapFile = pcapFileName.rsplit('/',1)[1]
print("\n>>> pcapFile: " , pcapFile)

# Put a copy of the pcap in EA pcapDirectory folder
command = 'echo octoscope | sudo -S cp '+pcapFileName+' '+paramsDict['expertAnalysis_server']['val']['dirpath']+'/pcapDirectory/'+pcapFile
print('\n>>> copy to EA pcapDirectory folder command: ', command)
os.popen(command)


#Remove existing test report so that if there is a problem here, you don't get fooled into thinking that an old report is the new report.
if os.path.exists(directory_name+"TestReport.json"):
        rmResult = os.system("rm " +directory_name+"TestReport.json")
        print("\n>>> Removing old TestReport.json: {}".format(rmResult))
if os.path.exists(directory_name+"TestMessages.json"):
        rmResult = os.system("rm "+directory_name+"TestMessages.json")
        print("\n>>> Removing old TestMessages.json: {}".format(rmResult))

#print('>>> EXIT @ LINE 793')
#sys.exit()
############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED #########################

import createReport
print('')
print('##############################################################')
print(">>> Start the HTML report creation process.")

someData = {
    "iface":interface,
    "bw":bandwidth,
    "channel":primaryChannel,
    "upOrDown":updn,
    "nss":streams,
    "bssidToUse": bssidToUse,
    "Aid2MacMap": Aid2MacMap,
    "palBoxMACs": palBoxMACs
    }
#createReport.createReport(directory_name,json_path,ea_root,someData=someData)
print("Calling createReport with someData")
print(someData)
createReport.createReport(directory_name,globalsfile.outputDirPath,ea_root,someData=someData)
endTime = time.time()    
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("{} ########## The elapsed time for the entire run is {} {} seconds.".format(cGreen,round((endTime-startTime),1),cNormal))
print('##############################################################')

