############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime
import copy
import random

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

# ##################################################################################	
# ##################################################################################
#	                             Start of main test script
# ##################################################################################
# ##################################################################################


############################
# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

#Is the stack in use?
URL = "http://" + "{}:4000".format(paramsDict["oBox_server"]["val"]["publicip"]) + "/api/v1/in-use"
theResponse = requests.get(url=URL)
print("{} CURRENT TESTBED-IN-USE STATUS: {} {}".format(cGreen,theResponse.text,cNormal))
iam = paramsDict["myUserName"]["val"]
try:
    theJson = json.loads(theResponse.text)
    #print("{} CURRENT TESTBED-IN-USE STATUS: {} {}".format(cGreen,theJson,cNormal))
    inUseBy = theJson["userName"]
    if inUseBy.lower() == iam.lower():
        print("{} CURRENT TESTBED-IN-USE BY USER: {} THIS IS OK, SO CONTINUE.{}".format(cGreen,inUseBy,cNormal))
        blocked = False
    else:
        print("{} CURRENT TESTBED-IN-USE BY USER: {} THE TESTBED IS BLOCKED, SO QUIT.{}".format(cRed,inUseBy,cNormal))
        blocked = True
except:
    print("{} CURRENT TESTBED-IN-USE STATUS: {} {}".format(cGreen,"NOT IN USE",cNormal))
    blocked = False

if blocked: sys.exit(55)

#Reserve the testbed
URL = "http://" + "{}:4000".format(paramsDict["oBox_server"]["val"]["publicip"]) + "/api/v1/in-use/release"
theResponse = requests.put(url=URL)
data = {"userName": iam}
URL = "http://" + "{}:4000".format(paramsDict["oBox_server"]["val"]["publicip"]) + "/api/v1/in-use/assign/{}".format(iam)
theResponse = requests.post(URL,json=data,timeout=REST_TIMEOUT)
theJson = json.loads(theResponse.text)
#print(theJson)
if (theJson=="OK"): print("{} System {} now reserved for user {}{} \n\n".format(cGreen,paramsDict["oBox_server"]["val"]["publicip"],iam,cNormal))
else: print("{} Reservation of the system {} for user {} not a success: {} {}\n\n".format(cRed,paramsDict["oBox_server"]["val"]["publicip"],iam,theJson,cNormal))

        
############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

# Build list for config check
instList = []
attensToUse = paramsDict["attensToUse"]["val"]
attenList = attensToUse
palToUsedrop = paramsDict["palToUse"]["val"]
for item in palToUsedrop:
    if item["selected"]:
        palToUse = item["value"]
        break
instList.append(palToUse)
testUses=paramsDict['testUses']['val']+instList+attenList
print(">>> testUses: ", testUses)

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)

print(">>> Pulling in vSTA settings from the test parameters file.")

