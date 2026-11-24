'''
Test Description
================
This test associates many vSTAs on Pal6C to a DUT in Box A.
It then breaks the connection by maximizing Box C to A path loss, then minimizes path loss to
measure reassociation time without config push time.
'''
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

# Restart all Pals
if paramsDict['restartPals']['val']:
        startPalResetTime = time.time()
        sd2Utils.restartAllPals(180,'Initialization')
        PalResetTime = int(time.time()-startPalResetTime)
        resultDict = {}
        resultDict.update({"PalResetTime":PalResetTime})
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

############### END SECTION: BUILD DICTIONARY #########################

# ##################################################################################	
# ##################################################################################
#	                             Start of main test script
# ##################################################################################
# ##################################################################################


############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################
palAsAPdrop = paramsDict["palAsAP"]["val"]
for item in palAsAPdrop:
        if item["selected"]:
                palAsAP = item["value"]
                break

pal6APbandConfig = paramsDict['pal6APbandConfig']['val']

# Build list for config check
instList = []
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]

palToUse = paramsDict['palToUse']['val']
print('')
print('##############################################################')
print("###### Pal to use for vSTAS is {}".format(palToUse))
print('##############################################################')

instList.append(palToUse)
if 'Pal' in palAsAP:
        instList.append(palAsAP)
        print('')
        print('##############################################################')
        print("###### Pal to use for AP is {}".format(palAsAP))
        print('##############################################################')

testUses=paramsDict['testUses']['val']+instList+attenList
print(">>> testUses: ", testUses)

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)

print(">>> Pulling in vSTA settings from the test parameters file.")

vstaSettings = paramsDict["vstaSettings"]["val"]
bandsFound = []
settingsPerRadio = {}
radios = []
validBandList = ['24g','5g','5Ag','5Bg','6g']
validBandwidthList = ['BANDWIDTH_ADAPT','BANDWIDTH_20_FIXED','BANDWIDTH_40_ADAPT', 'BANDWIDTH_80_ADAPT', 'BANDWIDTH_160_ADAPT']
validInterfaceList = ['INTERFACE_G', 'INTERFACE_N', 'INTERFACE_AC', 'INTERFACE_AX']
for setting in vstaSettings:
        if setting["vstaCount"] <= 0: continue
        if setting["band"] not in validBandList:
                print('!!! ERROR. Invalid band value %s. Must be %s. QUITTING!' % (setting["band"],validBandList))
                sys.exit(53)
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

        if 'Pal' in palAsAP:
                ssid     = paramsDict["pal6APssid"]["val"]
                security = paramsDict["pal6APsecurity"]["val"]
                password = paramsDict["pal6APpass"]["val"]
                if "2" in setting["band"]:
                        theBand = "24g"
                        bandsFound.append(theBand)
                        radio = "RADIO_24"
                elif setting["band"] == '5g':
                        theBand = "5g"
                        bandsFound.append(theBand)
                        radio = "RADIO_5"
                elif setting["band"] == '5Ag':
                        theBand = "5Ag"
                        bandsFound.append(theBand)
                        radio = "RADIO_5A"
                elif setting["band"] == '5Bg':
                        theBand = "5Bg"
                        bandsFound.append(theBand)
                        radio = "RADIO_5B"
                elif "6" in setting["band"]:
                        theBand = "6g"
                        bandsFound.append(theBand)
                        radio = "RADIO_6"
        else:
                if "2" in setting["band"]:
                        theBand = "24g"
                        bandsFound.append(theBand)
                        radio = "RADIO_24"
                        ssid     = paramsDict["dut"]["val"]["dutssid24"]
                        security = paramsDict["dut"]["val"]["dutsecurity24"]
                        password = paramsDict["dut"]["val"]["dutpass24"]
                elif setting["band"] == '5g':
                        theBand = "5g"
                        bandsFound.append(theBand)
                        radio = "RADIO_5"
                        ssid     = paramsDict["dut"]["val"]["dutssid5"]
                        security = paramsDict["dut"]["val"]["dutsecurity5"]
                        password = paramsDict["dut"]["val"]["dutpass5"]
                elif setting["band"] == '5Ag':
                        theBand = "5Ag"
                        bandsFound.append(theBand)
                        radio = "RADIO_5A"
                        ssid     = paramsDict["dut"]["val"]["dutssid5"]
                        security = paramsDict["dut"]["val"]["dutsecurity5"]
                        password = paramsDict["dut"]["val"]["dutpass5"]
                elif setting["band"] == '5Bg':
                        theBand = "5Bg"
                        bandsFound.append(theBand)
                        radio = "RADIO_5B"
                        ssid     = paramsDict["dut"]["val"]["dutssid5"]
                        security = paramsDict["dut"]["val"]["dutsecurity5"]
                        password = paramsDict["dut"]["val"]["dutpass5"]
                elif "6" in setting["band"]:
                        theBand = "6g"
                        bandsFound.append(theBand)
                        radio = "RADIO_6"
                        ssid     = paramsDict["dut"]["val"]["dutssid6"]
                        security = paramsDict["dut"]["val"]["dutsecurity6"]
                        password = paramsDict["dut"]["val"]["dutpass6"]


        settingsPerRadio[radio] = {
                "band": theBand,
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
        radios.append(radio)

print('>>> settingsPerRadio: ', settingsPerRadio)
print('>>> radios: ', radios)

# Check that vstaSettings bands match pal6APbandConfig
if pal6APbandConfig == "BAND_TRI" and ('5Ag' not in bandsFound or '5Bg' not in bandsFound):
        funcName = 'MainScript'
        message = 'pal6APbandConfig set to tri-band but band not defined in vstaSettings. \nCheck and correct params_test and test arguement JSONS'
        sd2Utils.failHandler(funcName,message)


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
resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp, "security":security, "ssid":ssid, "password":password,  "vstaWaitMore":vstaWaitMore})
resultDict['testInfo'].update({"palAsAP":palAsAP,"pal6APbandConfig":pal6APbandConfig})
if 'RADIO_24' in settingsPerRadio.keys(): 
        resultDict['testInfo'].update({"24g_vStaSettings": settingsPerRadio['RADIO_24']})
