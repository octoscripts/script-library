'''
Test Description
================
Run a pre-configured test on the server.  So, for example, if you have created a test using the UI, but want to automate running it over and over again.
'''
############### START SECTION: IMPORTS #########################
import os
import sys
import json
import requests
import time
import datetime

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

sd2Utils.updateParamsDict()	# Update paramsDict with instrument dicts

############### END SECTION: BUILD DICTIONARY #########################

#____________###############  DO NOT MODIFY ANYTHING ABOVE THIS LINE ###############_______________
# ##################################################################################	
# ##################################################################################
#	                             Start of main test script
# ##################################################################################
# ##################################################################################

# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'

test_name = paramsDict["testName"]["val"]
print("The test you will be running is {} {} {}".format(cGreen,test_name,cNormal))

urlIP = paramsDict["oBox_server"]["val"]["publicip"]
URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/testConfigs"

print("Initializing the test.")
URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/testConfigs/initialize/{}".format(test_name)
print(URL)
myresponse = requests.post(URL, json={}, timeout=REST_TIMEOUT)
#pp.pprint(myresponse.json()) 
print("{} Done. {}".format(cGreen,cNormal))

if ("not found" in myresponse.json()):
    URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/testConfigs/"
    myresponse = requests.get(URL, timeout=REST_TIMEOUT)
    tests = myresponse.json()
    names = []
    for test in tests: names.append(test["name"])
    names.sort()
    list = ""
    for name in names: list += name + "\n"
    print("There are {} tests".format(len(tests)))
    print("{}The valid test names are these.  Pick one.\n{}{}".format(cRed,cNormal,list))
    print("{} Done. {}".format(cGreen,cNormal))
    sys.exit(45)


####Starting Autotest
autotest_push = {"pushConfigs": False}
URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/autotest/start/{}".format(test_name)
print("Starting Autotest with {}...".format(URL))
myresponse = requests.post(URL,json=autotest_push, timeout=REST_TIMEOUT)
print (myresponse.json())

#########Checking for test status
testDuration = paramsDict["testDuration"]["val"]
globalsfile.autoTestStartTimeStamp = time.time() # Test start time.  Usually handled in a startAutoTest, but we are not doing that in this script.
sd2Utils.waitForAutotestDone(testDuration=testDuration)
          
#########Generating JSON reports

jsonZipPath = os.path.join(globalsfile.outputDirPath, globalsfile.latestTimeStamp + '_' + paramsDict['dut']['val']['dutId'] + '_' +paramsDict['dut']['val']['dutRevision'] + '_' + paramsDict['testPrefix']['val'] + globalsfile.fileSuffix + '.zip')
print('>>> getAutotestResults jsonZipPath:', jsonZipPath)

json_extract_path = os.path.join(globalsfile.outputDirPath, globalsfile.latestTimeStamp + '_' + paramsDict['dut']['val']['dutId'] + '_' +paramsDict['dut']['val']['dutRevision'] + '_' + paramsDict['testPrefix']['val'] + globalsfile.fileSuffix)
print('>>> getAutotestResults json_extract_path:', json_extract_path)

URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/reports/json/{}".format(test_name)
json_report = requests.get(URL,timeout=REST_TIMEOUT)
#print (json_report)
with open(jsonZipPath, 'wb') as f:
    for chunk in json_report.iter_content(chunk_size=1024):
        if chunk:
            f.write(chunk)
print("{} Zipped file of all JSONs at: {} {}".format(cGreen,jsonZipPath,cNormal))

'''
with ZipFile('{}'.format(jsonZipPath), 'r') as zipObj:
    zipObj.extractall(path = json_extract_path)
print("{} Unzipped directory of all JSONs at: {} {}".format(cGreen,json_extract_path,cNormal))
'''

'''
#Place a PDF export in the same location
URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/reports/pdf/{}".format(test_name)
pdf_report = requests.get(URL,timeout=REST_TIMEOUT)
pdf_path = jsonZipPath.replace(".zip",".pdf")
with open(pdf_path, 'wb') as f:
    for chunk in pdf_report.iter_content(chunk_size=1024):
        if chunk:
            f.write(chunk)
print("{} PDF file at: {} {}".format(cGreen,pdf_path,cNormal))
'''
    
print("{} Script is complete. {}".format(cGreen,cNormal))

testRunTime = time.strftime("%H:%M:%S", time.gmtime(time.time() - globalsfile.timeStampts))
print('')
print('##############################################################')
print("########## %s TEST DONE " % testName)
print("########## Test run time: %s. " % testRunTime)
print('##############################################################')	