vstaSettings = paramsDict["vstaSettings"]["val"]
settingsPerRadio = {}
radios = []
validBandList = ['24g','2.4g','5g','6g']
validBandwidthList = ['BANDWIDTH_ADAPT','BANDWIDTH_20_FIXED','BANDWIDTH_40_ADAPT', 'BANDWIDTH_80_ADAPT', 'BANDWIDTH_160_ADAPT']
validInterfaceList = ['INTERFACE_G', 'INTERFACE_N', 'INTERFACE_AC', 'INTERFACE_AX']
txAttenValue = -2
for setting in vstaSettings:      
        if setting["vstaCount"] <= 0: continue
        if setting["band"] not in validBandList:
                print('!!! ERROR. Invalid band value %s. Must be %s. QUITTING!' % (setting["band"],validBandList))
                sys.exit(53)
        if "24" in setting["band"] or "2.4" in setting["band"]:
                radio = "RADIO_24"
                ssid = paramsDict["dut"]["val"]["dutssid24"]
                password = paramsDict["dut"]["val"]["dutpass24"]
                security = paramsDict["dut"]["val"]["dutsecurity24"]
        if "5" in setting["band"]:
                radio = "RADIO_5"
                ssid = paramsDict["dut"]["val"]["dutssid5"]
                password = paramsDict["dut"]["val"]["dutpass5"]
                security = paramsDict["dut"]["val"]["dutsecurity5"]
        if "6" in setting["band"]:
                radio = "RADIO_6"
                ssid = paramsDict["dut"]["val"]["dutssid6"]
                password = paramsDict["dut"]["val"]["dutpass6"]
                security = paramsDict["dut"]["val"]["dutsecurity6"]
        band = setting["band"]
        if setting["bandwidth"] not in validBandwidthList:
                print('!!! ERROR. Invalid bandwidth value %s. Must be %s. QUITTING!' % (setting["bandwidth"],validBandwidthList))
                sys.exit(53)
        bandwidth = setting["bandwidth"]
        if setting["interface"] not in validInterfaceList:
                print('!!! ERROR. Invalid interface value %s. Must be %s. QUITTING!' % (setting["interface"],validInterfaceList))
                sys.exit(53)
        interface = setting["interface"]

        if setting["streams"] < 1 or setting["streams"] > 8:
                print('!!! ERROR. Invalid streams value %s. Must be 1-8. QUITTING!' % (setting["streams"]))
                sys.exit(53)

        settingsPerRadio[radio] = {
                "band": band,
                "vstaCount": setting["vstaCount"],
                "interface": interface,
                "streams": setting["streams"],        
                "bandwidth": bandwidth,
                "primaryChannel": setting["primaryChannel"],
                "txAtten": setting["txAtten"],
                "ssid": ssid,
                "security": security,
                "password": password
        }

        #txAttenValue += 2
        #settingsPerRadio[radio]["txAtten"] = txAttenValue

        radios.append(radio)

#print('>>> settingsPerRadio: ', settingsPerRadio)
print('>>> radios: ', radios)

upOrDowndrop = paramsDict["upOrDown"]["val"]
for item in upOrDowndrop:
    if item["selected"]:
        upOrDown = item["value"]
        break

# Calculate additional wait time for vSTA config push and association
totalVstaWait = 0
print('')
print('##############################################################')
for radio in radios:
        vstaWaitMore = settingsPerRadio[radio]["vstaCount"]*paramsDict["vstaWait"]["val"]
        totalVstaWait += vstaWaitMore
        settingsPerRadio[radio]["vstaWaitMore"] = vstaWaitMore
        print(">>> Adding {} seconds to association and config push waits for radio {}.".format(vstaWaitMore,radio))

print(">>> Adding TOTAL of %s seconds to association and config push waits." % totalVstaWait)
print('##############################################################')

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
resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp, "security":security, "ssid":ssid, "password":password, "trafficType": paramsDict['trafficType']['val'], "trafficMode":paramsDict['trafficMode']['val'], "upOrDown": upOrDown})
if 'RADIO_24' in settingsPerRadio.keys(): 
        resultDict['testInfo'].update({"24g_vStaSettings": settingsPerRadio['RADIO_24']})
if 'RADIO_5' in settingsPerRadio.keys(): 
        resultDict['testInfo'].update({"5g_vStaSettings": settingsPerRadio['RADIO_5']})
if 'RADIO_6' in settingsPerRadio.keys(): 
        resultDict['testInfo'].update({"6g_vStaSettings": settingsPerRadio['RADIO_6']})
resultDict['testInfo'].update({"scriptSuiteVersion":globalsfile.scriptSuiteVersion})
resultDict['testInfo'].update({"starDustVersion":globalsfile.starDustVersion})
resultDict['testInfo'].update({"palFWversions":globalsfile.palFWdict})
if test_param_alt_file:
        resultDict['testInfo'].update({"testParamAltFile":test_param_alt_file})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

print(">>> Pulling in data from the test parameters file. DONE.")
############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################


############### START SECTION: BUILD THE TEST OBJECT #########################
print(">>> Creating the complete test object.")

tmpdict={'rvrMode':'RvR'}
sd2Utils.updateAutotest(tmpdict, pushConfig=True)

print('')
print('##############################################################')
print("########## Setting up Attenuators START ")
print('##############################################################')
sd2Utils.isolateAllBoxes()

