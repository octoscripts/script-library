'''
Test Description
================
Simple MLO setup.
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime

import zipfile
from zipfile import ZipFile

import pprint
pp = pprint.PrettyPrinter(indent=4)


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

#Fix the traffic pair
theTrafficPair = tpDictList[0]
if theTrafficPair["to"]["trafficAddress"]   in ipMapping: theTrafficPair["to"]["trafficAddress"]   = ipMapping[theTrafficPair["to"]["trafficAddress"]]
if theTrafficPair["from"]["trafficAddress"] in ipMapping: theTrafficPair["from"]["trafficAddress"] = ipMapping[theTrafficPair["from"]["trafficAddress"]]
sd2Utils.updateTrafficPair(theTrafficPair)

tpDictList[0] = theTrafficPair

staInlineSniffing = paramsDict["staInlineSniffing"]["val"]
#Set this up for inline sniffing.
if staInlineSniffing:
    #Setting up sniffers.
    #Is SnifferRelay running?
        SnifferRelayPidList = sd2Utils.checkNstartNodeService(paramsDict['SnifferRelay_location']['val']['dirpath'],paramsDict['SnifferRelay_location']['val']['filename'],True,args=paramsDict['oBox_server']['val']['publicip'])

        snifSetDictList = []
        snifDispDictList = []
        snifStartDictList = []

        mloBands = mloConfig["bands"]
        for snifferPal in palsInTest:
            for mloBand in mloBands:
                if not mloBands[mloBand]["member"]: continue                

                useChannel = mloBands[mloBand]["channel"]
                if "6" in mloBand: useChannel += 190
                print("Set up a sniffer with Pal {}, on band {}".format(snifferPal,mloBand))
                (snifSetDictList, snifDispDictList, snifStartDictList) = sd2Utils.setupSniffer(snifferPal, mloBand, 160, useChannel, interface, snifSetDictList, snifDispDictList, snifStartDictList, headerFrames=True, mgmtFrames=False)

        #Only set sniffers if they are NOT existing endpoints.
        print("The Pals being used in this test are {}".format(palsInTest))
        palsInTestMgmtIPs = []
        for p in palsInTest: palsInTestMgmtIPs.append(paramsDict[p]["val"]["address"])
        print("The management addresses of these pals are {}".format(palsInTestMgmtIPs))
        for index in range (len(snifSetDictList) - 1, -1, -1):
            object = snifSetDictList[index]
            if object["palAddress"] in palsInTestMgmtIPs:
                print("Remove this object with address {} from the snifSetDictList:\n {}".format(object["palAddress"],object))
                snifSetDictList.remove(object)

        #Make sure snifDispDictList has unique probe IDs.
        for object in snifDispDictList:
            tag = object["palRadio"].replace("RADIO_","")
            object["probeID"] += "_{}".format(tag)

        '''
        print('')
        print('#################################')
        #print('>>> snifSetDictList:')
        #pp.pprint(snifSetDictList)
        print('>>> snifDispDictList:')
        pp.pprint(snifDispDictList)
        #print('>>> snifStartDictList:')
        #pp.pprint(snifStartDictList)
        #sys.exit()        
        '''
        
        # Update sniffer Autotest configs and push
        sd2Utils.updateAutotestInst(snifSetDictList, "synchroSniffers")
        sd2Utils.updateAutotestInst(snifDispDictList, "snifferDisplay", pushConfig=True) 


############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

palsToUseSTA = [palToUse]
#for palToUseSTA in palsToUseSTA: sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)
#Let's not for now.  Need to understand this better.
time.sleep(10)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

if staInlineSniffing:
    sd2Utils.startSniffers(snifStartDictList)

totalTests = paramsDict["totalTests"]["val"]
try:
    totalTests = int(totalTests)
except:
    totalTests = 1
if totalTests<1: totalTests = 1

for testNumber in range (0,totalTests):

        json_path = sd2Utils.runAutotest(sleepTime=2,saveCSV=False,unzip=False,saveTaJSON=False)
        newPath = json_path.replace(".zip","_{}.zip".format(testNumber))
        command = "mv " + json_path + " " + newPath
        print("Renaming the json file using this command: {}".format(command))
        os.system(command)        
        print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,newPath,cNormal))

        pcapFile = None
        if staInlineSniffing:
            globalsfile.fileSuffix = '_PCAP_{}'.format(testNumber)   # Set pcap filename suffix
            pcapFile = sd2Utils.stopSniffers()        

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))

print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')

#Place a PDF export in the same location
'''
pdf_dict = {
"showAll": False,
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

# NOTE! Report creation requires a createReport.py file. 
if haveCreateReport:
    
    print('')
    print('##############################################################')
    print("########## Creating final report ")
    print('##############################################################')
    
    ea_root = sd2Utils.whereIsEA()
    
    reportJson = createReport.main(directory_name,globalsfile.outputDirPath,json_path,pcapFile,ea_root) # Actual arguments depend on createReport script
    with open(globalsfile.outputDirPath + "/" + "simpleMLO.json","w",encoding="utf-8") as f:
        json.dump(reportJson,f,ensure_ascii=False,indent=4)

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("##### %s TEST DONE " % testName)
print("##### Test run time: %s. " % testRunTime)
print('##############################################################')	
