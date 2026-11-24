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

############### END SECTION: BUILD DICTIONARY #########################

# ##################################################################################	
# ##################################################################################
#	                             Start of main test script
# ##################################################################################
# ##################################################################################

haveCreateReport = False
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
    haveCreateReport = True
    import createReport

############################
# Set up some text coloring
cRed=   '\033[m'
cGreen= '\033[m'
cNormal='\033[m'

############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

# Build list for config check
instList = []
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]

print(">>> Pulling in vSTA settings from the test parameters file.")
vstaSettings = paramsDict["vstaSettings"]["val"]
print(vstaSettings)
palsToUse = []
for palToUse in vstaSettings:
    countVstas = 0
    for bandInfo in vstaSettings[palToUse]:
        countVstas += bandInfo["vstaCount"]
    print("Total vSTA count for {} is {}".format(palToUse,countVstas))
    if countVstas > 0: palsToUse.append(palToUse)
print('')
print('##############################################################')
print("########## List of Pals to use is {}".format(palsToUse))
print('##############################################################')

for palToUse in palsToUse: 
        instList.append(palToUse)

palToUseAP = paramsDict['palToUseAP']['val']
if palToUseAP not in paramsDict:  palToUseAP = None

testUses=instList+attenList
if palToUseAP: testUses += [palToUseAP]
print(">>> testUses: ", testUses)

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)

#Set up the AP if required.
if palToUseAP:
    thisType = paramsDict[palToUseAP]["val"]["devType"]
    thisList = "{}s".format(thisType)
    apDictList = []
    theBands = ["24","5","6"]
    for band in theBands:
        didIt = False
        for palToUse in palsToUse:
            if didIt: break
            for setting in vstaSettings[palToUse]:
                if band in setting["band"]:
                    if setting["vstaCount"]>0:
                        radio = "RADIO_{}".format(band)
                        ssid = paramsDict["dut"]["val"]["dutssid{}".format(band)]
                        password = paramsDict["dut"]["val"]["dutpass{}".format(band)]
                        security = paramsDict["dut"]["val"]["dutsecurity{}".format(band)]
                        UseBand = setting["band"]
                        bandwidth = setting["bandwidth"]
                        interface = setting["interface"]
                        #if band == "5g":
                        #if setting["primaryChannel"] < 100: UseBand = "5Bg"
                        #else: UseBand = "5Ag"
                        useThisBridgeAddress = paramsDict[palToUseAP]['val']['endpoints']["RADIO_24"]['defaultIp']  #All radios on a single Pal must have the same bridge address.  So pick one.
                        apDictOverride = {"ssid":ssid}
                        apDictOverride["password"]=password
                        apDictOverride["security"]=security
                        apDictOverride["bandwidth"] = bandwidth
                        apDictOverride["ipAddressBridge"] = useThisBridgeAddress
                        if thisType == "pal7": apDictOverride["bandConfig"] = ""
                        #Setting up AP configurations:
                        print("Setting up {} as AP using band {} with ssid {} password {} security {}".format(palToUseAP,UseBand,ssid,password,security))
                        apDictList = sd2Utils.setupAP(palToUseAP, UseBand, apDictList, type=interface, channel=setting["primaryChannel"], streams=setting["streams"], apBridge= True, pushConfig=False, apDictOverride=apDictOverride)
                        didIt = True
                        break
                    else:
                        print("You cannot configure an AP with a channel number of '0'.  You need to configure an allowed channel number in params_test for band {}".format(band))

    #print(json.dumps(apDictList,indent=3))
    sd2Utils.updateAutotestInst(apDictList, thisList, pushConfig=True) # update config and push