icnt = 0
for atten in attensToUse:
    icnt += 1
    pc = False
    if icnt==len(attensToUse): pc=True
    sd2Utils.setAtten(atten,paramsDict[atten]["val"]["devType"],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=pc)

print('')
print('##############################################################')
print("########## Setting up Attenuators DONE ")
print('#############################################################')
print('')
print('##############################################################')
print("########## Setting up vSTA Traffic pairs START ")
print('##############################################################')

startvStaSetupTime = time.time()
allVstaConfigs = {}
vstaConfigList = []
tpDictList = []
for radio in radios:
        print('')
        print('##############################################################')
        print("############ Setting up {} vSTAs for Pal {} on radio {}".format(settingsPerRadio[radio]["vstaCount"],palToUse,radio))
        print('##############################################################')

        vstaParams = {
                "interface_": settingsPerRadio[radio]["interface"],
                "bandwidth": settingsPerRadio[radio]["bandwidth"],
                "certFilename": '',
                "radiusIdentity": '',
                "radiusPassword": '',
                "security": settingsPerRadio[radio]["security"],
                "ssid": settingsPerRadio[radio]["ssid"],
                "streams": settingsPerRadio[radio]["streams"],
                "txAtten": settingsPerRadio[radio]["txAtten"]
        }

        (vstaConfigList,tpDictList) = sd2Utils.setupVsta(palToUse, settingsPerRadio[radio]["band"], settingsPerRadio[radio]["primaryChannel"], upOrDown, paramsDict['trafficMode']['val'], settingsPerRadio[radio]["vstaCount"], vstaParams, tpDictList, pushConfig=False,linkMonitor=paramsDict['linkMonitor']['val'])
        allVstaConfigs[radio] = vstaConfigList
        if paramsDict['debug']['val']:
                print('')
                print('##############################################################')
                print('>>> radio: ', radio)
                print('>>> tpDictList: ', tpDictList)
                print('##############################################################')
endvStaSetupTime = time.time()

sd2Utils.updateAutotestInst(tpDictList, 'trafficPairs', pushConfig=True) # update config and push
endvStaTrafficPairPushTime = time.time()
vstaTrafficPairConfigCreateTime = round((endvStaSetupTime-startvStaSetupTime),1)
vstaTrafficPairConfigPushTime = round((endvStaTrafficPairPushTime-endvStaSetupTime),1)
print('')
print('##############################################################')
print("########## Setting up vSTAs DONE")
print('########## Time to create all vSTA traffic pairs: %s' % vstaTrafficPairConfigCreateTime)
print('########## Time to push all vSTA traffic pair config: %s' % vstaTrafficPairConfigPushTime)
if paramsDict['debug']['val']:
        print('########## tpDictList:')
        pp.pprint(tpDictList)
print('##############################################################')
resultDict = {}
resultDict.update({"vstaTrafficPairConfigCreateTime": vstaTrafficPairConfigCreateTime})
resultDict.update({"vstaTrafficPairConfigPushTime": vstaTrafficPairConfigPushTime})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
#print('>>> EXIT at LINE 338')
#sys.exit()

startStaSetupTime = time.time()

print('')
print('##############################################################')
print("########## Setting up Pal6 STAs START")
print('##############################################################')
allStaPalDicts = {}
staPalDictList = []

for radio in radios:
        print('')
        print('##############################################################')
        print("########## Set up {}, radio {}".format(palToUse,radio))
        print('##############################################################')
        overrideDict = {
            "bandwidth": settingsPerRadio[radio]["bandwidth"],
            "interface_": settingsPerRadio[radio]["interface"],
            "ssid": settingsPerRadio[radio]["ssid"],
            "password": settingsPerRadio[radio]["password"],
            "security":settingsPerRadio[radio]["security"],
            "vstaCount": settingsPerRadio[radio]["vstaCount"],
            "vstaConfig": allVstaConfigs[radio],
            "ipMode":"IP_DHCP"
        }

        staPalDictList = sd2Utils.setupSTA(palToUse,settingsPerRadio[radio]["band"], staPalDictList, streams=settingsPerRadio[radio]["streams"], channel=settingsPerRadio[radio]["primaryChannel"], staDictOverride=overrideDict, timeoutOverride=REST_TIMEOUT+settingsPerRadio[radio]["vstaWaitMore"])
        allStaPalDicts[radio] = staPalDictList
