'''
Test Description
================
Example of using the External Statistics Interface in an RvR test.
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime
import subprocess

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

############################

##############################################################################################################
###                                                                                                          #
###                                                                                                          #
#                                                                                                            #
#  Be sure to enable the external data interface for this test.                                              #
updateDict = {"externalDataInterfaceEnable": True}                                                           #
sd2Utils.updateAutotest(updateDict,pushConfig=True)                                                          #
#                                                                                                            #
###                                                                                                          #
###                                                                                                          #
##############################################################################################################

##############################################################################################################
###                                                                                                          #
###                                                                                                          #
#  This is the location of the script you will use to pull the external statistics.                          #
#  At the moment, ths script must be running on the octobox server in order to connect to Kafka              #
#  So, to be very clear, this is the full path to the script location ON THE SERVER.                         #
#                                                                                                            #
pluginPath = paramsDict["pluginPath"]["val"].strip()                                                         #
if pluginPath[len(pluginPath)-1] != "/": pluginPath += "/"                                                   #
pluginName = paramsDict["pluginName"]["val"].strip()                                                         #
Plugin1 = pluginPath + pluginName                                                                            #
print("The plugin will be placed in {}".format(Plugin1))                                                     #
#                                                                                                            #
#                                                                                                            #
#                                                                                                            #
###                                                                                                          #
###                                                                                                          #
##############################################################################################################

##############################################################################################################
###                                                                                                          #
###                                                                                                          #
#  The extraction script needs to be running on the server.  So we need to do two things.  (1) We need       #
#  to place a file onto the server, and (2) we need to run that file during our test.  If the test script    #
#  is running on a script machine, we have no way to do that other than to use the basic-server APIs.        #
#  So we need to confirm that we have basic-server running on the server, and then we can define some        #
#  commands we will use.  For example, we use the basic-server API to run the script from the script         # 
#  machine, and we also want to stop it when we are done.                                                    #
#                                                                                                            #
#  Is Basic server running on octoBox server?  If it's not, this will terminate the script                   #
#  with an error message.                                                                                    #  
#                                                                                                            #
sd2Utils.checkBasicServerOnOBox()                                                                            #
urlIP = paramsDict["oBox_server"]["val"]["publicip"]                                                         #
serverExec =  "http://" + urlIP + ":8383/exec?command="                                                      #
serverSpawn =  "http://" + urlIP + ":8383/spawn?command="                                                    #
startUrl = serverSpawn + "python3 {} {}".format(Plugin1,testName)                                            #
splits = Plugin1.split("/")                                                                                  #
stopUrl  = serverExec + "pkill -9 -f {}".format(splits[len(splits)-1])                                       #
#                                                                                                            #
#                                                                                                            #
#                                                                                                            #
###                                                                                                          #
###                                                                                                          #
##############################################################################################################


##############################################################################################################
###                                                                                                          #
###                                                                                                          #
#  Find the local copy of the extraction file, and place it onto the server in the desired location.         #
#                                                                                                            #
localPluginFile = paramsDict["localPluginFile"]["val"]                                                       #
f = open(directory_name + localPluginFile,"r")                                                               #
content = f.read()                                                                                           #
api_endpoint = "http://" + urlIP + ":8383/writeFile"                                                         #
data = {'path':pluginPath,'fileName':pluginName,'content':content}                                           #
try:                                                                                                         # 
    r = requests.post(url=api_endpoint, data=data, timeout=15)                                               #
except requests.exceptions.RequestException as error:                                                        #
    info("Error: ", error)                                                                                   #
    sys.exit(44)                                                                                             #
#                                                                                                            #
###                                                                                                          #
###                                                                                                          #
##############################################################################################################

print("The contents of the local file {} have been placed on the server at location {}. This is the extraction file that will be executed.".format(localPluginFile,Plugin1))
time.sleep(3)

sd2Utils.topoDaddPathsNBoxesToParamsDict()
(meshInfoDict,calfileDict)= sd2Utils.checkCalfileandDiscoveryOK(directory_name,checkDiscovery=False)

# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

# Build list for config check

haveCreateReport = False
createReportFilePath = directory_name+'/createReport.py'
if os.path.exists(createReportFilePath):
    import createReport
    haveCreateReport = True
else:
    print("{} No createReport at {} {}".format(cRed,createReportFilePath,cNormal)) 


palToUseSTAdrop = paramsDict["palToUseSTA"]["val"]
for item in palToUseSTAdrop:
    if item["selected"]:
        palToUseSTA = item["value"]
        break

(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
attenList = [attenToUseA,attenToUseB]

testUses=paramsDict['testUses']['val']+[palToUseSTA]+attenList
print(">>> testUses: ", testUses)

# Check that system can support the test
sd2Utils.checkSystemConfig(testUses)

# Set attens to known state (all boxes isolated from each other)
sd2Utils.isolateAllBoxes()

#Get information about the server
serverMIp = paramsDict["oBox_server"]["val"]["address"]
serverIp  = paramsDict["oBox_server"]["val"]["defaultIp"]
serverParts = serverIp.split(".")

pieces = serverIp.split('.')
ipGateway = pieces[0] + "." + pieces[1] + "." + pieces[2] + "." + "1"

#Find EA
ea_root =sd2Utils.whereIsEA()

# Create copy of initial autotest config
emptyTest = json.dumps(globalsfile.autotest_dict)

theChannel = paramsDict["primaryChannel"]["val"]
theBand = "24g"
if int(theChannel) > 14: theBand = "5g"
if int(theChannel) > 190: theBand = "6g"

thisDrop = paramsDict["bw"]["val"]
for item in thisDrop:
    if item["selected"]:
        theBW = item["value"]
        break
thisDrop = paramsDict["interface"]["val"]
for item in thisDrop:
    if item["selected"]:
        theInterface = item["value"]
        break
thisDrop = paramsDict["direction"]["val"]
for item in thisDrop:
    if item["selected"]:
        theDirection = item["value"]
        break
theStreams = 2  #Do we want this to be configurable?

thisJson = {"channel":theChannel, "band":theBand, "BW":theBW, "interface":theInterface, "direction":theDirection, "nss":theStreams}
sd2Utils.logToJSON(globalsfile.resultsPath, {"configuration":thisJson})

# Reset the autotest_dict.
globalsfile.autotest_dict = json.loads(emptyTest)
print("HERE IS THE EMPTY TEST CONFIG")
print(globalsfile.autotest_dict)
autotest_dict = sd2Utils.initializeAutotest()

#print(autotest_dict)
if "WARNINGS" in autotest_dict:
    print("Looks like there are some issues with the autotest, probably with the API.  Getting a copy directly.")
    print("What we have at the moment is: '{}'".format(autotest_dict))
    autotest_dict = sd2Utils.getAutotestFromDB()
    globalsfile.autotest_dict = autotest_dict
    #print(autotest_dict)


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
            
############### START SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################
    
# ssid, security and password are taken from params_system['dut']
ssidval = 'dutssid'+theBand.replace('g','')
ssid = paramsDict['dut']['val'][ssidval]
# valid security options:  'SECURITY_NONE', 'SECURITY_WPA', 'SECURITY_WPA2', 'SECURITY_WPA_WPA2_MIXED', 'SECURITY_WPA3', 'SECURITY_WPA3_WPA2_MIXED'
securityval = 'dutsecurity'+theBand.replace('g','')
security = paramsDict['dut']['val'][securityval]
passwordval = 'dutpass'+theBand.replace('g','')
password = paramsDict['dut']['val'][passwordval]
print('>>> ssid: %s, security: %s, password: %s, channel: %s, band: %s' % (ssid, security, password, theChannel, theBand))


iperfMode = paramsDict["iperfMode"]["val"]
if iperfMode!='tcp' and iperfMode!='udp':
    print(">>> {} is not a valid iperf mode.".format(iperfMode))
    iperfMode = None

############### END SECTION: GATHER UP TEST-SPECIFIC PARAMETERS #########################

############### START SECTION: BUILD THE TEST OBJECT #########################

print('\n>>> Adding test information to testresults.json')
resultDict = {"testInfo": testInfoDict}
resultDict['testInfo'].update({"timeStamp":globalsfile.timeStamp, "security":security, "ssid":ssid, "password":password,"band":theBand, "primaryChannel":theChannel, "bandwidth":theBW, "interface":theInterface, "streams":theStreams, "upOrDown": theDirection })
resultDict['testInfo'].update({"scriptSuiteVersion":globalsfile.scriptSuiteVersion})
resultDict['testInfo'].update({"starDustVersion":globalsfile.starDustVersion})
resultDict['testInfo'].update({"palFWversions":globalsfile.palFWdict})
if test_param_alt_file:
    resultDict['testInfo'].update({"testParamAltFile":test_param_alt_file})

time.sleep(5)

#Setting up traffic pairs:
tpDictList = []
tpDictList = sd2Utils.setupTrafficPairs(palToUseSTA, theBand, theDirection, tpDictList)
    
#Setting up Pal configurations:
staDictList = []
staoverride={"ssid":ssid, "password": password, "security": security }
staoverride["txAtten"] = 5
staoverride["bandwidth"] = theBW
if "_N"  in theInterface or "_AC" in theInterface: staoverride["guardInterval"] = 'GUARD_0_4US'
if "_AX" in theInterface or "_BE" in theInterface: staoverride["guardInterval"] = 'GUARD_0_8US'

staDictList = sd2Utils.setupSTA(palToUseSTA, theBand, staDictList, type=theInterface, channel=theChannel, staDictOverride=staoverride, pushConfig=True)
targetRadio = staDictList[0]['palRadio']

#Setting attenuation values for attenuators or MPEs:
(attenToUseA,attenToUseB) = sd2Utils.whichBoxCatten()
print('>>> attenToUseA: ', attenToUseA)
print('>>> attenToUseB: ', attenToUseB)

if "STA" in palToUseSTA: endType = "S"
else: endType = "P"
qaStart = paramsDict["quadAttenStart"]["val"]
qaStop  = paramsDict["quadAttenStop"]["val"]
offsetValA = sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],qaStart,attenValueStop=qaStop,primaryChannel=theChannel,endType=endType,mpeBypassValue=63)
offsetValB = sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],qaStart,attenValueStop=qaStop,primaryChannel=theChannel,endType=endType,mpeBypassValue=63,pushConfig=True)

############### END SECTION: BUILD THE TEST OBJECT #########################

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

##############################################################################################################
###                                                                                                          #
###                                                                                                          #
#  The extraction script must start AFTER the test starts.  Therefore, we do not use runAutotest             #
#  since that blocks further execution until completion of the test.  So we use startAutotest so that we     #
#  can then start the extraction script.                                                                     #
#                                                                                                            #
sd2Utils.startAutotest()                                                                                     #
time.sleep(1)                                                                                                #
#                                                                                                            #
###                                                                                                          #
###                                                                                                          #
##############################################################################################################


##############################################################################################################
###                                                                                                          #
###                                                                                                          #
#  Start the external statistics accumulation process.  So, sending the startUrl to the basic-server API.    #
#  Note that we use SPAWN (see the startUrl definition) so that the API call is non-blocking.                #
#                                                                                                            #
print("{} Start the external statistics accumulation process with {} {}".format(cRed,Plugin1,cNormal))       #
resp = requests.get(url=startUrl, timeout=REST_TIMEOUT)                                                      #
jsn = json.loads(resp.text)                                                                                  #
print('>>> jsn from external statistics start process: ', jsn)                                               #
#                                                                                                            #
###                                                                                                          #
###                                                                                                          #
##############################################################################################################

#json_path = sd2Utils.runAutotest(sleepTime=2,unzip=False,saveCSV=False)

##############################################################################################################
###                                                                                                          #
###                                                                                                          #
#  Wait for the test to complete, and once done, extract and store the data.                                 #
#                                                                                                            #
sd2Utils.waitForAutotestDone(sleepTime=2)                                                                    #
json_path = sd2Utils.getAutotestResults(unzip=False,saveCSV=False,saveTaJSON=False)                          #
#                                                                                                            #
###                                                                                                          #
###                                                                                                          #
##############################################################################################################

##############################################################################################################
###                                                                                                          #
###                                                                                                          #
#  Stop the external statistics accumulation process.  So, sending the stopUrl to the basic-server API.      #
#  Note that we use EXEC (see the stopUrl definition) since it happens quickly and blocking is not an issue. #
#                                                                                                            #
print("{} Stop the subprocess by killing the subprocess with {} {}".format(cRed,stopUrl,cNormal))            #
resp = requests.get(url=stopUrl, timeout=REST_TIMEOUT)                                                       #
jsn = json.loads(resp.text)                                                                                  #
print('>>> jsn from external statistics stop process: ', jsn)                                                #
#                                                                                                            #
###                                                                                                          #
###                                                                                                          #
##############################################################################################################

#Rename the JSON zip file.
useName = "ExternalStatisticsExample"
newPath = globalsfile.outputDirPath + "/" + useName + ".zip"
command = "mv " + json_path + " " + newPath
print("Renaming the json file using this command: {}".format(command))
os.system(command)

if haveCreateReport:
    print()
    print('#########################################')
    print('>>> Getting test results')
    print('#########################################')
    theData = createReport.analyze(directory_name,newPath,ea_root)
    sd2Utils.logToJSON(globalsfile.resultsPath, theData)

############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
resultDict = {}
resultDict = {'testRunTime':testRunTime}
resultDict["Offset_Value_PathA"] = offsetValA
resultDict["Offset_Value_PathB"] = offsetValB
sd2Utils.logToJSON(globalsfile.resultsPath, resultDict)

#########Generating JSON reports

#Remove existing test report so that if there is a problem here, you don't get fooled into thinking that an old report is the new report.
rmResult = os.system("rm " + directory_name + "TestReport.json")
print("Removing any old TestReport.json: {}".format(rmResult))

print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))

print('')
print('##############################################################')
print("########## Creating HTML report ")
print('##############################################################')	


if haveCreateReport:
    reportJson = createReport.summarize(directory_name,globalsfile.outputDirPath,ea_root)


testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