settingsPerRadio = {}
radios = {}
validBandList = ['24g','2.4g','5g','6g']
validBandwidthList = ['BANDWIDTH_ADAPT','BANDWIDTH_20_FIXED','BANDWIDTH_40_ADAPT', 'BANDWIDTH_80_ADAPT', 'BANDWIDTH_160_ADAPT', 'BANDWIDTH_320_ADAPT']
validInterfaceList = ['INTERFACE_G', 'INTERFACE_N', 'INTERFACE_AC', 'INTERFACE_AX', 'INTERFACE_BE']
for palToUse in palsToUse:
    settingsPerRadio[palToUse] = {}
    radios[palToUse] = []
    for setting in vstaSettings[palToUse]:
        if setting["vstaCount"] <= 0: continue
        if setting["band"] not in validBandList:
            print('!!! ERROR. Pal %s, Invalid band value %s. Must be %s. QUITTING!' % (palToUse,setting["band"],validBandList))
            sys.exit(53)
        if "24" in setting["band"] or "2.4" in setting["band"]:
            radio = "RADIO_24"
            ssid = paramsDict["dut"]["val"]["dutssid24"]
            password = paramsDict["dut"]["val"]["dutpass24"]
            security = paramsDict["dut"]["val"]["dutsecurity24"]
        if setting["band"] == '5g':
            radio = "RADIO_5"
            ssid = paramsDict["dut"]["val"]["dutssid5"]
            password = paramsDict["dut"]["val"]["dutpass5"]
            security = paramsDict["dut"]["val"]["dutsecurity5"]
        if "5A" in setting["band"]:
            radio = "RADIO_5A"
            ssid = paramsDict["dut"]["val"]["dutssid5"]
            password = paramsDict["dut"]["val"]["dutpass5"]
            security = paramsDict["dut"]["val"]["dutsecurity5"]
        if "5B" in setting["band"]:
            radio = "RADIO_5B"
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
            print('!!! ERROR. Pal %s, Invalid bandwidth value %s. Must be %s. QUITTING!' % (palToUse,setting["bandwidth"],validBandwidthList))
            sys.exit(53)
        bandwidth = setting["bandwidth"]
        if setting["interface"] not in validInterfaceList:
            print('!!! ERROR. Pal %s, Invalid interface value %s. Must be %s. QUITTING!' % (palToUse,setting["interface"],validInterfaceList))
            sys.exit(53)
        interface = setting["interface"]

        if setting["streams"] < 1 or setting["streams"] > 8:
            print('!!! ERROR. Pal %s, Invalid streams value %s. Must be 1-8. QUITTING!' % (palToUse,setting["streams"]))
            sys.exit(53)

        settingsPerRadio[palToUse][radio] = {
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
        radios[palToUse].append(radio)


#print('>>> settingsPerRadio: ', settingsPerRadio)
#print(radios)

upOrDowndrop = paramsDict["upOrDown"]["val"]
for item in upOrDowndrop:
    if item["selected"]:
        upOrDown = item["value"]
        break

histogramMode = paramsDict["histograms"]["val"]
binCount =      paramsDict["binCount"]["val"]
binWidth =      paramsDict["binWidth"]["val"]
lowerCi =       paramsDict["lowerCi"]["val"]
upperCi =       paramsDict["upperCi"]["val"]

trafficType = paramsDict["trafficType"]["val"]
trafficMode = paramsDict["trafficMode"]["val"]
iperfMode = trafficMode
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


# Calculate additional wait time for vSTA config push and association
totalVstaWait = {}
for palToUse in palsToUse:
    totalVstaWait[palToUse] = 0
    print('')
    print('##############################################################')
    for radio in radios[palToUse]:
        vstaWaitMore = settingsPerRadio[palToUse][radio]["vstaCount"]*paramsDict["vstaWait"]["val"]
        totalVstaWait[palToUse] += vstaWaitMore
        settingsPerRadio[palToUse][radio]["vstaWaitMore"] = vstaWaitMore
        print(">>> For Pal {}, Adding {} seconds to association and config push waits for radio {}.".format(palToUse,vstaWaitMore,radio))

        print(">>> Adding TOTAL of %s seconds to association and config push waits." % totalVstaWait[palToUse])
        print('##############################################################')

print("Here are the final totalVstaWait values: {}".format(totalVstaWait))
cumulativeWaitTime = 0
for pal in totalVstaWait: cumulativeWaitTime += totalVstaWait[pal]
print("Here is the cumulative wait time to handle all of these vstas: {}".format(cumulativeWaitTime))

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
resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp, "security":security, "ssid":ssid, "password":password, "trafficType": paramsDict['trafficType']['val'], "trafficMode":paramsDict['trafficMode']['val'], "upOrDown": upOrDown, "vstaWaitMore":vstaWaitMore})
for palToUse in palsToUse:
    if 'RADIO_24' in settingsPerRadio[palToUse].keys():
        resultDict['testInfo'].update({palToUse:{"24g_vStaSettings": settingsPerRadio[palToUse]['RADIO_24']}})
    if 'RADIO_5A' in settingsPerRadio[palToUse].keys(): 
        resultDict['testInfo'].update({palToUse:{"5g_vStaSettings": settingsPerRadio[palToUse]['RADIO_5A']}})
    if 'RADIO_6' in settingsPerRadio[palToUse].keys():
        resultDict['testInfo'].update({palToUse:{"6g_vStaSettings": settingsPerRadio[palToUse]['RADIO_6']}})
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
sd2Utils.updateAutotest(tmpdict, pushConfig=True,timeoutOverride=REST_TIMEOUT+cumulativeWaitTime)

