'''
Test Description
================
Congestion script.
Use two Pal devices, one as AP and one as STA, and run traffic to achieve a targeted congestion value as measured by the Pal/AP.  This is a prototype interaction for a new kind of iGen constructed in this way.
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
from datetime import datetime

import zipfile
from zipfile import ZipFile

import pprint
pp = pprint.PrettyPrinter(indent=4)
############### END SECTION: IMPORTS #########################

# Get the location of the results directory, as far as script-manager is concerned
response = requests.get("http://localhost:5678/getResultsDirectory")
theJson = response.json()
resultsDirectory = theJson["resultsDirectory"]
print("The results directory is {}.".format(resultsDirectory))

############### START SECTION: BUILD DICTIONARY #########################
# Find working directory
try:
        directory_name = sys.argv[1]
        print(">>> The directory name passed in is {}".format(
                directory_name), flush=True)
except:
        # directory_name = "./"
        directory_name = os.getcwd()
        print('>>> No directory_name provided, so using {}'.format(
                directory_name), flush=True)

# This line makes sure script can run from command line without SM
if directory_name[len(directory_name)-1] != "/": directory_name += "/"

sys.path.append(directory_name + '../')

# MUST HAVE if you are going to use any real time stats
from stardust_socket_listen import StardustSocketListen
# MUST HAVE. Contains functions used in this script and other helpful functions
import sd2Utils
# MUST HAVE to be able to reference global variables stored in globalsfile.py
import globalsfile

# Reference params and base auto test dictionaries
paramsDict = globalsfile.paramsDict

REST_TIMEOUT = paramsDict['rest_timeout']['val']  # Used by REST API calls
print('\n>>> REST_TIMEOUT: ', REST_TIMEOUT)

# This is to bring in alternate parameters set in Script Manager Arguments field
# This enables the same script to be run with a different set of test parameters stored in a json file
# -----  Look at the test parameter info, in arg[2]
try:
        test_param_alt_file = sys.argv[2]
        print(">>> The parameters file name passed in is {}.".format(test_param_alt_file))
except:
        print('>>> No parameters file name provided')
        test_param_alt_file = None

# Update paramsDict if there is a test_param_alt_file found
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
globalsfile.outputDirPath = resultsDirectory+paramsDict['topDirectory']+'/'+paramsDict['subDirectory'] + '/'

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

# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

haveCreateReport = False
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
    import createReport
    haveCreateReport = True
else:
    print("{} No createReport at {} {}".format(cRed,createReportFilePath,cNormal))
    sys.exit(25)

print("haveCreateReport = {}".format(haveCreateReport))

ea_root = sd2Utils.whereIsEA()
print("ea_root = {}".format(ea_root))

    
def main():
    # ##################################################################################
    #	                             Start of main test script
    # ##################################################################################
    # ##################################################################################

    ############### START SECTION: BUILD THE TEST OBJECT #########################

    from kafka import KafkaProducer
    kafkaBrokerFound = True
    # initializing the Kafka producer  
    my_producer = KafkaProducer(  
        bootstrap_servers = ['localhost:9092'],
        api_version=(0,11,5),
        value_serializer = lambda x:json.dumps(x).encode('utf-8')  
    )

    from kafka import KafkaConsumer
    my_consumer = KafkaConsumer('dataStream',
                             bootstrap_servers = ['localhost:9092'],
                             auto_offset_reset = 'earliest',
                             enable_auto_commit = True,  
                             api_version=(0,11,5),
                             value_deserializer = lambda x : json.loads(x.decode('utf-8'))
                             )
    print("kafkaBrokerFound = {}".format(kafkaBrokerFound))
            
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
    attensToUse = paramsDict["attensToUse"]["val"]
    attenStart = paramsDict["quadAttenStart"]["val"]
    attenStop = paramsDict["quadAttenStop"]["val"]

    #Setting attenuation values for attenuators or MPEs:
    for atten in attensToUse:
            thisType = paramsDict[atten]["val"]["devType"]
            if thisType == "virtualAtten": sd2Utils.setVatten(atten,attenStart,attenValueStop=attenStop)
            elif thisType == "quadAtten": sd2Utils.setAtten(atten,thisType,attenStart,attenValueStop=attenStop)
            elif thisType == "MPE": sd2Utils.setAtten(atten,thisType,attenStart,attenValueStop=attenStop,mpeBypassValue=63)

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

    tpDictList = []
    tpDictList = sd2Utils.setupTrafficPairs(palToUse, '5g', updn, tpDictList, useWANendpoint=False, measureCongestion=False, palAsAP=usePalAsAP, tType=trafficType, tMode=iperfMode, tBW=trafficBW, tParallel=parallel, tLength='', tWindow='',linkMonitor=False)

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

    streams = int(paramsDict["nss"]["val"])
    mcs = int(paramsDict["mcs"]["val"])

    chainRXMask = None
    if "chainRXMask" in paramsDict: chainRXMask = paramsDict["chainRXMask"]["val"]
    chainTXMask = None
    if "chainTXMask" in paramsDict: chainTXMask = paramsDict["chainTXMask"]["val"]

    if usePalAsAP != "" and usePalAsAP in paramsDict:
            usingPalAsAP = True
            print("{} Going to use Pal {} as the AP. {}".format(cGreen,usePalAsAP,cNormal))
            apDictList = []
            palAPssid = paramsDict["palAPssid"]["val"]
            thisDrop = paramsDict["palAPsecurity"]["val"]
            for item in thisDrop:
                    if item["selected"]:
                            palAPsecurity = item["value"]
                            break
            palAPpassword = paramsDict["palAPpassword"]["val"]
            palAPchannel = paramsDict["palAPchannel"]["val"]
            override = {"ssid":palAPssid,"security":palAPsecurity,"password":palAPpassword,"bandwidth":bandwidth,"rate":mcs}
            if chainRXMask != None: override["chainRXMask"] = chainRXMask
            if chainTXMask != None: override["chainTXMask"] = chainTXMask
            sd2Utils.setupAP(usePalAsAP, '5g', apDictList, type = interface, channel=palAPchannel, streams= 4, apBridge= True, pushConfig=False, apDictOverride=override)



    #Setting up Pal configurations:

    thisDrop = paramsDict["band"]["val"]
    for item in thisDrop:
            if item["selected"]:
                    theBand = item["value"]
                    break
    primaryChannel = paramsDict['primaryChannel']['val']
    try:
            if primaryChannel.strip() == "": primaryChannel = 0
            else: primaryChannel = int(primaryChannel)
    except:
            primaryChannel = int(primaryChannel)

    ssidval = 'dutssid'+theBand.replace('g','')
    securityval = 'dutsecurity'+theBand.replace('g','')
    passwordval = 'dutpass'+theBand.replace('g','')
    # ssid, security and password are taken from params_system['dut']
    ssid = paramsDict['dut']['val'][ssidval]
    # valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
    security = paramsDict['dut']['val'][securityval]
    password = paramsDict['dut']['val'][passwordval]
    print('>>> ssid: %s, security: %s, password: %s, channel: %s, band: %s' % (ssid, security, password, primaryChannel, theBand))

    staDictList = []
    override = {"bandwidth":bandwidth}
    override["ssid"] = ssid
    override["security"] = security
    override["password"] = password
    if usingPalAsAP: override = {"ssid":palAPssid,"security":palAPsecurity,"password":palAPpassword,"bandwidth":bandwidth,"rate":mcs}
    if chainRXMask != None: override["chainRXMask"] = chainRXMask
    if chainTXMask != None: override["chainTXMask"] = chainTXMask
    staDictList = sd2Utils.setupSTA(palToUse, theBand, staDictList, type=interface, channel=primaryChannel, bssid='', streams=streams, staDictOverride=override, pushConfig=True)

    targetRadio = staDictList[0]['palRadio']

    #Setting up AP configurations:
    apDictList = []

    print('\n>>> Adding test information to testresults.json')
    resultDict = {"testInfo": testInfoDict}
    resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp, "security":security, "ssid":ssid, "password":password,"band":theBand, "primaryChannel":primaryChannel, "bandwidth":bandwidth, "interface":interface, "streams":streams, "mcs":mcs, "upOrDown": upOrDown })
    resultDict['testInfo'].update({"scriptSuiteVersion":globalsfile.scriptSuiteVersion})
    resultDict['testInfo'].update({"starDustVersion":globalsfile.starDustVersion})
    resultDict['testInfo'].update({"palFWversions":globalsfile.palFWdict})
    now = datetime.now()
    resultDict["startTime"] = str(now)
    if test_param_alt_file:
        resultDict['testInfo'].update({"testParamAltFile":test_param_alt_file})
    sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

    ############### END SECTION: BUILD THE TEST OBJECT #########################

    ############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################
    palsToUseSTA = [palToUse]
    for palToUseSTA in palsToUseSTA: sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)
    ############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

    targetCongestion = paramsDict["targetCongestion"]["val"]
    congestionInfo = []
    
    ############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################
    #Step 1.  Congestion at starting traffic level.
    trafficValue = int(trafficBW.replace("M",""))
    jsonPath, theCongestion = getCurrentCongestion()
    print("The current congestion is {} using a rate of {}".format(theCongestion,trafficBW))
    congestionInfo.append({"rate":trafficValue, "dataPath":jsonPath, "congestion":theCongestion})
    sd2Utils.logToJSON(globalsfile.resultsPath, {"congestion":congestionInfo})
    if haveCreateReport:
        reportJson = createReport.plot(directory_name,globalsfile.outputDirPath)
        if kafkaBrokerFound:
            try:
                my_producer.send('plotStream', value = reportJson)
            except:
                print("The Kafka broker doesn't seem to be responding.")
                kafkaBrokerFound = False
    

    #Step 2.  Scale to what would give you the desired congestion level using a linear scale.
    trafficValue = int(targetCongestion/theCongestion * trafficValue)
    trafficBW = "{}M".format(trafficValue)
    print("Updating the traffic rate to {}".format(trafficBW))
    time.sleep(5)
    trafficPair = tpDictList[0]
    trafficPair["bitrate"] = trafficBW
    sd2Utils.updateTrafficPair(trafficPair)
    jsonPath, theCongestion = getCurrentCongestion()
    print("The current congestion is {} using a rate of {}".format(theCongestion,trafficBW))
    congestionInfo.append({"rate":trafficValue, "dataPath":jsonPath, "congestion":theCongestion})
    sd2Utils.logToJSON(globalsfile.resultsPath, {"congestion":congestionInfo})
    if haveCreateReport:
        reportJson = createReport.plot(directory_name,globalsfile.outputDirPath)
        if kafkaBrokerFound:
            try:
                my_producer.send('plotStream', value = reportJson)
            except:
                print("The Kafka broker doesn't seem to be responding.")
                kafkaBrokerFound = False

    #Step 3.  Iterate to find the traffic level that gets you the congestion level you want.
    targetCongestionDelta = paramsDict["targetCongestionDelta"]["val"]
    nextRate = getNextSetting(congestionInfo,targetCongestion,targetCongestionDelta)
    while nextRate != None:
        trafficValue = nextRate
        trafficBW = "{}M".format(trafficValue)
        print("Updating the traffic rate to {}".format(trafficBW))
        time.sleep(5)
        trafficPair = tpDictList[0]
        trafficPair["bitrate"] = trafficBW
        sd2Utils.updateTrafficPair(trafficPair)
        jsonPath, theCongestion = getCurrentCongestion()
        print("The current congestion is {} using a rate of {}".format(theCongestion,trafficBW))
        congestionInfo.append({"rate":trafficValue, "dataPath":jsonPath, "congestion":theCongestion})
        sd2Utils.logToJSON(globalsfile.resultsPath, {"congestion":congestionInfo})
        if haveCreateReport:
            reportJson = createReport.plot(directory_name,globalsfile.outputDirPath)
            if kafkaBrokerFound:
                try:
                    my_producer.send('plotStream', value = reportJson)
                except:
                    print("The Kafka broker doesn't seem to be responding.")
                    kafkaBrokerFound = False
        nextRate = getNextSetting(congestionInfo,targetCongestion,targetCongestionDelta)        
        
    ############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

    ############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########
    testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))

    print()
    print('#########################################')
    print('>>> Getting test results')
    print('#########################################')

    testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
    print('')
    print('##############################################################')
    print("########## %s TEST DONE " % testName)
    print("########## Test run time: %s. " % testRunTime)
    print('##############################################################')

#____________________________________________________________________________________________________________________________
def getCurrentCongestion():

    json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False)
    newName = "{}_{}_NSS{}_MCS{}".format(paramsDict["trafficType"]["val"],paramsDict["iperfMode"]["val"],paramsDict["nss"]["val"],paramsDict["mcs"]["val"])
    newPath = globalsfile.outputDirPath + newName + '.zip'
    command = "mv " + json_path + " " + newPath
    #print("Renaming the json file using this command: {}".format(command))
    os.system(command)        

    retObj = createReport.extract(newPath,ea_root)

    return newPath, retObj["load"]["WiFi"]
#____________________________________________________________________________________________________________________________
def getNextSetting(congestionInfo,targetCongestion,targetCongestionDelta):

    nextRate = None
    
    ciLen = len(congestionInfo)
    lastCongestion = congestionInfo[ciLen-1]["congestion"]
    lastRate       = congestionInfo[ciLen-1]["rate"]
    currentDelta = abs(lastCongestion-targetCongestion)
    if currentDelta <= targetCongestionDelta:
        return nextRate
    else:
        lastStep = congestionInfo[ciLen-1]["rate"] - congestionInfo[ciLen-2]["rate"]
        direction = +1
        if lastCongestion > targetCongestion: direction = -1
        stepSize = lastStep
        if ciLen >= 3: # Decide if you want to start doubling or halving the step sizes
            lastDelta = congestionInfo[ciLen-1]["congestion"] - targetCongestion
            previousDelta = congestionInfo[ciLen-2]["congestion"] - targetCongestion
            if lastDelta*previousDelta >0: #Means that you continue to be above, or below, the target
                stepSize *= 2
            elif lastDelta*previousDelta <0: #Means that you are straddling the target
                stepSize /=2
        else:
            stepSize /=2  
                
        nextRate = congestionInfo[ciLen-1]["rate"] + stepSize*direction
        nextRate = int(nextRate)
        if nextRate<=0:  # "0M" is a special case, so if you get here, don't use it.  Use something small instead
            nextRate = 1

        if nextRate == lastRate:
            nextRate = None
            
        return nextRate
#____________________________________________________________________________________________________________________________

main()
