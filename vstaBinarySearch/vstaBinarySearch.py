'''
Test Description
================
For a given traffic pair data rate, determine the number of STAs (vSTAs) that can be used to achieve a given packet error rate.  
Remember that in order to get packet loss measurements, you must use only a single parallel traffic stream.
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
import base64
import math
import statistics
from random import *

import pprint
pp = pprint.PrettyPrinter(indent=4)

import zipfile
from zipfile import ZipFile

#--------------------------------------------------------------------------------
def main():

        global ea_root,packetLossTarget,stepSizeTarget,lossQuantile,directory_name
        global palsToUse,radios,settingsPerRadio,upOrDown,trafficBW
        global badPairs, badPairNames, tpMap, maxGood, minBad, REST_TIMEOUT, totalVstaWait
        badPairNames = []
        maxGood = -1
        minBad = 100000


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
        cRed=   '\033[m'
        cGreen= '\033[m'
        cNormal='\033[m'

        ############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

        trafficMode = paramsDict["trafficMode"]["val"]
        if trafficMode != "udp":
                print("Please use 'udp' for the traffic mode.  This test requires packet loss calculations and these are only available in udp.")
                sys.exit(41)

        # Build list for config check
        instList = []
        #(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
        #attenList = [attenToUseA,attenToUseB]
        attensToUse = paramsDict["attensToUse"]["val"]
        attenList = attensToUse

        palsToUse = paramsDict['palsToUse']['val']
        print('')
        print('##############################################################')
        print("########## List of Pal6es to use is {}".format(palsToUse))
        print('##############################################################')

        for palToUse in palsToUse: 
                    instList.append(palToUse)

        testUses=paramsDict['testUses']['val']+instList+attenList
        print(">>> testUses: ", testUses)

        # Check that system can support the test
        sd2Utils.checkSystemConfig(testUses)

        thisDrop = paramsDict["eaLocation"]["val"]
        for item in thisDrop:
                if item["selected"]:
                    eaLocation = item["value"]
                    break

        if eaLocation == "remote": ea_root = "http://www.octapi.tech/"
        if eaLocation == "local":  ea_root = "http://localhost:8080/"

        packetLossTarget = paramsDict["packetLossTarget"]["val"]
        stepSizeTarget   = paramsDict["stepSizeTarget"]["val"]
        lossQuantile     = paramsDict["lossQuantile"]["val"]

        print(">>> Pulling in vSTA settings from the test parameters file.")

        vstaSettings = paramsDict["vstaSettings"]["val"]
        settingsPerRadio = {}
        radios = []
        validBandList = ['24g','2.4g','5g','6g']
        validBandwidthList = ['BANDWIDTH_ADAPT','BANDWIDTH_20_FIXED','BANDWIDTH_40_ADAPT', 'BANDWIDTH_80_ADAPT', 'BANDWIDTH_160_ADAPT']
        validInterfaceList = ['INTERFACE_G', 'INTERFACE_N', 'INTERFACE_AC', 'INTERFACE_AX']
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
                    radios.append(radio)

        print('>>> settingsPerRadio: ', settingsPerRadio)
        #print(radios)

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
        resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp, "security":security, "ssid":ssid, "password":password, "trafficType": paramsDict['trafficType']['val'], "trafficMode":paramsDict['trafficMode']['val'], "upOrDown": upOrDown, "vstaWaitMore":vstaWaitMore})
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
                if icnt==len(attensToUse): pc = True
                sd2Utils.setAtten(atten,paramsDict[atten]["val"]["devType"],paramsDict["quadAttenStart"]["val"],attenValueStop=paramsDict["quadAttenStop"]["val"],mpeBypassValue=63,pushConfig=pc)


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

                            (vstaConfigList,tpDictList) = sd2Utils.setupVsta(palToUse, settingsPerRadio[radio]["band"], settingsPerRadio[radio]["primaryChannel"], upOrDown, paramsDict['trafficMode']['val'], settingsPerRadio[radio]["vstaCount"], vstaParams, tpDictList, startTpAt1=True)
                            allVstaConfigs[palToUse][radio] = vstaConfigList
                            allTpConfigs[palToUse][radio] = tpDictList
                            alltpDictList += tpDictList
                            if paramsDict['debug']['val']:
                                    print('')
                                    print('##############################################################')
                                    print('>>> radio: ', radio)
                                    print('>>> allVstaConfigs: ', allVstaConfigs)
                                    print('>>> allTpConfigs: ', allTpConfigs)
                                    #print('>>> tpDictList: ', tpDictList)
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
        #print('>>> EXIT at LINE 365')
        #sys.exit()

        startStaSetupTime = time.time()

        allStaPalDicts = {}
        staPalDictList = []
        for palToUse in palsToUse:
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

                            staPalDictList = sd2Utils.setupSTA(palToUse,settingsPerRadio[radio]["band"], staPalDictList, streams=settingsPerRadio[radio]["streams"], channel=settingsPerRadio[radio]["primaryChannel"], staDictOverride=overrideDict, timeoutOverride=REST_TIMEOUT+settingsPerRadio[radio]["vstaWaitMore"], startTpAt1=True)
                            allStaPalDicts[palToUse][radio] = staPalDictList
                            if paramsDict['debug']['val']:
                                    print('>>> staPalDictList: ' )
                                    pp.pprint(staPalDictList)
        endStaSetupTime = time.time()
        sd2Utils.updateAutotestInst(staPalDictList, 'pal6s', pushConfig=True, timeoutOverride=REST_TIMEOUT+totalVstaWait) # update config and push
        endStaSetupPushTime = time.time()

        staConfigCreateTime = round((endStaSetupTime-startStaSetupTime),1)
        staConfigPushTime = round((endStaSetupPushTime-endStaSetupTime),1)
        print('')
        print('##############################################################')
        print("########## Setting up STAs DONE")
        print('########## Time to create pal6s config: %s' % staConfigCreateTime)
        print('########## Time to push pal6s config: %s' % staConfigPushTime)
        print('##############################################################')
        resultDict = {}
        resultDict.update({"staConfigCreateTime": staConfigCreateTime})
        resultDict.update({"staConfigPushTime": staConfigPushTime})
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

        ############### END SECTION: BUILD THE TEST OBJECT #########################

        ############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

        for palToUse in palsToUse:

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

        trafficBW = paramsDict["trafficBW"]["val"]
        trafficBW = trafficBW.upper().replace("M","").replace("K","")
        trafficBW = int(trafficBW)
        resultDict = {}
        resultDict.update({"packetLossTarget": packetLossTarget})
        resultDict.update({"trafficBW": paramsDict["trafficBW"]["val"]})
        resultDict.update({"stepSizeTarget": stepSizeTarget})
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)        

        Timestamp = sd2Utils.getTimestamp()

        allTestResults = []
        allResultsJson = []
        allPacketData  = {}

        #I have noticed that it is mostly with this first attempt that I find traffic pairs getting tagged as "bad".  Maybe this is because even though the STAs are associated,
        #they are not yet ready for traffic.  Let's give them a little while to setting.
        '''
        waitTimePerVsta = 1
        waitTime = waitTimePerVsta * len(alltpDictList)
        print("Going to wait {} seconds to see if it improves stability.".format(waitTime))
        time.sleep(waitTime)
        '''
        #The above didn't help much.  Instead, try running a test set of traffic first, without using it in the testing.

        #First Test.  Using all possible traffic pairs.
        activeList = []
        for i in range(0,len(alltpDictList)): activeList.append(i)
        activePairs = []
        for i in range(0,len(alltpDictList)): activePairs.append(alltpDictList[i]["alias"])
        print("Run a pump-priming test set of data, which is not used.  No analysis, no identifying of bad pairs, etc.")
        json_path = sd2Utils.runAutotest(traceback=True,unzip=False,saveCSV=False,saveTaJSON=False,triesLimit=30)

        print("And now run the test again, for real.")
        json_path = sd2Utils.runAutotest(traceback=True,unzip=False,saveCSV=False,saveTaJSON=False,triesLimit=30)
        print(">>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))
        nTrafficPairs, allThroughputs, allLostPercent, nonZeroThroughputs, lossMetric, resultsJson, packetData = getTestResults(json_path,len(alltpDictList),activeList,activePairs)
        allTestResults.append({"nTrafficPairs":nTrafficPairs,
                                   "lastStep": None,
                                   "activePairs": len(alltpDictList),
                                   "allThroughputs":allThroughputs,
                                   "allLostPercent":allLostPercent,
                                   "nonZeroThroughputs":nonZeroThroughputs,
                                   "lossMetric":lossMetric,
                                   "good":lossMetric < packetLossTarget})
        #print(json.dumps(allTestResults[len(allTestResults)-1],indent=4))
        allPacketData[str(len(alltpDictList))] = packetData
        resultDict = {}        
        resultDict.update({"allTestResults": allTestResults})
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
        allResultsJson.append(resultsJson)
        resultDict = {}        
        resultDict.update({"allResultsJson": allResultsJson})
        print("\n*********************************************************")
        for testResult in allTestResults:
                print("Active Pairs: {},  Losses: {},  Good? {}, Step: {}".format(testResult["activePairs"],testResult["lossMetric"],testResult["good"],testResult["lastStep"]))
        print("*********************************************************\n")


        #Next test.  Using only a single traffic pair.
        nActive = 1

        #This is where you choose the active traffic pairs going from 0 and heading up.
        '''
        for i in range(0,nActive):
                updateDict = {"alias":alltpDictList[i]["alias"] , "active":True}
                sd2Utils.updateTrafficPair(updateDict)
        for i in range(nActive,len(alltpDictList)):
                updateDict = {"alias":alltpDictList[i]["alias"] , "active":False}
                sd2Utils.updateTrafficPair(updateDict)
        '''

        #This is where you choose the active traffic pairs by random selection.        
        activeList = getActiveList(nActive,len(alltpDictList))
        activePairs = []
        print("Here is the list of active traffic pairs: {}".format(activeList))
        for i in range(0,len(alltpDictList)):
                isActive = False
                if i in activeList: isActive = True
                updateDict = {"alias":alltpDictList[i]["alias"] , "active":isActive}
                sd2Utils.updateTrafficPair(updateDict)
                if isActive: activePairs.append(alltpDictList[i]["alias"])
        print("Here is the list of active traffic pairs names: {}".format(activePairs))

        json_path = sd2Utils.runAutotest(traceback=True,unzip=False,saveCSV=False,saveTaJSON=False,triesLimit=30)
        print(">>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))
        nTrafficPairs, allThroughputs, allLostPercent, nonZeroThroughputs, lossMetric, resultsJson, packetData = getTestResults(json_path,1,activeList,activePairs)
        allTestResults.append({"nTrafficPairs":nTrafficPairs,
                                   "lastStep": abs(nActive - allTestResults[len(allTestResults)-1]["activePairs"]),
                                   "activePairs": nActive,
                                   "allThroughputs":allThroughputs,
                                   "allLostPercent":allLostPercent,
                                   "nonZeroThroughputs":nonZeroThroughputs,
                                   "lossMetric":lossMetric,
                                   "good":lossMetric < packetLossTarget})
        #print(json.dumps(allTestResults[len(allTestResults)-1],indent=4))
        allPacketData[str(nActive)] = packetData    
        resultDict = {}        
        resultDict.update({"allTestResults": allTestResults})
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
        allResultsJson.append(resultsJson)
        resultDict = {}        
        resultDict.update({"allResultsJson": allResultsJson})
        sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
        print("\n*********************************************************")
        for testResult in allTestResults:
                print("Active Pairs: {},  Losses: {},  Good? {}, Step: {}".format(testResult["activePairs"],testResult["lossMetric"],testResult["good"],testResult["lastStep"]))
        print("*********************************************************\n")

        weAreDone, message = checkIfDone(allTestResults)
        print(weAreDone)
        print(message)
        if not weAreDone:

                while not weAreDone:
                    print("\n*********************************************************")
                    for testResult in allTestResults:
                        print("Active Pairs: {},  Losses: {},  Good? {}, Step: {}".format(testResult["activePairs"],testResult["lossMetric"],testResult["good"],testResult["lastStep"]))
                    print("*********************************************************\n")
                    nActive = getTheNextCount(allTestResults)
                    print("The next pair count will be {}".format(nActive))
                    if nActive <=0 or nActive > len(alltpDictList):
                        print("Something is going terribly wrong.")
                        removeVSTAsFromPals()
                        sys.exit(55)

                    #This is where you choose the active traffic pairs going from 0 and heading up.
                    '''
                    for i in range(0,nActive):            
                        updateDict = {"alias":alltpDictList[i]["alias"] , "active":True}
                        sd2Utils.updateTrafficPair(updateDict)
                    for i in range(nActive,len(alltpDictList)):
                        updateDict = {"alias":alltpDictList[i]["alias"] , "active":False}
                        sd2Utils.updateTrafficPair(updateDict)
                    '''

                    #This is where you choose the active traffic pairs by random selection.        
                    activeList = getActiveList(nActive,len(alltpDictList))
                    activePairs = []
                    print("Here is the list of active traffic pairs: {}".format(activeList))
                    for i in range(0,len(alltpDictList)):
                        isActive = False
                        if i in activeList: isActive = True
                        updateDict = {"alias":alltpDictList[i]["alias"] , "active":isActive}
                        sd2Utils.updateTrafficPair(updateDict)
                        if isActive: activePairs.append(alltpDictList[i]["alias"])
                    print("Here is the list of active traffic pairs names: {}".format(activePairs))

                    json_path = sd2Utils.runAutotest(traceback=True,unzip=False,saveCSV=False,saveTaJSON=False,triesLimit=30)
                    print(">>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))
                    nTrafficPairs, allThroughputs, allLostPercent, nonZeroThroughputs, lossMetric, resultsJson, packetData = getTestResults(json_path,nActive,activeList,activePairs)
                    allTestResults.append({"nTrafficPairs":nTrafficPairs,
                                           "lastStep": abs(nActive - allTestResults[len(allTestResults)-1]["activePairs"]),
                                           "activePairs": nActive,
                                           "allThroughputs":allThroughputs,
                                           "allLostPercent":allLostPercent,
                                           "nonZeroThroughputs":nonZeroThroughputs,
                                           "lossMetric":lossMetric,
                                           "good":lossMetric < packetLossTarget})
                    #print(json.dumps(allTestResults[len(allTestResults)-1],indent=4))
                    allPacketData[str(nActive)] = packetData        
                    allResultsJson.append(resultsJson)

                    weAreDone, message = checkIfDone(allTestResults)
                    print(weAreDone)
                    print(message)
                    resultDict = {}        
                    resultDict.update({"allTestResults": allTestResults})
                    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
                    resultDict = {}        
                    resultDict.update({"allResultsJson": allResultsJson})
                    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)


                #OK, we are done.  Final results:
                print("\n*********FINAL RESULTS***********************************")
                print("\n*********************************************************")
                for testResult in allTestResults:
                    print("Active Pairs: {},  Losses: {},  Good? {}".format(testResult["activePairs"],testResult["lossMetric"],testResult["good"]))
                print("*********************************************************\n")

                #Actually, fill in the numbers between the good and bad limits.
                print("Do a final infill from {} to {}".format(maxGood+1,minBad-1))
                for aValue in range (maxGood+1,minBad):
                    print("\n*********************************************************")
                    for testResult in allTestResults:
                        print("Active Pairs: {},  Losses: {},  Good? {}, Step: {}".format(testResult["activePairs"],testResult["lossMetric"],testResult["good"],testResult["lastStep"]))
                    print("*********************************************************\n")
                    nActive = aValue
                    print("The next pair count will be {}".format(nActive))
                    if nActive <=0 or nActive > len(alltpDictList):
                        print("Something is going terribly wrong.")
                        removeVSTAsFromPals()
                        sys.exit(55)

                    #This is where you choose the active traffic pairs going from 0 and heading up.
                    '''
                    for i in range(0,nActive):            
                        updateDict = {"alias":alltpDictList[i]["alias"] , "active":True}
                        sd2Utils.updateTrafficPair(updateDict)
                    for i in range(nActive,len(alltpDictList)):
                        updateDict = {"alias":alltpDictList[i]["alias"] , "active":False}
                        sd2Utils.updateTrafficPair(updateDict)
                    '''

                    #This is where you choose the active traffic pairs by random selection.        
                    activeList = getActiveList(nActive,len(alltpDictList))
                    activePairs = []
                    print("Here is the list of active traffic pairs: {}".format(activeList))
                    for i in range(0,len(alltpDictList)):
                        isActive = False
                        if i in activeList: isActive = True
                        updateDict = {"alias":alltpDictList[i]["alias"] , "active":isActive}
                        sd2Utils.updateTrafficPair(updateDict)
                        if isActive: activePairs.append(alltpDictList[i]["alias"])
                    print("Here is the list of active traffic pairs names: {}".format(activePairs))

                    json_path = sd2Utils.runAutotest(traceback=True,unzip=False,saveCSV=False,saveTaJSON=False,triesLimit=30)
                    print(">>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))
                    nTrafficPairs, allThroughputs, allLostPercent, nonZeroThroughputs, lossMetric, resultsJson, packetData = getTestResults(json_path,nActive,activeList,activePairs)
                    allTestResults.append({"nTrafficPairs":nTrafficPairs,
                                           "lastStep": abs(nActive - allTestResults[len(allTestResults)-1]["activePairs"]),
                                           "activePairs": nActive,
                                           "allThroughputs":allThroughputs,
                                           "allLostPercent":allLostPercent,
                                           "nonZeroThroughputs":nonZeroThroughputs,
                                           "lossMetric":lossMetric,
                                           "good":lossMetric < packetLossTarget})
                    #print(json.dumps(allTestResults[len(allTestResults)-1],indent=4))
                    allPacketData[str(nActive)] = packetData        
                    allResultsJson.append(resultsJson)

                    resultDict = {}        
                    resultDict.update({"allTestResults": allTestResults})
                    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)
                    resultDict = {}        
                    resultDict.update({"allResultsJson": allResultsJson})
                    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

                #OK, we are actually done now.  Final results:
                print("\n*********FINAL RESULTS***********************************")
                print("\n*********************************************************")
                for testResult in allTestResults:
                    print("Active Pairs: {},  Losses: {},  Good? {}".format(testResult["activePairs"],testResult["lossMetric"],testResult["good"]))
                print("*********************************************************\n")

                highestGood = -1
                lowestBad =   -1
                for i in range(0,len(allTestResults)):
                    if allTestResults[i]["good"]:
                        if highestGood < 0:                                                               highestGood = i
                        if allTestResults[i]["activePairs"] > allTestResults[highestGood]["activePairs"]: highestGood = i
                    if not allTestResults[i]["good"]:
                        if lowestBad < 0:                                                                 lowestBad = i
                        if allTestResults[i]["activePairs"] < allTestResults[lowestBad]["activePairs"]:   lowestBad = i

                highestGood = allTestResults[highestGood]["activePairs"]
                lowestBad   = allTestResults[lowestBad]["activePairs"]
                print("Highest good value: {}, and Lowest bad value: {}".format(highestGood,lowestBad))

                resultDict.update({"allTestResults": allTestResults})
                sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

                #Save away the packetData information for the last, good set of data.  After this, you exceed the packet loss threshold.
                resultDict = {}        
                resultDict.update({"lastPacketData": allPacketData[str(highestGood)]})
                sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

                print('')
                print('##############################################################')
                print("########## Creating HTML report ")
                print('##############################################################')	

                import createReport
                cRvalues = {"lossQuantile":lossQuantile}
                createReport.main(directory_name,globalsfile.outputDirPath,cRvalues)

        testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
        print('')
        print('##############################################################')
        print("########## %s TEST DONE " % testName)
        print("########## Test run time: %s. " % testRunTime)
        print('##############################################################')

        removeVSTAsFromPals()

#--------------------------------------------------------------------------------
def removeVSTAsFromPals():

    global palsToUse,radios,settingPerRadio, REST_TIMEOUT, totalVstaWait

    sys.path.append(directory_name + '../')
    import globalsfile	# MUST HAVE to be able to reference global variables stored in globalsfile.py
    import sd2Utils		# MUST HAVE. Contains functions used in this script and other helpful functions
    from stardust_socket_listen import StardustSocketListen # MUST HAVE if you are going to use any real time stats

    print("Removing all of the VSTAs from the Pals so that the script will run the next time.")

    #Try and clean up the Pals after the test is run
    staPalDictList = []
    for palToUse in palsToUse:
        for radio in radios:
            overrideDict = {
                "vstaCount": 1,
            }            
            staPalDictList = sd2Utils.setupSTA(palToUse,settingsPerRadio[radio]["band"], staPalDictList,
                                               streams=settingsPerRadio[radio]["streams"], channel=settingsPerRadio[radio]["primaryChannel"],
                                               staDictOverride=overrideDict, timeoutOverride=REST_TIMEOUT+settingsPerRadio[radio]["vstaWaitMore"])
    sd2Utils.updateAutotestInst(staPalDictList, 'pal6s', pushConfig=True, timeoutOverride=REST_TIMEOUT+totalVstaWait) # update config and push            

    return

#--------------------------------------------------------------------------------
def extractJson(json_path):
    global ea_root

    #Extract data from this JSON
    fileName = json_path
    with open(fileName, "rb") as f:
        bytes = f.read()
        encoded = base64.b64encode(bytes)
        api_endpoint = ea_root + "zip2csv"
        data = {'zip':encoded}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)

    csv = theJson["csv"]

    # Analyze the CSV file
    api_endpoint = ea_root + "objectify"
    data = {'csv':csv}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)

    headers = theJson["headers"]
    dataSet = theJson["dataSet"]
    if "error" in theJson: print("objectify: This data returned an error: {}".format(theJson["error"]))

    api_endpoint = ea_root + "crunch"
    run = 1
    data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    if "error" in theJson: print("crunch: This data returned an error: {}".format(theJson["error"]))
    crunchedData = theJson["crunchedData"]

    #Get basic test results information
    api_endpoint = ea_root + "getStats"
    data = {
        'csv':csv,
        'filter':'counts'
    }

    try:
        r = requests.post(url=api_endpoint, data=data, timeout=90)
    except requests.exceptions.RequestException as error:
        print("Error: ", error)
        sys.exit(44)

    y = json.loads(r.text)
    tpMap = y["filteredData"]["trafficPairs"]["map"]

    return csv, headers, dataSet, crunchedData, tpMap

#--------------------------------------------------------------------------------
def getTestResults(json_path,expected,activeList,activePairs):

    global trafficBW, badPairNames, tpMap, maxGood, minBad, lossQuantile
    csv, headers, dataSet, crunchedData, tpMap = extractJson(json_path)

    #Gather up the raw data for the lost packets for each traffic pair.  This is done in order to be able to choose the definition of "packet loss" with more granularity.
    packetData = {}
    for item in tpMap:
        tpName = tpMap[item]
        packetData[tpName] = {"count":[], "lost":[], "lostPercent":[]}
        for data in dataSet:
            if "(avg)" in data["Traffic State"]:
                if data[tpName + " Packets"].replace(".","",1).isnumeric():          packetData[tpName]["count"].append(int(data[tpName + " Packets"]))
                if data[tpName + " Lost Packets"].replace(".","",1).isnumeric():     packetData[tpName]["lost"].append(int(data[tpName + " Lost Packets"]))
                if data[tpName + " Lost Percent [%]"].replace(".","",1).isnumeric(): packetData[tpName]["lostPercent"].append(float(data[tpName + " Lost Percent [%]"]))

    #Create an aggregate set of data as well, using all (active) traffic pairs
    packetData["aggregate"] = {"count":[], "lost":[], "lostPercent":[]}    
    for data in dataSet:
        if "(avg)" not in data["Traffic State"]: continue
        aggCount = 0
        aggLost  = 0
        for item in tpMap:
            tpName = tpMap[item]
            if tpName in activePairs:
                if data[tpName + " Packets"].replace(".","",1).isnumeric():          aggCount += int(data[tpName + " Packets"])
                if data[tpName + " Lost Packets"].replace(".","",1).isnumeric():     aggLost  += int(data[tpName + " Lost Packets"])
        packetData["aggregate"]["count"].append(aggCount)
        packetData["aggregate"]["lost"].append(aggLost)
        if aggCount > 0:
            packetData["aggregate"]["lostPercent"].append(aggLost/aggCount * 100)
        else:
            packetData["aggregate"]["lostPercent"].append(0)


    for key in packetData:
        data = packetData[key]
        if sum(data["count"]) > 0: data["lostPercentAgg"] = (sum(data["lost"])/sum(data["count"])) * 100
        else: data["lostPercentAgg"] = 0
        if(len(data["lostPercent"])>0):
            sorted = []
            for item in data["lostPercent"]: sorted.append(item)
            sorted.sort()
            length = len(sorted)
            qItem = min(length-1, math.floor((lossQuantile/100)*(length+1))-1)
            data["quantile"] = sorted[qItem]
        else:
            data["quantile"] = 0

    #print(json.dumps(packetData,indent=4))

    nEndpoints = len(crunchedData)
    #print("There are {} endpoints.".format(nEndpoints))
    nAttenuations = len(crunchedData[0])
    #print("There are {} attenuations.".format(nAttenuations))

    allThroughputs = []
    allLostPercent = []

    #Remember that all traffic pair information is duplicated in every endpoint.  So there is no reason to loop over endpoints.
    #for analyzedData in crunchedData: #Per endpoint

    analyzedData = crunchedData[0]    
    nTrafficPairs = len(analyzedData[0]["tpairData"]) #Per attenuation
    print("There are {} traffic pairs.".format(nTrafficPairs))
    print("There are {} active traffic pairs EXPECTED.".format(expected))
    #for pair in analyzedData[0]["tpairData"]:
    badPairs = []
    for i in range(0,len(analyzedData[0]["tpairData"])):
        #Should this even be active?
        thisPair = tpMap[str(i)]
        if thisPair in activePairs:
            print("For index {}, this is pair {}, and it should be active.".format(i,thisPair))
        else:
            print("For index {}, this is pair {}, and it is not active.".format(i,thisPair))
            continue
        pair = analyzedData[0]["tpairData"][i]
        isGood = True
        if isGood and pair["throughput"]["mean"] == None: isGood = False
        if isGood:
            if math.isnan(pair["throughput"]["mean"]): isGood = False
        if pair["throughput"]["mean"] == 0: isGood = False
        if not isGood:
            badPairs.append(i)
            badPairNames.append(thisPair)
        else:
            #print(pair["throughput"])
            allThroughputs.append(pair["throughput"]["mean"])
            #print(pair["lostPercentage"])
            #What do you want to store away for the "lost percentage?
            #This is the EA-calculated max, or mean
            '''
            if "max" in pair["lostPercentage"]: allLostPercent.append(pair["lostPercentage"]["max"])
            else:                               allLostPercent.append(pair["lostPercentage"]["mean"])
            '''
            #This is the specific quantile we found above
            allLostPercent.append(packetData[thisPair]["quantile"])


    tagAsBad = False
    if len(allThroughputs) != expected:
        print("Unexpected data length in getTestResults")
        print("Expectation is for {} values.".format(expected))
        print("Length of allThroughputs is {}, and allLostPercent is {}".format(len(allThroughputs),len(allLostPercent)))
        print("The bad pairs are: {}, or {}".format(badPairs,badPairNames))
        badThroughput = []
        badLostPercent = []
        for i in range(0,len(analyzedData[0]["tpairData"])):
            if i not in badPairs: continue
            pair = analyzedData[0]["tpairData"][i]
            badThroughput.append(pair["throughput"]["mean"])
            if "max" in pair["lostPercentage"]: badLostPercent.append(pair["lostPercentage"]["max"])
            else:                               badLostPercent.append(pair["lostPercentage"]["mean"])            
        tagAsBad = True
        #print("########## vstaBinarySearch Reset the Pals ")
        #sys.exit(66)


    #This is the quantile value of the aggregate packData information
    sorted = []
    for item in packetData["aggregate"]["lostPercent"]: sorted.append(item)
    sorted.sort()
    length = len(sorted)
    qItem = min(length-1, math.floor((lossQuantile/100)*(length+1))-1)
    aggregateQuantile = sorted[qItem]

    try:
        nonZeroThroughputs = 0
        sumOfThroughputs = 0
        for throughput in allThroughputs:
            if throughput > 0: nonZeroThroughputs += 1
            sumOfThroughputs += throughput
        #What loss metric do you want to use?
        #This one uses the maximum of whatever value you have stored in allLostPercent, the max over all of the traffic pairs.
        lossMetric = max(allLostPercent)
        #You could do something else, of course.  Average of all of them, sum(allLost)/sum(allPackets), etc.
        lossMetric = aggregateQuantile
    except:
        tagAsBad = True
        print("Problem with either these throughputs:\n{}\nor these losses:\n{}".format(allThroughputs,allLostPercent))

    if tagAsBad:
        nonZeroThroughputs = -1
        lossMetric = 100
        if expected < minBad: minBad = expected

    isGood = lossMetric < packetLossTarget
    if isGood and not tagAsBad:
        if expected > maxGood: maxGood = expected
    if not isGood and not tagAsBad:
        if expected < minBad: minBad = expected

    resultsJson = {}
    resultsJson["active"] = {"expected":expected, "found":len(allThroughputs)}
    resultsJson["nTrafficPairs"] = nTrafficPairs
    resultsJson["tagAsBad"] = tagAsBad
    resultsJson["lossMetric"] = lossMetric
    resultsJson["good"] = lossMetric < packetLossTarget
    resultsJson["expectedTraffic"] = expected * trafficBW
    resultsJson["foundTraffic"] = sumOfThroughputs
    resultsJson["maxGood"] = maxGood
    resultsJson["minBad"] = minBad

    if tagAsBad:
        resultsJson["badPairs"] = badPairs
        resultsJson["badPairNames"] = badPairNames
        resultsJson["badThroughput"] = badThroughput
        resultsJson["badLostPercent"] = badLostPercent

    return nTrafficPairs, allThroughputs, allLostPercent, nonZeroThroughputs, lossMetric, resultsJson, packetData

#---------------------------------------------------------------------------------------------
def checkIfDone(allTestResults):

    global packetLossTarget,stepSizeTarget,maxGood, minBad
    weAreDone = False
    index = len(allTestResults) - 1

    #Check to see if you are below the required limit even for the highest setting.  If that's the case, you'll never be able to do this.

    if allTestResults[0]["lossMetric"] <= packetLossTarget:
        weAreDone = True
        message = "The packet loss with the largest number of traffic pairs, {}, is {}, which is below the limit of {}.  Increase the number of VSTAs to finish this test.".format(
            allTestResults[0]["activePairs"],allTestResults[0]["lossMetric"],packetLossTarget)

    elif allTestResults[index]["lossMetric"] <= packetLossTarget:
        lastStep = allTestResults[index-1]["activePairs"] - allTestResults[index]["activePairs"]
        lastStep = abs(lastStep)
        goodBadGap = minBad - maxGood
        #if lastStep <= stepSizeTarget:
        if goodBadGap <= stepSizeTarget:
            weAreDone = True
            message = "The packet loss with {} traffic pairs is {}, which is below the limit of {}.  Since the gap of {} is equal to or below {}, we are done.".format(
                #allTestResults[index]["activePairs"],allTestResults[index]["lossMetric"],packetLossTarget,lastStep,stepSizeTarget)
                allTestResults[index]["activePairs"],allTestResults[index]["lossMetric"],packetLossTarget,goodBadGap,stepSizeTarget)
        else:
            weAreDone = False
            message = "The packet loss with {} traffic pairs is {}, which is below the limit of {}.  But the gap of {} is above the target of {}.".format(
                #allTestResults[index]["activePairs"],allTestResults[index]["lossMetric"],packetLossTarget,lastStep,stepSizeTarget)
                allTestResults[index]["activePairs"],allTestResults[index]["lossMetric"],packetLossTarget,goodBadGap,stepSizeTarget)

    elif allTestResults[index]["lossMetric"] > packetLossTarget:
        goodBadGap = minBad - maxGood
        if goodBadGap <= stepSizeTarget:
            weAreDone = True
            message = "The packet loss with {} traffic pairs is {}, which is above the limit of {}, but since the gap of {} is equal to or below {}, we are done.".format(
                allTestResults[index]["activePairs"],allTestResults[index]["lossMetric"],packetLossTarget,goodBadGap,stepSizeTarget)
        else:
            weAreDone = False
            message = "The packet loss with {} traffic pairs is {}, which is above the limit of {}.".format(
                allTestResults[index]["activePairs"],allTestResults[index]["lossMetric"],packetLossTarget)

    #If you have been driven to check a value below a known good value, declare the test done.
    if not weAreDone and allTestResults[index]["activePairs"] < maxGood:
        weAreDone = True
        message = "This test with {} traffic pairs is below a known good test value of {}. This should not really be happening, but end the test.".format(
                allTestResults[index]["activePairs"],maxGood)


    return weAreDone, message

#---------------------------------------------------------------------------------------------
def getTheNextCount(allTestResults):

    global packetLossTarget
    global maxGood, minBad

    index = len(allTestResults) - 1    

    if maxGood > minBad:
        print("The largest good value {} is somehow larger than the smallest bad value {}".format(maxGood,minBad))
        sys.exit(46)
    else:
        nextCount = int( (minBad + maxGood)/2 )

    lastCount = allTestResults[index]["activePairs"]
    previousCount = allTestResults[index-1]["activePairs"]
    lastStep = allTestResults[index-1]["activePairs"] - allTestResults[index]["activePairs"]
    lastStep = abs(lastStep)
    direction = +1
    if lastCount < previousCount: direction = -1

    #In general, make sure you didn't do this one already.
    notOK = True
    while notOK:
        notOK = False
        for testResult in allTestResults:
            if testResult["activePairs"] == nextCount:
                nextCount = nextCount + direction*1
                if nextCount <= maxGood:
                    nextCount = maxGood
                    direction = +1    # Don't let it keep going down.
                if nextCount >= minBad:
                    nextCount = minBad
                    direction = -1
                notOK = True
                break

    return nextCount
#---------------------------------------------------------------------------------------------
def getTheNextCount_old(allTestResults):
    global packetLossTarget

    index = len(allTestResults) - 1

    lastCount = allTestResults[index]["activePairs"]
    previousCount = allTestResults[index-1]["activePairs"]
    lastStep = allTestResults[index-1]["activePairs"] - allTestResults[index]["activePairs"]
    lastStep = abs(lastStep)
    direction = +1
    if lastCount < previousCount: direction = -1

    if (allTestResults[index]["good"] and allTestResults[index-1]["good"]) or (not allTestResults[index]["good"] and not allTestResults[index-1]["good"]):
        #Keep going in whatever direction you were going in, with the same step size.
        nextCount = lastCount + direction*lastStep
        #Make sure you don't go high....
        if nextCount > allTestResults[index]["nTrafficPairs"]:
            nextCount = allTestResults[index]["nTrafficPairs"]
            #Make sure you didn't do this one already.
            notOK = True
            while notOK:
                notOK = False
                for testResult in allTestResults:
                    if testResult["activePairs"] == nextCount:
                        nextCount -= 1
                        notOK = True
                        break
        #Make sure you don't go low....
        if nextCount < 1:
            nextCount = 1
            #Make sure you didn't do this one already.
            notOK = True
            while notOK:
                notOK = False
                for testResult in allTestResults:
                    if testResult["activePairs"] == nextCount:
                        nextCount += 1
                        notOK = True
                        break
    elif (allTestResults[index]["good"] and not allTestResults[index-1]["good"]) or (not allTestResults[index]["good"] and allTestResults[index-1]["good"]):
        #Reverse direction, and shrink the step
        nextStep = math.ceil(lastStep/2)
        direction *= -1
        nextCount = lastCount + direction*nextStep

    #In general, make sure you didn't do this one already.
    notOK = True
    while notOK:
        notOK = False
        for testResult in allTestResults:
            if testResult["activePairs"] == nextCount:
                nextCount = nextCount + direction*1
                if nextCount <= 1:
                    nextCount = 1
                    direction = +1    # Don't let it keep going down.
                if nextCount >= allTestResults[index]["nTrafficPairs"]:
                    nextCount = allTestResults[index]["nTrafficPairs"]
                    direction = -1
                notOK = True
                break

    return nextCount

#---------------------------------------------------------------------------------------------
def getActiveList(count,total):
    #Randomly select items in a list between 0 and total-1 such that 'count' are true
    global badPairs, badPairNames, tpMap

    checkForBadPairs = True

    if(total - len(badPairNames) < count):
        print("You are trying to get {} pairs from {} total, but are trying not to use {}.  This cannot work.".format(count,total,len(badPairNames)))
        #removeVSTAsFromPals()
        #sys.exit(43)
        #Rather than quitting, try just allowing all of the pairs again.  I know, seems to mean that you don't believe these are really bad pairs...
        print("Removing the list of band pair names, and just allowing all of them to be used.")
        #badPairs = []
        #badPairNames = []
        checkForBadPairs = False

    activeList = []
    while len(activeList) < count:
        thisOne = randint(0,total-1)
        useIt = True
        if thisOne in activeList: useIt = False
        thisPair = tpMap[str(thisOne)]
        if checkForBadPairs:
            if thisPair in badPairNames: useIt = False
        if useIt: activeList.append(thisOne)

    return activeList

#---------------------------------------------------------------------------------------------

main()

'''
        allTestResults.append({"nTrafficPairs":nTrafficPairs,
                               "activePairs": nActive,
                               "allThroughputs":allThroughputs,
                               "allLostPercent":allLostPercent,
                               "nonZeroThroughputs":nonZeroThroughputs,
                               "lossMetric":lossMetric,
                               "good":lossMetric < packetLossTarget})
'''