print('')
print('##############################################################')
print("########## Setting up Attenuators START ")
print('##############################################################')
sd2Utils.isolateAllBoxes()
attensToUse = []
for palToUse in palsToUse:
        if "6C" in palToUse or "7C" in palToUse:
                (attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
                sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63,False)
                sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],63,False)
                attensToUse.append(attenToUseA)

        if "6B" in palToUse or "7B" in palToUse: 
                attenToUse = "QA-D"
                sd2Utils.setAtten(attenToUse,paramsDict[attenToUse]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],False)
                attensToUse.append(attenToUse)

        if "6D" in palToUse or "7D" in palToUse: 
                attenToUse = "QA-C"
                sd2Utils.setAtten(attenToUse,paramsDict[attenToUse]["val"]["devType"],paramsDict["quadAttenStart"]["val"],paramsDict["quadAttenStop"]["val"],False)
                attensToUse.append(attenToUse)

        if "6A" in palToUse or "7A" in palToUse:
                attenToUse = "None"
                attensToUse.append(attenToUse)
                #You can do this, but this Pal6 is in Box A, so it cannot be attenuated relative to the DUT, which is assumed to be in Box A.


print('')
print('##############################################################')
print("########## Setting up Attenuators DONE ")
print('##############################################################')

startvStaSetupTime = time.time()
allVstaConfigs = {}
allTpConfigs = {}
alltpDictList = []
for palToUse in palsToUse:
        allVstaConfigs[palToUse] = {}
        allTpConfigs[palToUse] = {}
        tpDictList = []
        for radio in radios[palToUse]:
                print('')
                print('##############################################################')
                print("############ Setting up {} vSTAs for Pal {} on radio {}".format(settingsPerRadio[palToUse][radio]["vstaCount"],palToUse,radio))
                print('##############################################################')

                vstaParams = {
                        "interface_": settingsPerRadio[palToUse][radio]["interface"],
                        "bandwidth": settingsPerRadio[palToUse][radio]["bandwidth"],
                        "certFilename": '',
                        "radiusIdentity": '',
                        "radiusPassword": '',
                        "security": settingsPerRadio[palToUse][radio]["security"],
                        "ssid": settingsPerRadio[palToUse][radio]["ssid"],
                        "streams": settingsPerRadio[palToUse][radio]["streams"],
                        "txAtten": settingsPerRadio[palToUse][radio]["txAtten"]
                }

                tpDictOverride = {}
                
                tpDictOverride["histogram"] = histogramMode
                tpDictOverride["binCount"] = str(binCount)
                tpDictOverride["binWidth"]= str(binWidth)
                tpDictOverride["lowerCi"] =  str(lowerCi)
                tpDictOverride["upperCi"] = str(upperCi)
                
                tpDictOverride["trafficType"] = trafficType
                tpDictOverride["udp"] = iperfMode
                tpDictOverride["bitrate"] = trafficBW
                tpDictOverride["length"] = length
                tpDictOverride["ipStreams"] = parallel
                tpDictOverride["window"] = window
                tpDictOverride["advanced"] = trafficAdvanced
                if tpDictOverride["advanced"]:
                    tpDictOverride["isochronous"] = isochronous
                    tpDictOverride["dscp"] = dscp
                    tpDictOverride["ipg"] = iso_gap
                    tpDictOverride["mean"] = iso_mean
                    tpDictOverride["stdev"] = iso_stdev
                    tpDictOverride["fps"] = iso_fps                            

                (vstaConfigList,tpDictList) = sd2Utils.setupVsta(palToUse, settingsPerRadio[palToUse][radio]["band"], settingsPerRadio[palToUse][radio]["primaryChannel"], upOrDown, paramsDict['trafficMode']['val'], settingsPerRadio[palToUse][radio]["vstaCount"], vstaParams, tpDictList, startTpAt1=True,palAsAP=palToUseAP,tpDictOverride=tpDictOverride)
                allVstaConfigs[palToUse][radio] = vstaConfigList
                allTpConfigs[palToUse][radio] = tpDictList
                alltpDictList += tpDictList
                if paramsDict['debug']['val']:
                        print('')
                        print('##############################################################')
                        print('>>> radio: ', radio)
                        print('>>> allVstaConfigs: ', allVstaConfigs)
                        print('>>> allTpConfigs: ', allTpConfigs)
                        print('>>> tpDictList: ', tpDictList)
                        print('>>> alltpDictList: ')
                        pp.pprint(alltpDictList)
                        print('##############################################################')