if paramsDict['debug']['val']:
        print('>>> staPalDictList: ' )
        pp.pprint(staPalDictList)
#print('>>> EXIT @ LINE 370 to check STA setup')
#sys.exit()

endStaSetupTime = time.time()

thePalConfig = paramsDict[palToUse]["val"]
if thePalConfig['devType'] == "pal7": 
    palType = "pal7s"
else:
    palType = "pal6s"


sd2Utils.updateAutotestInst(staPalDictList, palType, pushConfig=True, timeoutOverride=REST_TIMEOUT+settingsPerRadio[radio]["vstaWaitMore"]) # update config and push
endStaSetupPushTime = time.time()

staConfigCreateTime = round((endStaSetupTime-startStaSetupTime),1)
staConfigPushTime = round((endStaSetupPushTime-endStaSetupTime),1)
print('')
print('##############################################################')
print("########## Setting up Pal STAs DONE")
print('########## Time to create pals config: %s' % staConfigCreateTime)
print('########## Time to push pals config: %s' % staConfigPushTime)
print('##############################################################')
resultDict = {}
resultDict.update({"staConfigCreateTime": staConfigCreateTime})
resultDict.update({"staConfigPushTime": staConfigPushTime})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

DHCP_IPs = {}
for radio in radios:

        palRadio = allStaPalDicts[radio][0]['palRadio']
        targetRadio = palRadio
        palAlias = allStaPalDicts[radio][0]['alias']

        print('')
        print('##############################################################')
        print("########## Associating {} vSTAs for {} on radio {} ".format(settingsPerRadio[radio]["vstaCount"], palToUse, radio))
        print('##############################################################')

        associatedStatus = False
        assocWaitTime = 30+settingsPerRadio[radio]["vstaWaitMore"]
        band = settingsPerRadio[radio]["band"]
        #print('>>> band: ', band)
        if band: # Make sure not None
                if '6' in band:
                        assocWaitTime = 40+settingsPerRadio[radio]["vstaWaitMore"]	# 6 GHz takes longer to associate
        print('')
        print('##############################################################')
        print('>>> assocWaitTime_'+radio+': ', assocWaitTime)
        print('##############################################################')

        palRadio = radio
        if palType == "pal7s":
            if palRadio == "RADIO_5": palRadio = "RADIO_5A"
        associatedStatus = sd2Utils.waitForAssociation(palToUse,palRadio,timeToWait=assocWaitTime,vstasRequired=settingsPerRadio[radio]["vstaCount"])
        if not associatedStatus:
                print(">>> Association not completed. Quitting.")
                sys.exit(66) # Set for SM
        else:
            if globalsfile.online:
                looping = 0
                theStatus = sd2Utils.getPalStatus(palToUse,3,targetRadio=palRadio,vstasRequired=settingsPerRadio[radio]["vstaCount"])
                while theStatus["palStatus"]["id"]["radio"] != palRadio:
                    looping += 1
                    #print("At this point, theStatus is {}. \n Looking for {}, not {}. ".format(theStatus,palRadio,theStatus["palStatus"]["id"]["radio"]))
                    print("Looking for {}, not {}. Looped {} times.".format(palRadio,theStatus["palStatus"]["id"]["radio"],looping))
                    theStatus = sd2Utils.getPalStatus(palToUse,3,targetRadio=palRadio,vstasRequired=settingsPerRadio[radio]["vstaCount"])
                print("For radio {}, the AP is associated.  Now wait until you have the IP address.".format(palRadio))
                #print(theStatus["palStatus"])
                theIP = theStatus["palStatus"]["ipAddress"]
                vstaCount = theStatus["palStatus"]["vstaCount"]
                vstaIPs = []
                if "vstaStatus" in theStatus["palStatus"]:
                    for vstaStatus in theStatus["palStatus"]["vstaStatus"]:
                        if len(vstaStatus["ipAddress"])!= 0: vstaIPs.append(vstaStatus["ipAddress"])
                while len(theIP)==0 or len(vstaIPs)<vstaCount:
                    print("No IP address assigned yet.  theIP={}, and vstaCount={}".format(theIP,vstaCount))
                    theStatus = sd2Utils.getPalStatus(palToUse,3,targetRadio=palRadio,vstasRequired=settingsPerRadio[radio]["vstaCount"])
                    theIP = theStatus["palStatus"]["ipAddress"]
                    vstaCount = theStatus["palStatus"]["vstaCount"]
                    vstaIPs = []
                    print("The assigned IP to {} on radio {} is {}".format(palToUse,palRadio,theIP))
                #It's a good idea to update the IP address in paramsDict in case you need to access it again quickly.
                print("For Pal {}, the IP address is {}, and for the {} vSTAs, the IP addresses are {}".format(palToUse,theIP,vstaCount,vstaIPs))
                theEndpoints = paramsDict[palToUse]["val"]["endpoints"]
                for endpoint in theEndpoints:
                    if endpoint == palRadio: theEndpoints[endpoint]["defaultIp"] = theIP

        print("Updated the IP address in paramsDict in case that IP address needs to be used again.")
        #print("For {} the paramsDict entry is now{}.".format(palToUse,paramsDict[palToUse]))
        DHCP_IPs[radio] = vstaIPs.copy()

        print('')
        print('##############################################################')
        print("########## Associating vSTAs DONE for {} on radio {}".format(palToUse,radio))
        print('##############################################################')

