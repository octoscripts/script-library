'''
Test Description
================
Example of using Kafka to produce analysis in semi-real time, using a manual RvR test.
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

Plugin1 = "/home/octoscope/Documents/script-home/plugins/getDUTstats.py"

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

attenuationList = []
attenuationList = paramsDict["steps"]["val"].split(",")

allData = {"perAttenData":{}}

for attenuation in attenuationList:
    attenuation = float(attenuation)
    allData["perAttenData"][attenuation] = {}

    print("\n\n{}".format(cGreen))
    print("Setting attenuation to {}.".format(attenuation))
    print("\n\n{}".format(cNormal))
    
    if "STA" in palToUseSTA: endType = "S"
    else: endType = "P"
    offsetValA = sd2Utils.setAtten(attenToUseA,paramsDict[attenToUseA]['val']['devType'],attenuation,primaryChannel=theChannel,endType=endType,mpeBypassValue=63)
    offsetValB = sd2Utils.setAtten(attenToUseB,paramsDict[attenToUseB]['val']['devType'],attenuation,primaryChannel=theChannel,endType=endType,mpeBypassValue=63,pushConfig=True)

    ############### END SECTION: BUILD THE TEST OBJECT #########################

    ############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

    sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)

    ############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED  #########################

    ############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

    ################################# Capture and run. #################################

    print("{} Start the subprocess with {} {}".format(cRed,[Plugin1],cNormal))
    p = subprocess.Popen(["python3",Plugin1])
    print("{} Poll is {}, and Subprocess return code is {}{}".format(cGreen,p.poll(),p.returncode,cNormal))

    json_path = sd2Utils.runAutotest(sleepTime=2,unzip=False,saveCSV=False)

    print("{} Stop the subprocess by killing the subprocess with .kill() {}".format(cRed,cNormal))
    p.kill()
    pidList = sd2Utils.isServiceRunning(Plugin1)
    print("{} PID list for {} analysis is {} {}".format(cRed,Plugin1,pidList,cNormal))
    

    #Rename the JSON zip file.
    useName = "KafkaExample" + "_" + str(attenuation) + "dB"
    newPath = globalsfile.outputDirPath + "/" + useName + ".zip"
    command = "mv " + json_path + " " + newPath
    print("Renaming the json file using this command: {}".format(command))
    os.system(command)

    if haveCreateReport:
        print()
        print('#########################################')
        print('>>> Getting test results')
        print('#########################################')
        lastData = {}
        theData = createReport.analyze(directory_name,newPath,ea_root)
        allData["perAttenData"][attenuation] = theData
        if kafkaBrokerFound:
            previous = None
            keepGoing = True
            while keepGoing:
                raw_messages = my_consumer.poll(timeout_ms=5000, max_records=100)
                if raw_messages == {}:
                    keepGoing = False
                for topic_partition, messages in raw_messages.items():
                    #print("Topic Partition is {}".format(topic_partition))
                    #print("Length of messages is {}".format(len(messages)))
                    lastMessage = messages[len(messages)-1]
                    lastData = lastMessage.value
                    #print("The previous last data element is {}".format(previous))
                    #print("The last data element is {}\n\n".format(lastData))
                    if lastData == previous:
                        keepGoing = False
                    else:
                        previous = lastData
                        time.sleep(5)
            theDutRssi = []
            if "dutRSSI" in lastData: theDutRssi = lastData["dutRSSI"]
            aveDutRssi = 0
            for item in theDutRssi: aveDutRssi += item["y"]
            if len(theDutRssi)>0: aveDutRssi /= len(theDutRssi)
            else: aveDutRssi = None
            allData["perAttenData"][attenuation]["aveDutRssi"] = aveDutRssi
            #print("\n Here is the DUT RSSI collected:  {} \n".format(theDutRssi))
            '''
                msgcnt = 0
                for message in messages:
                    fields = message._fields
                    if "topic" in fields and "value" in fields:
                        topic = message.topic
                        data = message.value
                        datacnt=0
                        for item in data:
                            print("{}.{}.     {} picked up from item {} in topic {}.".format(msgcnt,datacnt,data[item],item,topic))
                            datacnt += 1
                    msgcnt += 1
            '''        
        sd2Utils.logToJSON(globalsfile.resultsPath, allData)

    resultDict["testInfo"]["Offset_Value_PathA"] = offsetValA
    resultDict["testInfo"]["Offset_Value_PathB"] = offsetValB


    if haveCreateReport:        
        reportJson = createReport.summarize(directory_name,globalsfile.outputDirPath,ea_root)
        if kafkaBrokerFound:
            try:
                my_producer.send('plotStream', value = reportJson)
            except:
                print("The Kafka broker doesn't seem to be responding.")
                kafkaBrokerFound = False
            
    ############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
resultDict = {}
resultDict = {'testRunTime':testRunTime}
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
    if kafkaBrokerFound:
        try:
            my_producer.send('plotStream', value = reportJson)
        except:
            print("The Kafka broker doesn't seem to be responding.")
            kafkaBrokerFound = False

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
