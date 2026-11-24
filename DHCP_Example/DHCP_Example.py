'''
Test Description
================
DHCP setup example.  Note that you have to figure out the IP address before you create the traffic pair.
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
# Set up some text coloring
cRed=   '\033[m'
cGreen= '\033[m'
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

#Setting attenuation values for attenuators or MPEs:
sd2Utils.setVatten('QJ-34',0,attenValueStop=0)

#Setting up traffic pairs.  These will need to be adjusted for actual IP addresses.
tpDictList = []
tpDictList = sd2Utils.setupTrafficPairs('L2E-STApal', '5g', 'dn', tpDictList, useWANendpoint=False, measureCongestion=False, palAsAP='', tType='iperf3', tMode='tcp', tBW='0M', tParallel=0, tLength='', tWindow='')

#Setting up Pal configurations:
staDictList = []
staDictOverride={"bandwidth":"BANDWIDTH_80_ADAPT","ipMode":"IP_DHCP"}
staDictList = sd2Utils.setupSTA('L2E-STApal', '5g', staDictList, type="INTERFACE_AX", channel=36, bssid='', streams=2, staDictOverride=staDictOverride, pushConfig=True)

targetRadio = staDictList[0]['palRadio']

#Setting up AP configurations:
apDictList = []

############### START SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED, AND FOR AN IP ADDRESS TO BE ASSIGNED  #########################

palsToUseSTA = ["L2E-STApal"]
for palToUseSTA in palsToUseSTA:    
    sd2Utils.waitForAssociation(palToUseSTA,targetRadio,timeToWait=45)
    if globalsfile.online:
        print("The AP is associated.  Now wait until you have the IP address.")
        theIP = globalsfile.palStatus["ipAddress"]
        while len(theIP)==0:
            print("No IP address assigned yet.")
            sd2Utils.getPalStatus(palToUseSTA,3,targetRadio=targetRadio)
            theIP = globalsfile.palStatus["ipAddress"]
        print("The assigned IP to {} on radio {} is {}".format(palToUseSTA,targetRadio,theIP))
        #It's a good idea to update the IP address in paramsDict in case you need to access it again quickly.
        theEndpoints = paramsDict[palToUseSTA]["val"]["endpoints"]
        for endpoint in theEndpoints:
            if endpoint == targetRadio: theEndpoints[endpoint]["defaultIp"] = theIP

    print("Updated the IP address in paramsDict in case that IP address needs to be used again.")
    print("For {} the paramsDict entry is now{}.".format(palToUseSTA,paramsDict[palToUseSTA]))


############### END SECTION: WAIT FOR REQUIRED PALS TO BE ASSOCIATED, AND FOR AN IP ADDRESS TO BE ASSIGNED  #########################

############### REASSIGN THE IP ADDRESS TO THIS TRAFFIC PAIR  #########################
#Update your traffic pair with the correct IP address.
theTrafficPair = tpDictList[0]
theAlias = paramsDict[palToUseSTA]["val"]["alias"]
if theTrafficPair["to"]["alias"] == theAlias: theTrafficPair["to"]["trafficAddress"] = theIP
elif theTrafficPair["from"]["alias"] == theAlias: theTrafficPair["from"]["trafficAddress"] = theIP
sd2Utils.updateTrafficPair(theTrafficPair)

############### START SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

################################# Capture and run. #################################

json_path = sd2Utils.runAutotest(sleepTime=2)
print("\n>>>{} Zipped file of all JSONs at: {} {}".format(cGreen,json_path,cNormal))


############### END SECTION: START THE TEST, AND WAIT FOR IT TO COMPLETE #########################

############### START SECTION: DO WHATEVER OTHER ACTIVITY YOU WANT TO DO AFTER THE TEST HAS COMPLETED ###########

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))

print()
print('#########################################')
print('>>> Getting test results')
print('#########################################')

#Place a PDF export in the same location
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

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