endvStaSetupTime = time.time()

sd2Utils.updateAutotestInst(alltpDictList, 'trafficPairs', pushConfig=True) # update config and push

endvStaTrafficPairPushTime = time.time()
vstaTrafficPairConfigCreateTime = round((endvStaSetupTime-startvStaSetupTime),1)
vstaTrafficPairConfigPushTime = round((endvStaTrafficPairPushTime-endvStaSetupTime),1)

print('')
print('##############################################################')
print("########## Setting up vSTAs DONE")
print('########## Time to create all vSTA traffic pairs: %s' % vstaTrafficPairConfigCreateTime)
print('########## Time to push all vSTA traffic pair config: %s' % vstaTrafficPairConfigPushTime)
#print('>>> allVstaConfigs: ', allVstaConfigs)
#print('>>> allTpConfigs: ', allTpConfigs)
#print('>>> tpDictList: ', tpDictList)
#print('>>> alltpDictList:')
#pp.pprint(alltpDictList)
print('##############################################################')
resultDict = {}
resultDict.update({"vstaTrafficPairConfigCreateTime": vstaTrafficPairConfigCreateTime})
resultDict.update({"vstaTrafficPairConfigPushTime": vstaTrafficPairConfigPushTime})
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

startStaSetupTime = time.time()