print("Here are the IP addresses being used, per Radio, per vSTA: {}".format(DHCP_IPs))

endAssocTime = time.time()
timePushToAssociateDone = round((endAssocTime-endStaSetupPushTime),1)
print('##############################################################')
print("########## Associating all vSTAs DONE on all Pals and radios")
print('########## Time from push done to all vSTAs associated: %s' % timePushToAssociateDone)
print('##############################################################')


############### REASSIGN THE IP ADDRESS TO THIS TRAFFIC PAIR  #########################
#Update your traffic pair with the correct IP address.
for radio in radios:
    #print("Looking at radio {}".format(radio))
    suffix = radio.replace("RADIO","")
    #print("Looking for suffix {}".format(suffix))
    theseIPs = DHCP_IPs[radio]
    #print("Going to update IPs with these IPs. {}".format(theseIPs))
    count = 0
    for theTrafficPair in tpDictList:
        theAlias = paramsDict[palToUse]["val"]["alias"]
        #print("The Pal alias is {}".format(theAlias))
        thisAlias = "{}{}_{}".format(theAlias,suffix,count).replace("_0","")
        #print("The alias for radio {} is {}".format(radio,thisAlias))
        if theTrafficPair["to"]["alias"] == thisAlias:
            theIP = theseIPs[count]
            print("Going to replace {} with {}".format(theTrafficPair["to"]["trafficAddress"],theIP))
            theTrafficPair["to"]["trafficAddress"] = theIP
            count += 1
            sd2Utils.updateTrafficPair(theTrafficPair)
        elif theTrafficPair["from"]["alias"] == thisAlias:
            theIP = theseIPs[count]
            print("Going to replace {} with {}".format(theTrafficPair["from"]["trafficAddress"],theIP))
            theTrafficPair["from"]["trafficAddress"] = theIP
            count += 1
            sd2Utils.updateTrafficPair(theTrafficPair)


resultDict = {}
resultDict.update({"timePushToAssociateDone": timePushToAssociateDone})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

resultDict = {}
resultDict.update({"DHCP_Assignments_Per_Radio": DHCP_IPs})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

