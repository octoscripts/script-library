'''
Test Description
================
Fully developed eMLSR test.  
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime
import math

import zipfile
from zipfile import ZipFile

import pprint
pp = pprint.PrettyPrinter(indent=4)

def formatMAC(mac):
    fMAC = mac
    fMAC = fMAC.replace(".",":")
    fMAC = fMAC.upper()
    if(fMAC[len(fMAC)-1]==":"): fMAC = fMAC[0:len(fMAC)-1]
    fMAC = fMAC.strip()
    return fMAC

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

haveCreateReport = False
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
    print("I see a file called createReport.  So using it for report creation.")
    haveCreateReport = True
    import createReport
else:
    print("I do not see a file called createReport.")

ea_root = sd2Utils.whereIsEA()

sd2Utils.logToJSON(globalsfile.resultsPath, {"palToUse":paramsDict["palToUse"]["val"]})
sd2Utils.logToJSON(globalsfile.resultsPath, {"mloConfig_STA":paramsDict["mloConfig_STA"]["val"]})
sd2Utils.logToJSON(globalsfile.resultsPath, {"mloConfig_AP":paramsDict["mloConfig_AP"]["val"]})
sd2Utils.logToJSON(globalsfile.resultsPath, {"obssAP":paramsDict["obssAP"]["val"]})

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
# A bit hard-coded.  Work on this later.  But for now, have a specific setting for the eMLSR link path.
#sd2Utils.setAtten("vQA-Group4", "virtualAtten", 20, attenValueStop=20)


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
if usePalAsAP != "" and usePalAsAP in paramsDict: usingPalAsAP = True

mloConfig_AP = paramsDict["mloConfig_AP"]["val"]
ipMapping = {}
palsInTest = []

if usingPalAsAP:
    print("Using {} as the AP.".format(usePalAsAP))
    #Setting up Pal AP MLO configuration
    mloConfig = mloConfig_AP
    apDictList = []
    (apDictList, APselectedValues) = sd2Utils.setupMloAP(usePalAsAP,mloConfig, apDictList,apBridge=True,bandConfig='BAND_DUAL',pushConfig=False)
    thisMapping = APselectedValues[usePalAsAP]["ipMapping"]
    for address in thisMapping: ipMapping[address] = thisMapping[address]
    print("Here are the selected values from setupMloAP:\n{}".format(APselectedValues))
    palsInTest.append(usePalAsAP)
else:
    print("A real AP is assumed.")
    mloConfig_STA = paramsDict["mloConfig_STA"]["val"]
    mloConfig = mloConfig_STA

#Select a band to use for the traffic pair configuration.
for band in mloConfig["bands"]:
    if not mloConfig["bands"][band]["member"]: continue
    useBand = band
    break;

tpDictList = []
tpDictList = sd2Utils.setupTrafficPairs(palToUse, useBand, updn, tpDictList, useWANendpoint=False, measureCongestion=False, palAsAP=usePalAsAP, tType=trafficType, tMode=iperfMode, tBW=trafficBW, tParallel=parallel, tLength='', tWindow='',linkMonitor=False)

ifaceDrop = paramsDict["iface"]["val"]
for item in ifaceDrop:
    if item["selected"]:
        interface = item["value"]
        break

streams = int(paramsDict["nss"]["val"])

chainRXMask = None
if "chainRXMask" in paramsDict: chainRXMask = paramsDict["chainRXMask"]["val"]
chainTXMask = None
if "chainTXMask" in paramsDict: chainTXMask = paramsDict["chainTXMask"]["val"]

#Setting up Pal STA MLO configurations:
mloConfig_STA = paramsDict["mloConfig_STA"]["val"]
staDictList = []
mloConfig = mloConfig_STA
(STAselectedValues, staDictList) = sd2Utils.setupMloSTA(palToUse, mloConfig,staDictList,bssid='',pushConfig=True)
print("Here are the selected values from setupMloSTA:\n{}".format(STAselectedValues))
thisMapping = STAselectedValues[palToUse]["ipMapping"]
for address in thisMapping: ipMapping[address] = thisMapping[address]
palsInTest.append(palToUse)

targetRadio = staDictList[0]['palRadio']
theSTA = staDictList[0]

#Fix the traffic pair
theTrafficPair = tpDictList[0]
if theTrafficPair["to"]["trafficAddress"]   in ipMapping: theTrafficPair["to"]["trafficAddress"]   = ipMapping[theTrafficPair["to"]["trafficAddress"]]
if theTrafficPair["from"]["trafficAddress"] in ipMapping: theTrafficPair["from"]["trafficAddress"] = ipMapping[theTrafficPair["from"]["trafficAddress"]]
sd2Utils.updateTrafficPair(theTrafficPair)
tpDictList[0] = theTrafficPair

##################################################################################################################
#Here we set up the OBSS traffic.
obssPal = paramsDict["obssAP"]["val"]

bandToObssTP = {}
obssTpDictList = []
for band in mloConfig_STA["bands"]:
    if not mloConfig_STA["bands"][band]["member"]: continue
    useBand = band
    obssTpDictList = sd2Utils.setupTrafficPairs(mloConfig_STA["bands"][band]["palName"], useBand, "dn", obssTpDictList, useWANendpoint=False, measureCongestion=False, palAsAP=obssPal["palName"], tType=trafficType,tMode="tcp", tBW="0M", tParallel="1", tLength='', tWindow='',linkMonitor=False)
    bandToObssTP[useBand] = obssTpDictList[len(obssTpDictList)-1]


obssAPDictList = []
obssBands = obssPal["bands"]

radiosToSet = 0
for band in obssBands: radiosToSet += 1
ipAddressBridge = None
radiosSet = 0
for band in obssBands:
    apDictOverride={"bandwidth":obssBands[band]["bandwidth"]}
    apDictOverride["ssid"] = obssBands[band]["ssid"]
    apDictOverride["security"] = obssBands[band]["security"]
    apDictOverride["password"] = obssBands[band]["password"]
    #You need to make sure that you use the same ipAddressBridge for all of the enabled radios.  sd2Utils does not do this by default, so do it by hand here.
    if ipAddressBridge==None:
        if "2" in band: ipAddressBridge = paramsDict[obssPal["palName"]]["val"]["endpoints"]["RADIO_24"]["defaultIp"]
        elif "5A" in band: ipAddressBridge = paramsDict[obssPal["palName"]]["val"]["endpoints"]["RADIO_5A"]["defaultIp"]
        elif "5B" in band: ipAddressBridge = paramsDict[obssPal["palName"]]["val"]["endpoints"]["RADIO_5B"]["defaultIp"]
        elif "5" in band: ipAddressBridge = paramsDict[obssPal["palName"]]["val"]["endpoints"]["RADIO_5A"]["defaultIp"]
        elif "6" in band: ipAddressBridge = paramsDict[obssPal["palName"]]["val"]["endpoints"]["RADIO_6"]["defaultIp"]
    apDictOverride["ipAddressBridge"] = ipAddressBridge
    useChannel = obssBands[band]["channel"]
    if "6" in band: useChannel += 190
    doPush = False
    radiosSet += 1
    if radiosSet == radiosToSet: doPush=True
    obssAPDictList = sd2Utils.setupAP(obssPal["palName"],band,obssAPDictList,channel=useChannel,apDictOverride=apDictOverride,pushConfig=doPush)

if ipAddressBridge != None:
    #Change the traffic addresses for all of the obss pairs to use the bridge traffic address.  On the AP side, of course.
    for tp in obssTpDictList:
        if obssPal["palName"] in tp["from"]["alias"]: tp["from"]["trafficAddress"] = ipAddressBridge
        elif obssPal["palName"] in tp["to"]["alias"]: tp["to"]["trafficAddress"] = ipAddressBridge
        sd2Utils.updateTrafficPair(tp)

associatedAttenuators = []
obssSTADictList = []
for band in mloConfig_STA["bands"]:
    if not mloConfig_STA["bands"][band]["member"]: continue
    useBand = band
    theseAttenuators = mloConfig_STA["bands"][band]["associatedAttenuators"]
    for thisAttenuator in theseAttenuators:
        if thisAttenuator not in associatedAttenuators: associatedAttenuators.append(thisAttenuator)
    staDictOverride = {}
    staDictOverride["ssid"]     = obssBands[useBand]["ssid"]
    staDictOverride["security"] = obssBands[useBand]["security"]
    staDictOverride["password"] = obssBands[useBand]["password"]
    useChannel = obssBands[useBand]["channel"]
    if "6" in useBand: useChannel += 190
    staDictOverride["interface_"] = "INTERFACE_BE"
    if "2" in useBand:   staDictOverride["bandwidth"] = "BANDWIDTH_40_ADAPT"
    elif "5" in useBand: staDictOverride["bandwidth"] = "BANDWIDTH_160_ADAPT"
    elif "6" in useBand: staDictOverride["bandwidth"] = "BANDWIDTH_160_ADAPT"
    obssSTADictList = sd2Utils.setupSTA(mloConfig_STA["bands"][band]["palName"],useBand,obssSTADictList,channel=useChannel,staDictOverride=staDictOverride,pushConfig=True)

print("These are the associated attenuators: {}".format(associatedAttenuators))
autotest_dict = globalsfile.autotest_dict.copy()
testAttens = autotest_dict["quadAttens"]
#print("These are the test attenuators: {}".format(testAttens))
#Remove the associated attenuators
for i in range (len(testAttens)-1 , -1 , -1):
    anAtten = testAttens[i]
    #print("Checking {}".format(anAtten["devName"]))
    if anAtten["devName"] in associatedAttenuators:
        print("Removing {} from the quadAtten list.".format(anAtten["devName"]))
        autotest_dict["quadAttens"].remove(anAtten)
sd2Utils.updateAutotest(autotest_dict, pushConfig=True)        

for atten in associatedAttenuators:
    devType = sd2Utils.getAttenType(atten)
    #sd2Utils.setAtten(atten,devType,0,0)
    sd2Utils.setAttenDirect(atten, 0)
#There was a strange problem with configuring multiple Pal radios, in which only one of the radios would get a configuration pushed.  The solution seemed to be to have
#the Pal in standby mode completely.
#This may not be necessary if you don't push the AP configuration until you are done with all of the APs.  So remove for now.
'''
print("Shutting down all radios of {}".format(obssPal["palName"]))
time.sleep(5)
sd2Utils.setPalStandby(obssPal["palName"], "24g")
sd2Utils.setPalStandby(obssPal["palName"], "5g")
sd2Utils.setPalStandby(obssPal["palName"], "6g")
'''
#########################################################################################################################################    

doSniffing = paramsDict["doSniffing"]["val"]
#Set up for sniffing.
if doSniffing:
    #Setting up sniffers.
    #Is SnifferRelay running?
        SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],True,args=paramsDict['oBox_server']['val']['publicip'])

        snifSetDictList = []
        snifDispDictList = []
        snifStartDictList = []

        overrideDict = {}

        for band in mloConfig_STA["bands"]:
            if not mloConfig_STA["bands"][band]["member"]: continue
            snifferPal = mloConfig_STA["bands"][band]["snifferName"]
            useBand = band
            useChannel = obssBands[useBand]["channel"]
            if "6" in useBand:
                useChannel += 190
                channelSide = mloConfig_STA["bands"][band]["snifferChannelSide"].strip().lower()
                if "default" in channelSide: overrideDict["channelSide"] = "CHAN_SIDE_DEFAULT"
                elif "lower" in channelSide: overrideDict["channelSide"] = "CHAN_SIDE_LOWER"
                elif "upper" in channelSide: overrideDict["channelSide"] = "CHAN_SIDE_UPPER"
                overrideDict["bandwidth"] = "BANDWIDTH_160_ADAPT"
            print("Set up a sniffer with Pal {}, on band {}, channel {}".format(snifferPal,useBand,useChannel))
            (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(snifferPal, useBand, 160, useChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=True, mgmtFrames=False,overrideDict=overrideDict)

        '''
        #Why do I need so many sniffers?  Just have one sniffer per operating channel.
        #Set up a sniffer in the same group as the main stapal.  Problem is it can only be on a single channel...
        palToUseSniffer = paramsDict["palToUseSniffer"]["val"]
        print("Set up a sniffer with Pal {}, on band {}, channel {}".format(palToUseSniffer,useBand,useChannel))
        (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(palToUseSniffer, useBand, 160, useChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=True, mgmtFrames=False,overrideDict)
        '''
        
        # Update sniffer Autotest configs and push
        sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
        sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True)

else:
    #Push a config here, because you didn't get a chance to do it in the sniffer configuration above.
    autotest_dict = globalsfile.autotest_dict.copy()
    sd2Utils.updateAutotest(autotest_dict, pushConfig=True)

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

sd2Utils.waitForAssociation(palToUse,targetRadio,timeToWait=45)
#Let's not for now.  Need to understand this better.
time.sleep(10)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

#Going to run a whole suite of tests here.
suiteResults = {}
deviceMap = {"deviceMap":{}}
mloBands = mloConfig["bands"]

delayedStart = False

'''
#Seeing that the STApal doesn't necessarily come up using all bands. Push the config, since that seems to help.
print("\n\n\n\n\nDoing a final re-push of the MLO enabled STApal.\n\n\n\n\n")
sd2Utils.updateAutotestInst([theSTA], "staPal7s",pushConfig=True)
sd2Utils.waitForAssociation(palToUse,targetRadio,timeToWait=45)    
time.sleep(4)
'''

#0.  A capture just for the MLO association phase, as long as you are doing sniffing.
if doSniffing:
    # Hide the OBSS APs.
    for atten in associatedAttenuators:  sd2Utils.setAttenDirect(atten, 90)
    #Close main attenuators, too, so that you can get association information in this capture.
    for atten in attensToUse:  sd2Utils.setAttenDirect(atten, 90)
    #Hang for a bit.
    time.sleep(10)
    sd2Utils.startSniffers(snifStartDictList)
    time.sleep(4)
    #Open main attenuators so that you can see the association phase happening.
    for atten in attensToUse:  sd2Utils.setAttenDirect(atten, 0)
    #Seeing that the STApal doesn't necessarily re-attach. Push the config, since that seems to help.
    sd2Utils.updateAutotestInst([theSTA], "staPal7s",pushConfig=True)
    sd2Utils.waitForAssociation(palToUse,targetRadio,timeToWait=45)    
    time.sleep(4)
    pcapFile = sd2Utils.stopSniffers()            
    useName = "EMLSR-Capture.pcap"
    newPcap = globalsfile.outputDirPath + "/" + useName
    command = "mv " + pcapFile + " " + newPcap
    print("Renaming the pcap file using this command: {}".format(command))
    os.system(command)

    #Run an initial test using the main setup to find the max throughput we should expect.
    theTrafficPair['bitrate'] = '0M'
    theTrafficPair['udp'] = 'tcp'
    sd2Utils.updateTrafficPair(theTrafficPair)
    json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)    
    useName = "Max-TCP.zip"
    newPath = globalsfile.outputDirPath + "/" + useName
    command = "mv " + json_path + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)    
    if haveCreateReport:
        pcapFile = None
        retObj = createReport.extract(directory_name,globalsfile.outputDirPath,newPath,pcapFile,ea_root)
        suiteResults.update(retObj)
        sd2Utils.logToJSON(globalsfile.resultsPath, suiteResults)
    #Set them back...
    theTrafficPair['bitrate'] = trafficBW
    theTrafficPair['udp'] = iperfMode
    sd2Utils.updateTrafficPair(theTrafficPair)


throughputs = retObj[useName]
maxThroughput = throughputs[theTrafficPair['alias']]['throughput']
upperThroughput = 1000*math.ceil(maxThroughput/1000)
upperTput = "{}M".format(upperThroughput)
#print("Use {} Mbps for the throughput setting.".format(upperThroughput))

if iperfMode=='udp':
    trafficBW = upperTput
    theTrafficPair["bitrate"] = upperTput    
    theTrafficPair["ipStreams"] = 1
    sd2Utils.updateTrafficPair(theTrafficPair)

#1.  Get the data for the interfering traffic by itself.  So turn off the main traffic pair.  Make sure the OBSS attenuators are open, which they probably already are.
for atten in associatedAttenuators:  sd2Utils.setAttenDirect(atten, 0)

theTrafficPair["active"] = False
sd2Utils.updateTrafficPair(theTrafficPair)

#Turn off the OBSS pairs.
for tp in obssTpDictList:
    tp["active"] = False
    sd2Utils.updateTrafficPair(tp)

allObssAps = []
#Turn on each OBSS pair one at a time.
for band in mloBands:
    if not mloBands[band]["member"]: continue    
    print("\n\n\n\n\n\n\n Only interference on channel {} \n\n\n\n\n\n\n".format(mloBands[band]["channel"]))
    time.sleep(5)
    theTP = bandToObssTP[band]
    #print("The interfering traffic pair to use is  {}".format(theTP))
    theTP["active"] = True
    #print("Updating that traffic pair.")
    sd2Utils.updateTrafficPair(theTP)
    if doSniffing:
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(4)
    json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)
    if doSniffing:
        time.sleep(4)
        pcapFile = sd2Utils.stopSniffers()            
    useName = "Only-Interference-Channel_{}.zip".format(mloBands[band]["channel"])
    newPath = globalsfile.outputDirPath + "/" + useName
    command = "mv " + json_path + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)
    if doSniffing:
        newPcap = newPath.replace(".zip",".pcap")
        command = "mv " + pcapFile + " " + newPcap
        print("Renaming the pcap file using this command: {}".format(command))
        os.system(command)
    if haveCreateReport:
        pcapFile = newPcap
        retObj = createReport.extract(directory_name,globalsfile.outputDirPath,newPath,pcapFile,ea_root)
        suiteResults.update(retObj)
        sd2Utils.logToJSON(globalsfile.resultsPath, suiteResults)
        if "BSSIDs" in retObj:
            deviceMap["deviceMap"]["OBSS_AP_CH_{}".format(mloBands[band]["channel"])] = retObj["BSSIDs"]["AP"]
            deviceMap["deviceMap"]["OBSS_STA_CH_{}".format(mloBands[band]["channel"])] = retObj["BSSIDs"]["STA"]
            sd2Utils.logToJSON(globalsfile.resultsPath, deviceMap)
            thisValue = formatMAC(retObj["BSSIDs"]["AP"])
            if thisValue not in allObssAps: allObssAps.append(thisValue)
    theTP["active"] = False
    sd2Utils.updateTrafficPair(theTP)

if doSniffing:
    #Modify the sniffers to no longer pick up packets from the OBSS APs.  This should make the analysis easier/faster.
    print("Here are all the OBSS AP addresses: {}".format(allObssAps))
    theFilter = ""
    for bssid in allObssAps:
        if len(theFilter)==0: theFilter += "wlan addr1 not {} and wlan addr2 not {}".format(bssid,bssid)
        else:                 theFilter += " and wlan addr1 not {} and wlan addr2 not {}".format(bssid,bssid)
    print("Going to modify the sniffers to add this filter expression:  {}".format(theFilter))
    for snifferEntry in snifSetDictList:
        snifferEntry["filterExpression"] = theFilter
    sd2Utils.updateAutotestInst(snifSetDictList,"synchroSniffers",pushConfig=True)
        
#2. Run throughput to each of the radios, without any interference, and also with interference on that same channel.
theTrafficPair["active"] = True
sd2Utils.updateTrafficPair(theTrafficPair)

for tp in obssTpDictList:
    tp["active"] = False
    sd2Utils.updateTrafficPair(tp)
    
for band in mloBands:
    if not mloBands[band]["member"]: continue
    useChannel = mloBands[band]["channel"]
    if "6" in band: useChannel += 190    
    theSTA["primaryChannel"] = useChannel
    sd2Utils.updateAutotestInst([theSTA], "staPal7s",pushConfig=True)
    
    #Clean
    # Close the OBSS attenuators.
    print("\n\n\n\n\n\n\n Only throughput on channel {} \n\n\n\n\n\n\n".format(mloBands[band]["channel"]))
    time.sleep(5)    
    for atten in associatedAttenuators:  sd2Utils.setAttenDirect(atten, 90)
    if doSniffing:
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(4)
    json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)
    if doSniffing:
        time.sleep(4)
        pcapFile = sd2Utils.stopSniffers()            
    useName = "Throughput-Channel_{}.zip".format(mloBands[band]["channel"])
    newPath = globalsfile.outputDirPath + "/" + useName
    command = "mv " + json_path + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)
    if doSniffing:
        newPcap = newPath.replace(".zip",".pcap")
        command = "mv " + pcapFile + " " + newPcap
        print("Renaming the pcap file using this command: {}".format(command))
        os.system(command)
    if haveCreateReport:
        pcapFile = newPcap
        retObj = createReport.extract(directory_name,globalsfile.outputDirPath,newPath,pcapFile,ea_root)
        suiteResults.update(retObj)
        sd2Utils.logToJSON(globalsfile.resultsPath, suiteResults)
        
    #With interference
    # Open the OBSS attenuators.
    print("\n\n\n\n\n\n\n Throughput and Interference on channel {} \n\n\n\n\n\n\n".format(mloBands[band]["channel"]))
    time.sleep(5)    
    for atten in associatedAttenuators:  sd2Utils.setAttenDirect(atten, 0)
    print("Operating on channel {}".format(mloBands[band]["channel"]))
    theTP = bandToObssTP[band]
    #print("The interfering traffic pair to use is  {}".format(theTP))
    theTP["active"] = True
    #print("Updating that traffic pair.")
    sd2Utils.updateTrafficPair(theTP)

    #Now run the actual test with stored data, both PCAP and Pal
    if doSniffing:
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(4)

    #Run this test in a sort of odd way, but let the OBSS traffic flow first, and turn on the main traffic after a few seconds.  This seems to allow
    #eMLSR to get primed correctly.
    if delayedStart:
        theTrafficPair["active"] = False
        sd2Utils.updateTrafficPair(theTrafficPair)    
        sd2Utils.startAutotest()
        time.sleep(10)  #Give the OBSS traffic a chance to run alone.
        theTrafficPair["active"] = True
        sd2Utils.updateTrafficPair(theTrafficPair) #Now start the main traffic as well.
        runningTest = True
        while runningTest:
            runningTest = sd2Utils.isTestRunning()
            print("The running test is {}".format(runningTest))
        json_path = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False, saveResults=True)
    else:
        json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)
    
    if doSniffing:
        time.sleep(4)
        pcapFile = sd2Utils.stopSniffers()            
    useName = "Throughput-With-Interference-Channel_{}.zip".format(mloBands[band]["channel"])
    newPath = globalsfile.outputDirPath + "/" + useName
    command = "mv " + json_path + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)
    if doSniffing:
        newPcap = newPath.replace(".zip",".pcap")
        command = "mv " + pcapFile + " " + newPcap
        print("Renaming the pcap file using this command: {}".format(command))
        os.system(command)
    if haveCreateReport:
        pcapFile = None
        retObj = createReport.extract(directory_name,globalsfile.outputDirPath,newPath,pcapFile,ea_root)
        suiteResults.update(retObj)
        sd2Utils.logToJSON(globalsfile.resultsPath, suiteResults)
    theTP["active"] = False
    sd2Utils.updateTrafficPair(theTP)

#3. Next, reset the main traffic pair so that MLO can work.  Then get that throughput, and the throughput with each, and both, interferers.
theSTA["primaryChannel"] = 0
sd2Utils.updateAutotestInst([theSTA], "staPal7s",pushConfig=True)

theTrafficPair["active"] = True
sd2Utils.updateTrafficPair(theTrafficPair)

# If we are doing sniffing then do 2 versions of the eMLSR tests.  One at full traffic rate, and one at lower traffic rate.  Otherwise, just the one.
numberOfLoops = 1
if doSniffing: numberOfLoops = 2
print("\n\nWill be doing this many loops of eMLSR runs: {}\n\n".format(numberOfLoops))
for loop in range(0,numberOfLoops):
    #Create a tag for the PCAP file.  
    if   loop==0:
        theTag = ""
        #And don't do anything to the traffic rate.
        print("\n\nDoing loop: {}\n\n".format(loop))        
    elif loop==1:
        theTag = "_"
        #And update the traffic rate to a low value.
        theTrafficPair["bitrate"] = "5M"
        sd2Utils.updateTrafficPair(theTrafficPair)
        print("\n\nDoing loop: {}, with a traffic bit rate of {}\n\n".format(loop,theTrafficPair["bitrate"]))

    #Shut off the OBSS pairs.
    for tp in obssTpDictList:
        tp["active"] = False
        sd2Utils.updateTrafficPair(tp)

    #Clean
    # Close the OBSS attenuators.
    print("\n\n\n\n\n\n\n Throughput with EMLSR \n\n\n\n\n\n\n")
    time.sleep(5)    
    for atten in associatedAttenuators:  sd2Utils.setAttenDirect(atten, 90)
    if doSniffing:
        '''
        #Close main attenuators, too, so that you can get association information in this capture.
        for atten in attensToUse:  sd2Utils.setAttenDirect(atten, 90)
        '''
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(4)
        '''
        #Open main attenuators, too, so that you can get association information in this capture.
        for atten in attensToUse:  sd2Utils.setAttenDirect(atten, 0)
        #Seeing that the STApal doesn't necessarily re-attach. Push the config, since that seems to help.
        sd2Utils.updateAutotestInst([theSTA], "staPal7s",pushConfig=True)
        sd2Utils.waitForAssociation(palToUse,targetRadio,timeToWait=45)    
        time.sleep(4)
        '''
    json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)
    if doSniffing:
        time.sleep(4)
        pcapFile = sd2Utils.stopSniffers()            
    useName = "Throughput-EMLSR{}.zip".format(theTag)
    newPath = globalsfile.outputDirPath + "/" + useName
    command = "mv " + json_path + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)
    if doSniffing:
        newPcap = newPath.replace(".zip",".pcap")
        command = "mv " + pcapFile + " " + newPcap
        print("Renaming the pcap file using this command: {}".format(command))
        os.system(command)
    if haveCreateReport:
        pcapFile = None
        retObj = createReport.extract(directory_name,globalsfile.outputDirPath,newPath,pcapFile,ea_root)
        suiteResults.update(retObj)
        sd2Utils.logToJSON(globalsfile.resultsPath, suiteResults)

    # Open the OBSS attenuators.
    for atten in associatedAttenuators:  sd2Utils.setAttenDirect(atten, 0)
    for band in mloBands:
        if not mloBands[band]["member"]: continue    
        print("\n\n\n\n\n\n\n Throughput with EMLSR and Interference on {}\n\n\n\n\n\n\n".format(mloBands[band]["channel"]))
        time.sleep(5)    
        print("With interference on channel {}".format(mloBands[band]["channel"]))
        theTP = bandToObssTP[band]
        #print("The interfering traffic pair to use is  {}".format(theTP))
        theTP["active"] = True
        #print("Updating that traffic pair.")
        sd2Utils.updateTrafficPair(theTP)

        '''
        #Give the system a little time to learn.  So run the test as configured for a few seconds, but don't save this data. Very important here, as opposed to above.
        sd2Utils.startAutotest()
        time.sleep(20)
        json_path = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False, saveResults=False)
        '''

        #Now run the actual test with stored data, both PCAP and Pal        
        if doSniffing:
            sd2Utils.startSniffers(snifStartDictList)
            time.sleep(4)
        #Run this test in a sort of odd way, but let the OBSS traffic flow first, and turn on the main traffic after a few seconds.  This seems to allow
        #eMLSR to get primed correctly.  This is much more important here than when it was done above.
        if delayedStart:
            theTrafficPair["active"] = False
            sd2Utils.updateTrafficPair(theTrafficPair)    
            sd2Utils.startAutotest()
            time.sleep(10)  #Give the OBSS traffic a chance to run alone.
            theTrafficPair["active"] = True
            sd2Utils.updateTrafficPair(theTrafficPair) #Now start the main traffic as well.
            runningTest = True
            while runningTest:
                runningTest = sd2Utils.isTestRunning()
                print("The running test is {}".format(runningTest))
            json_path = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False, saveResults=True)
        else:
            json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)
        if doSniffing:
            time.sleep(4)
            pcapFile = sd2Utils.stopSniffers()            
        useName = "Throughput-EMLSR-With-Interference-Channel_{}{}.zip".format(mloBands[band]["channel"],theTag)
        newPath = globalsfile.outputDirPath + "/" + useName
        command = "mv " + json_path + " " + newPath
        print("Renaming the json file using this command: {}".format(command))
        os.system(command)
        if doSniffing:
            newPcap = newPath.replace(".zip",".pcap")
            command = "mv " + pcapFile + " " + newPcap
            print("Renaming the pcap file using this command: {}".format(command))
            os.system(command)
        if haveCreateReport:
            pcapFile = None
            retObj = createReport.extract(directory_name,globalsfile.outputDirPath,newPath,pcapFile,ea_root)
            suiteResults.update(retObj)
            sd2Utils.logToJSON(globalsfile.resultsPath, suiteResults)
        theTP["active"] = False
        sd2Utils.updateTrafficPair(theTP)

    #See what happens with ALL interfers active.
    # Open the OBSS attenuators.
    print("\n\n\n\n\n\n\n Throughput with EMLSR and Interference on all bands\n\n\n\n\n\n\n")
    time.sleep(5)    
    for atten in associatedAttenuators:  sd2Utils.setAttenDirect(atten, 0)
    for tp in obssTpDictList:
        tp["active"] = True
        sd2Utils.updateTrafficPair(tp)
    if doSniffing:
        sd2Utils.startSniffers(snifStartDictList)
        time.sleep(4)

    #Run this test in a sort of odd way, but let the OBSS traffic flow first, and turn on the main traffic after a few seconds.  This seems to allow
    #eMLSR to get primed correctly.  This is much more important here than when it was done above.
    if delayedStart:
        theTrafficPair["active"] = False
        sd2Utils.updateTrafficPair(theTrafficPair)    
        sd2Utils.startAutotest()
        time.sleep(10)  #Give the OBSS traffic a chance to run alone.
        theTrafficPair["active"] = True
        sd2Utils.updateTrafficPair(theTrafficPair) #Now start the main traffic as well.
        runningTest = True
        while runningTest:
            runningTest = sd2Utils.isTestRunning()
            print("The running test is {}".format(runningTest))
        json_path = sd2Utils.stopAutotest(unzip=False, saveCSV=False, saveTaJSON=False, saveResults=True)
    else:
        json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)
    if doSniffing:
        time.sleep(4)
        pcapFile = sd2Utils.stopSniffers()            
    useName = "Throughput-EMLSR-With-Interference_All{}.zip".format(theTag)
    newPath = globalsfile.outputDirPath + "/" + useName
    command = "mv " + json_path + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)
    if doSniffing:
        newPcap = newPath.replace(".zip",".pcap")
        command = "mv " + pcapFile + " " + newPcap
        print("Renaming the pcap file using this command: {}".format(command))
        os.system(command)
    if haveCreateReport:
        pcapFile = None
        retObj = createReport.extract(directory_name,globalsfile.outputDirPath,newPath,pcapFile,ea_root)
        suiteResults.update(retObj)
        sd2Utils.logToJSON(globalsfile.resultsPath, suiteResults)

if doSniffing:
    #Reset the traffic rate, in case we ever add more tests below this.
    theTrafficPair["bitrate"] = trafficBW
    sd2Utils.updateTrafficPair(theTrafficPair)


############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))

print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')

# NOTE! Report creation requires a createReport.py file. 
if haveCreateReport or False:
    
    print('')
    print('##############################################################')
    print("########## Creating final report ")
    print('##############################################################')

    reportJson = createReport.main(directory_name,globalsfile.outputDirPath,ea_root)    
    with open(globalsfile.outputDirPath + "/" + "eMLSR-Report.json","w",encoding="utf-8") as f:
        json.dump(reportJson,f,ensure_ascii=False,indent=4)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("##### %s TEST DONE " % testName)
print("##### Test run time: %s. " % testRunTime)
print('##############################################################')	