allStaPalDicts = {}
staPalDictList = []
for palToUse in palsToUse:
        allStaPalDicts[palToUse] = {}
        for radio in radios[palToUse]:
                print('')
                print('##############################################################')
                print("########## Set up {}, radio {}".format(palToUse,radio))
                print('##############################################################')
                overrideDict = {
                        "bandwidth": settingsPerRadio[palToUse][radio]["bandwidth"],
                        "interface_": settingsPerRadio[palToUse][radio]["interface"],
                        "ssid": settingsPerRadio[palToUse][radio]["ssid"],
                        "password": settingsPerRadio[palToUse][radio]["password"],
                        "security":settingsPerRadio[palToUse][radio]["security"],
                        "vstaCount": settingsPerRadio[palToUse][radio]["vstaCount"],
                        #"vstaConfig": vstaConfigList
                        "vstaConfig": allVstaConfigs[palToUse][radio]
                }

                staPalDictList = sd2Utils.setupSTA(palToUse,settingsPerRadio[palToUse][radio]["band"], staPalDictList, streams=settingsPerRadio[palToUse][radio]["streams"], channel=settingsPerRadio[palToUse][radio]["primaryChannel"], staDictOverride=overrideDict, timeoutOverride=REST_TIMEOUT+settingsPerRadio[palToUse][radio]["vstaWaitMore"], startTpAt1=True)
                allStaPalDicts[palToUse][radio] = staPalDictList
                if paramsDict['debug']['val']:
                        print('>>> staPalDictList: ' )
                        pp.pprint(staPalDictList)

        
        endStaSetupTime = time.time()
        if 'Pal' in palToUse or True:
            if paramsDict[palToUse]['val']['devType'] == "pal7":
                palType = "pal7s"
            else:
                palType = "pal6s"

        doPush = False
        if palToUse == palsToUse[len(palsToUse)-1]: doPush=True
        theWait = REST_TIMEOUT+totalVstaWait[palToUse]
        if doPush: theWait = REST_TIMEOUT+cumulativeWaitTime
        print("For Pal {}, calling updateAutotestInst for {}, with a timeout of {}".format(palToUse,palType,theWait))
        sd2Utils.updateAutotestInst(staPalDictList, palType, pushConfig=doPush, timeoutOverride=theWait) # update config and push
        
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

palVstaInformation = {}

for palToUse in palsToUse:

    palVstaInformation[palToUse] = {}

    for radio in radios[palToUse]:

        palRadio = allStaPalDicts[palToUse][radio][0]['palRadio']
        palAlias = allStaPalDicts[palToUse][radio][0]['alias']

        palVstaInformation[palToUse][radio] = []
        
        print('')
        print('##############################################################')
        print("########## Associating {} vSTAs on {}, radio {} ".format(settingsPerRadio[palToUse][radio]["vstaCount"], palToUse,radio))
        print('##############################################################')
        
        associatedStatus = False
        assocWaitTime = 30+settingsPerRadio[palToUse][radio]["vstaWaitMore"]
        band = settingsPerRadio[palToUse][radio]["band"]
        #print('>>> band: ', band)
        if band: # Make sure not None
            if '6' in band:
                assocWaitTime = 40+settingsPerRadio[palToUse][radio]["vstaWaitMore"]	# 6 GHz takes longer to associate
            print('')
            print('##############################################################')
            print('>>> assocWaitTime_'+radio+': ', assocWaitTime)
            print('##############################################################')

            palRadio = radio
            associatedStatus = sd2Utils.waitForAssociation(palToUse,palRadio,timeToWait=assocWaitTime,vstasRequired=settingsPerRadio[palToUse][radio]["vstaCount"])
            if not associatedStatus:
                print(">>> Association not completed. Quitting.")
                sys.exit(1) # Set for SM

            print('')
            print('##############################################################')
            print("########## Associating vSTAs DONE for {} on radio {}".format(palToUse,radio))
            print('##############################################################')
            print('')

            vstaStatus = globalsfile.palStatus["vstaStatus"]
            for vsta in vstaStatus: palVstaInformation[palToUse][radio].append({"MAC":vsta["macAddress"],"IP":vsta["ipAddress"],"status":vsta["radioState"]})
            
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
json_path = sd2Utils.runAutotest(traceback=True,saveCSV=False,unzip=False,saveTaJSON=False,triesLimit=30)
############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ############

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

ea_root = sd2Utils.whereIsEA()
if haveCreateReport:
    createReport.analyze(directory_name,globalsfile.outputDirPath,json_path,ea_root)
    
testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