if paramsDict['reassociationCheck']['val'] and len(attensToUse) != 0:

        print('')
        print('##############################################################')
        print("##### Reassociation check. Setting Attenuation to maximum to disassociate all vSTA.")

        for atten in attensToUse:
            sd2Utils.setAtten(atten,paramsDict[atten]["val"]["devType"],90)

        sd2Utils.waitLoop(paramsDict['reassociationCheckTime']['val'],2)

        resultDict = {"reassociationCheck":{}}
        #Check the association status.
        for radio in radios:
                vstasRequired = settingsPerRadio[radio]["vstaCount"]
                palRadio = allStaPalDicts[radio][0]['palRadio']
                palStatus = sd2Utils.getPalStatus(palToUse,1, targetRadio=palRadio, vstasRequired=vstasRequired)
                print(">>> Radio %s has %s vSTA of %s associated." % (palRadio,palStatus['vstaAssociatedCount'],vstasRequired))
                resultDict['reassociationCheck'].update({palRadio: palStatus['vstaAssociatedCount']})
        #Now, open up the link again, and check for association
        print('')
        print("##### Reassociation check. Setting Attenuation to minimum to reassociate all vSTA.")

        for atten in attensToUse:
            sd2Utils.setAtten(atten,paramsDict[atten]["val"]["devType"],0)

        startReAssocCheckTime = time.time()

        for radio in radios:
                vstasRequired = settingsPerRadio[radio]["vstaCount"]
                palRadio = allStaPalDicts[radio][0]['palRadio']
        associatedStatus = sd2Utils.waitForAssociation(palToUse,palRadio,timeToWait=assocWaitTime,vstasRequired=vstasRequired)
        if not associatedStatus:
                print(">>> Association not completed. Quitting.")
                sys.exit(1) # Set for SM

        endReAssocCheckTime = time.time()
        reassociationCheckTime = round(endReAssocCheckTime-startReAssocCheckTime,1)
        print('')
        print("##### Reassociation from disconnect took %s seconds." % reassociationCheckTime)
        print('##############################################################')

        resultDict['reassociationCheck'].update({"reassociationCheckTime": reassociationCheckTime})
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

#print('EXIT LINE 483')
#sys.exit()
############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

print (">>> Starting Autotest...")
Timestamp = sd2Utils.getTimestamp()

json_path = sd2Utils.runAutotest(saveCSV=False,unzip=False)
############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ############

print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')
bandDir = band+'_'+upOrDown
resultDict = {bandDir:{}}

filter ={"want": "avg"}
type = 'THROUGHPUT'
if len(attensToUse) != 0:
        result = sd2Utils.avgDataPost(type,filter,tpDictList[0],multival=True,attenName=attensToUse[0])
else:
        result = sd2Utils.avgDataPost(type, filter, tpDictList[0], multival=False)
if result:
        resultDict[bandDir].update({filter['want']:result})
        print('#########################################')
        print('>>> resultDict ', (resultDict))	
        print('#########################################')
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
else:
        print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
        print('########## ERROR! %s %s not found QUITTING' % (type,filter['want']))	
        print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
        sys.exit(1)	

filter ={"want": "rssiMgmtMean"}
type = 'PALSTATS'
if attensToUse != 0:
        result = sd2Utils.avgDataPost(type,filter,tpDictList[0],multival=True,attenName=attensToUse[0])
else:
        result = sd2Utils.avgDataPost(type, filter, tpDictList[0], multival=False)
if result:
        resultDict[bandDir].update({filter['want']:result})
        print('#########################################')
        print('>>> resultDict ', (resultDict))
        print('#########################################')
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
else:
        print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
        print('########## ERROR! %s %s not found QUITTING' % (type,filter['want']))	
        print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
        sys.exit(1)	

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
resultDict = {}
resultDict = {'testRunTime':testRunTime}
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

print('')
print('##############################################################')
print('##### Generating JSON reports')
print('##############################################################')

#Remove existing test report so that if there is a problem here, you don't get fooled into thinking that an old report is the new report.
rmResult = os.system("rm " + directory_name + "TestReport.json")
print(">>> Removed all old TestReport.json: {}".format(rmResult))

print(">>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))

'''
#Place a PDF export in the same location
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

#Cancel any testbed reservation
sd2Utils.releaseInUse()

haveCreateReport = False
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
    import createReport
    haveCreateReport = True
else:
    print("{} No createReport at {} {}".format(cRed,createReportFilePath,cNormal))
ea_root = sd2Utils.whereIsEA()    

if haveCreateReport:
    print('')
    print('##############################################################')
    print("########## Creating report ")
    print('##############################################################')	
    createReport.main(directory_name,globalsfile.outputDirPath,ea_root)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