if 'RADIO_5' in settingsPerRadio.keys(): 
        resultDict['testInfo'].update({"5g_vStaSettings": settingsPerRadio['RADIO_5']})
if 'RADIO_5A' in settingsPerRadio.keys(): 
        resultDict['testInfo'].update({"5Ag_vStaSettings": settingsPerRadio['RADIO_5A']})
if 'RADIO_5B' in settingsPerRadio.keys(): 
        resultDict['testInfo'].update({"5Bg_vStaSettings": settingsPerRadio['RADIO_5B']})
if 'RADIO_6' in settingsPerRadio.keys(): 
        resultDict['testInfo'].update({"6g_vStaSettings": settingsPerRadio['RADIO_6']})
resultDict['testInfo'].update({"scriptSuiteVersion":globalsfile.scriptSuiteVersion})
resultDict['testInfo'].update({"starDustVersion":globalsfile.starDustVersion})
resultDict['testInfo'].update({"palFWversions":globalsfile.palFWdict})
if test_param_alt_file:
        resultDict['testInfo'].update({"testParamAltFile":test_param_alt_file})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

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
attensToUse = []
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63,False)
sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63,False)
attensToUse.append(attenToUseA)

print('')
print('##############################################################')
print("########## Setting up Attenuators DONE ")
print('##############################################################')

if 'Pal' in palAsAP:
        # Set up Pal-6A as AP
        apDictList = []
        print('')
        print('##############################################################')
        print("########## Setting up %s as AP." % palAsAP)
        print('##############################################################')

        ssid     = paramsDict["pal6APssid"]["val"]
        security = paramsDict["pal6APsecurity"]["val"]
        password = paramsDict["pal6APpass"]["val"]

        # 2.4 GHz radio
        if paramsDict['pal6APchannel_24g']['val'] > 0:
                apDictList = sd2Utils.setupAP(palAsAP, '24g', apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel_24g']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_40_ADAPT", "ssid":ssid, "password": password, "security":security})
                resultDict['testInfo'].update({"2.4GHzChannelToTest":paramsDict['pal6APchannel_24g']['val']})

        # 5 GHz radio (dual-band)
        if pal6APbandConfig == 'BAND_DUAL':
                if paramsDict['pal6APchannel_5g']['val'] > 0:
                        apDictList = sd2Utils.setupAP(palAsAP, '5g', apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel_5g']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT", "ssid":ssid, "password": password, "security":security})
                        resultDict['testInfo'].update({"5GHzChannelToTest":paramsDict['pal6APchannel_5g']['val']})
                else:
                        funcName = 'MainScript'
                        message = "Dual band (5g) mode set but channel=0. Set paramsDict['pal6APchannel_5g']['val'] > 0."
                        sd2Utils.failHandler(funcName,message)

        # 5 GHz A radio (tri-band)
        if pal6APbandConfig == 'BAND_TRI':
                if paramsDict['pal6APchannel_5Ag']['val'] > 0:
                        apDictList = sd2Utils.setupAP(palAsAP, "5Ag", apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel_5Ag']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT", "ssid":ssid, "password": password, "security":security})
                        resultDict['testInfo'].update({"5GHzAChannelToTest":paramsDict['pal6APchannel_5Ag']['val']})
                else:
                        funcName = 'MainScript'
                        message = "Tri band (5g) mode set but 5Ag channel=0. Set paramsDict['pal6APchannel_5Ag']['val'] > 0."
                        sd2Utils.failHandler(funcName,message)

        # 5 GHz B radio (tri-band)
        if pal6APbandConfig == 'BAND_TRI':
                if paramsDict['pal6APchannel_5Bg']['val'] > 0:
                        apDictList = sd2Utils.setupAP(palAsAP, "5Bg", apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel_5Bg']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT", "ssid":ssid, "password": password, "security":security})
                        resultDict['testInfo'].update({"5GHzBChannelToTest":paramsDict['pal6APchannel_5Bg']['val']})
                else:
                        funcName = 'MainScript'
                        message = "Tri band (5g) mode set but 5Bg channel=0. Set paramsDict['pal6APchannel_5Bg']['val'] > 0."
                        sd2Utils.failHandler(funcName,message)

        if paramsDict[palAsAP]['val']['isPal6E']:
                # 6 GHz radio
                if paramsDict['pal6APchannel6g']['val'] > 0:
                        apDictList =sd2Utils.setupAP(palAsAP, "6g", apDictList, type = "INTERFACE_AX", channel=paramsDict['pal6APchannel6g']['val'], bandConfig=pal6APbandConfig, apBridge= True, apDictOverride={"bandwidth":"BANDWIDTH_160_ADAPT",  "ssid":ssid, "password": password, "security":security})
                        #primaryChannel = paramsDict['pal6APchannel6g']['val']
                        resultDict['testInfo'].update({"6GHzChannelToTest":paramsDict['pal6APchannel6g']['val']})

        pp.pprint(apDictList)
        #sys.exit()

        palType = "pal6s"
        if paramsDict[palAsAP]["val"]["devType"] == "pal7": palType = "pal7s"

        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)	
        sd2Utils.updateAutotestInst(apDictList, palType, timeoutOverride=150, pushConfig=True) # update config and push. Wait longer for tri-band push
        print('')
        print('##############################################################')
        print("########## Setting up %s as AP. DONE." % palAsAP)
        print('##############################################################')
#print('>>> EXIT at LINE 412')
#sys.exit()

startvStaSetupTime = time.time()
allVstaConfigs = {}
allTpConfigs = {}

allVstaConfigs[palToUse] = {}
allTpConfigs[palToUse] = {}
tpDictList = []
for radio in radios:
        print('')
        print('##############################################################')
        print("############ Setting up {} vSTAs for Pal {} on radio {}".format(settingsPerRadio[radio]["vstaCount"],palToUse,radio))
        print('##############################################################')
        radioBand = radio.split('_')[1]
        print('>>> radioBand: ', radioBand)
        trafficPairs = paramsDict["trafficPairs"]["val"]
        i = 0
        for pair in trafficPairs:
                i += 1
                doPush = False
                if i==len(trafficPairs): doPush = True
                if pair["band"] not in bandsFound:
                        funcName = 'MainScript'
                        message = 'Band '+pair["band"]+' not found in vstaSettings, but found in trafficPairs. \nCheck and correct params_test and test arguement JSONS'
                        sd2Utils.failHandler(funcName,message)
                """
                if "2" in pair["band"]: theBand = "24g"
                if "5g" in pair["band"]: theBand = "5g"
                if "5Ag" in pair["band"]: theBand = "5Ag"
                if "5Bg" in pair["band"]: theBand = "5Bg"
                if "6" in pair["band"]: theBand = "6g"
                """
                pairBand = pair["band"]
                print('>>> pairBand: ', pairBand)

                if "u" in pair["updn"]: updn = "up"
                if "d" in pair["updn"]: updn = "dn"

                tpDictOverride = {}
                if "trafficType" in pair: tpDictOverride["trafficType"] = pair["trafficType"]
                if "packetType"  in pair: tpDictOverride["udp"]         = pair["packetType"]
                if "trafficRate" in pair: tpDictOverride["bitrate"]     = pair["trafficRate"]
                if "packetSize"  in pair: tpDictOverride["length"]      = pair["packetSize"]
                if "trafficStreams" in pair: tpDictOverride["ipStreams"]= pair["trafficStreams"]
                if "windowSize" in pair: tpDictOverride["window"]      = pair["windowSize"]
                if "pingInterval" in pair: tpDictOverride["interval"]   = pair["pingInterval"]
                if "advanced" in pair:
                        tpDictOverride["advanced"]    = pair["advanced"]
                        if "isochronous" in pair: tpDictOverride["isochronous"] = pair["isochronous"]
                        if "dscp"        in pair: tpDictOverride["dscp"]        = pair["dscp"]
                        if "iso_gap"     in pair: tpDictOverride["ipg"]         = pair["iso_gap"]
                        if "iso_mean"    in pair: tpDictOverride["mean"]        = pair["iso_mean"]
                        if "iso_stdev"   in pair: tpDictOverride["stdev"]       = pair["iso_stdev"]
                        if "iso_fps"     in pair: tpDictOverride["fps"]         = pair["iso_fps"]
                print('')
                print('>>> tpDictOverride for ',pair)
                pp.pprint(tpDictOverride)

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
                if radioBand in pairBand:	# Only create vSTAs if bands match
                        (vstaConfigList,tpDictList) = sd2Utils.setupVsta(palToUse, settingsPerRadio[radio]["band"], settingsPerRadio[radio]["primaryChannel"], updn, pair["trafficType"], settingsPerRadio[radio]["vstaCount"], vstaParams, tpDictList, tpDictOverride=tpDictOverride, startTpAt1=True)
                        allVstaConfigs[palToUse][radio] = vstaConfigList
                        allTpConfigs[palToUse][radio] = tpDictList
                        if paramsDict['debug']['val']:
                                print('')
                                print('##############################################################')
                                print('>>> i: ', i)
                                print('>>> pair: ', pair)
                                print('>>> radio: ', radio)
                                print('>>> allVstaConfigs: ')
                                pp.pprint(allVstaConfigs)
                                print('>>> allTpConfigs: ')
                                pp.pprint(allTpConfigs)
                                print('>>> Length tpDictList: ', len(tpDictList))
                                print('>>> tpDictList: ')
                                pp.pprint(tpDictList)
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

print('')
print('##############################################################')
print('>>> i: ', i)
print('>>> pair: ', pair)
print('>>> radio: ', radio)
print('>>> allVstaConfigs: ')
pp.pprint(allVstaConfigs)
#print('>>> allTpConfigs: ')
#pp.pprint(allTpConfigs)
print('>>> Length tpDictList: ', len(tpDictList))
print('>>> tpDictList: ')
pp.pprint(tpDictList)
print('##############################################################')

#print('>>> EXIT at LINE 527')
#sys.exit()

resultDict = {}
resultDict.update({"vstaTrafficPairConfigCreateTime": vstaTrafficPairConfigCreateTime})
resultDict.update({"vstaTrafficPairConfigPushTime": vstaTrafficPairConfigPushTime})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

startStaSetupTime = time.time()

allStaPalDicts = {}
staPalDictList = []

allStaPalDicts[palToUse] = {}
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
                #"vstaConfig": vstaConfigList
                "vstaConfig": allVstaConfigs[palToUse][radio]
        }

        staPalDictList = sd2Utils.setupSTA(palToUse,settingsPerRadio[radio]["band"], staPalDictList, streams=settingsPerRadio[radio]["streams"], channel=settingsPerRadio[radio]["primaryChannel"], bandConfig=pal6APbandConfig, staDictOverride=overrideDict, timeoutOverride=REST_TIMEOUT+settingsPerRadio[radio]["vstaWaitMore"], startTpAt1=True)
        allStaPalDicts[palToUse][radio] = staPalDictList
        if paramsDict['debug']['val']:
                print('>>> staPalDictList: ' )
                pp.pprint(staPalDictList)

# Build radio alias list for stats later
staAliasList = []
for dict in staPalDictList:
        staAliasList.append(dict['alias'])
print('\n>>> staAliasList: ', staAliasList)
#print('>>> EXIT at LINE 568')
#sys.exit()

endStaSetupTime = time.time()
print('>>> Timeout override for setupSTA push: ', str(REST_TIMEOUT+totalVstaWait))
palType = "pal6s"
if paramsDict[palToUse]["val"]["devType"] == "pal7": palType = "pal7s"
sd2Utils.updateAutotestInst(staPalDictList, palType, pushConfig=True, timeoutOverride=REST_TIMEOUT+totalVstaWait) # update config and push
endStaSetupPushTime = time.time()

staConfigCreateTime = round((endStaSetupTime-startStaSetupTime),1)
staConfigPushTime = round((endStaSetupPushTime-endStaSetupTime),1)
print('')
print('##############################################################')
print("########## Setting up STAs DONE")
print('########## Time to create pal config: %s' % staConfigCreateTime)
print('########## Time to push pal config: %s' % staConfigPushTime)
print('##############################################################')
resultDict = {}
resultDict.update({"staConfigCreateTime": staConfigCreateTime})
resultDict.update({"staConfigPushTime": staConfigPushTime})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################


for radio in radios:
        palRadio = allStaPalDicts[palToUse][radio][0]['palRadio']
        palAlias = allStaPalDicts[palToUse][radio][0]['alias']
        print('')
        print('##############################################################')
        print("########## Associating {} vSTAs on {}, radio {} ".format(settingsPerRadio[radio]["vstaCount"], palToUse,radio))
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
        associatedStatus = sd2Utils.waitForAssociation(palToUse,palRadio,timeToWait=assocWaitTime,vstasRequired=settingsPerRadio[radio]["vstaCount"])
        if not associatedStatus:
                print(">>> runRvR: Association not completed. Quitting.")
                sys.exit(1) # Set for SM

        print('')
        print('##############################################################')
        print("########## Associating vSTAs DONE for {} on radio {}".format(palToUse,radio))
        print('##############################################################')
        print('')

endAssocTime = time.time()
timePushToAssociateDone = round((endAssocTime-endStaSetupPushTime),1)
print('')
print('##############################################################')
print("########## Associating all vSTAs DONE on all Pals and radios")
print('########## Time from push done to all vSTAs associated: %s' % timePushToAssociateDone)
print('##############################################################')

resultDict = {}
resultDict.update({"timePushToAssociateDone": timePushToAssociateDone})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)


############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

print (">>> Starting Autotest...")
Timestamp = sd2Utils.getTimestamp()
json_path = sd2Utils.runAutotest(traceback=True)
############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ############
if '6C' in palToUse:
        attenToUse = attenToUseA
# NOTE: 6/2/22 This needs work. But for now, we'll save something.

# Make sure attenToUse not None
for atten in attensToUse:
        if atten:
                attenToUse = atten

print()
print('#########################################')
print('>>> Getting test results')
print('>>> attenToUse: ', attenToUse)
print('#########################################')

tpt24dnList = []
tpt24upList = []
tpt5AdnList = []
tpt5AupList = []
tpt5BdnList = []
tpt5BupList = []
tpt6dnList = []
tpt6upList = []

for tpDict in tpDictList:
        resultDict = {tpDict['alias']:{}}
        filter ={"want": "avg"}
        type = 'THROUGHPUT'
        if attenToUse != 'None':
                result = sd2Utils.avgDataPost(type,filter,tpDict,multival=True,attenName=attenToUse)
        else:
                result = sd2Utils.avgDataPost(type,filter,tpDict,multival=False)
        # Build throughput list for totals
        if result:
                print('>>> result: ', result)
                if '24' in tpDict['alias'] and 'ServerTo' in tpDict['alias']:
                        tpt24dnList.append(result[0]['value'])
                elif '24' in tpDict['alias'] and 'ToServer' in tpDict['alias']:
                        tpt24upList.append(result[0]['value'])
                elif '5A' in tpDict['alias'] and 'ServerTo' in tpDict['alias']:
                        tpt5AdnList.append(result[0]['value'])
                elif '5A' in tpDict['alias'] and 'ToServer' in tpDict['alias']:
                        tpt5AupList.append(result[0]['value'])
                elif '5B' in tpDict['alias'] and 'ServerTo' in tpDict['alias']:
                        tpt5BdnList.append(result[0]['value'])
                elif '5B' in tpDict['alias'] and 'ToServer' in tpDict['alias']:
                        tpt5BupList.append(result[0]['value'])
                elif '6' in tpDict['alias'] and 'ServerTo' in tpDict['alias']:
                        tpt6dnList.append(result[0]['value'])
                elif '6' in tpDict['alias'] and 'ToServer' in tpDict['alias']:
                        tpt6upList.append(result[0]['value'])

                resultDict[tpDict['alias']].update({filter['want']:result})
                print('#########################################')
                print('>>> resultDict ', (resultDict))	
                print('#########################################')
                sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
        else:
            print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
            print('########## ERROR! %s %s not found QUITTING' % (type,filter['want']))	
            print('!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*!*')
            sys.exit(1)	

        if tpt24dnList:
                tpt24dnTotal = round(sum(tpt24dnList),2)
                sd2Utils.logToJSON(globalsfile.resultsPath, {'tpt24dnTotal':tpt24dnTotal,'tpt24dnList':tpt24dnList})
        if tpt24upList:
                tpt24upTotal = round(sum(tpt24upList),2)
                sd2Utils.logToJSON(globalsfile.resultsPath, {'tpt24upTotal':tpt24upTotal,'tpt24upList':tpt24upList})
        if tpt5AdnList:
                tpt5AdnTotal = round(sum(tpt5AdnList),2)
                sd2Utils.logToJSON(globalsfile.resultsPath, {'tpt5AdnTotal':tpt5AdnTotal,'tpt5AdnList':tpt5AdnList})
        if tpt5AupList:
                tpt5AupTotal = round(sum(tpt5AupList),2)
                sd2Utils.logToJSON(globalsfile.resultsPath, {'tpt5AupTotal':tpt5AupTotal,'tpt5AupList':tpt5AupList})
        if tpt5BdnList:
                tpt5BdnTotal = round(sum(tpt5BdnList),2)
                sd2Utils.logToJSON(globalsfile.resultsPath, {'tpt5BdnTotal':tpt5BdnTotal,'tpt5BdnList':tpt5BdnList})
        if tpt5BupList:
                tpt5BupTotal = round(sum(tpt5BupList),2)
                sd2Utils.logToJSON(globalsfile.resultsPath, {'tpt5BupTotal':tpt5BupTotal,'tpt5BupList':tpt5BupList})
        if tpt6dnList:
                tpt6dnTotal = round(sum(tpt6dnList),2)
                sd2Utils.logToJSON(globalsfile.resultsPath, {'tpt6dnTotal':tpt6dnTotal,'tpt6dnList':tpt6dnList})
        if tpt6upList:
                tpt6upTotal = round(sum(tpt6upList),2)
                sd2Utils.logToJSON(globalsfile.resultsPath, {'tpt6upTotal':tpt6upTotal,'tpt6upList':tpt6upList})


        filter ={"want": "rssiMgmtMean"}
        type = 'PALSTATS'
        if attenToUse != 'None':
                result = sd2Utils.avgDataPost(type,filter,tpDict,multival=True,attenName=attenToUse)
        else:
                result = sd2Utils.avgDataPost(type,filter,tpDict,multival=False)
        if result:
                    resultDict[tpDict['alias']].update({filter['want']:result})
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

print(">>> Zipped file of all JSONs at: {}".format(json_path))

print("\n>>> Creating PDF of Test HTML report")
#Place a PDF export in the same location
pdf_dict = {
"showAll": False,
"plotList": ['Throughput','congestion','%load','mgmtRssi','DataRssiChains','DataRssiStatus','rate','mcs','Streams','bandwidth','txpriority','rxpriority','missingack']
}
URL = "http://" + "{}:4000".format(paramsDict["oBox_server"]["val"]["publicip"]) + "/api/v1/reports/pdf/{}".format(testName)
pdf_report = requests.post(URL,json=pdf_dict,timeout=REST_TIMEOUT)
pdf_path = json_path.replace(".zip",".pdf")
with open(pdf_path, 'wb') as f:
        for chunk in pdf_report.iter_content(chunk_size=1024):
                if chunk:
                        f.write(chunk)
print(">>> PDF file at: {}".format(pdf_path))

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
    createReport.analyze(directory_name,globalsfile.outputDirPath,json_path,ea_root)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	

