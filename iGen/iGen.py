'''
Test Description
================
Simple test to set up one traffic pair and one sniffer and run traffic while doing packet capture.\n Illustrates all the basic functions of setting up results file folder and names, setting attenuators, settting up traffic pairs, setting up and associating STA and setting up, starting and stopping sniffing.
NOTE! This test requires an AP in Box A.
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

############### START SECTION: BUILD DICTIONARY #########################

# Find working directory
try:
    directory_name=sys.argv[1]
    print(f">>> The directory name passed in is {directory_name}",flush=True)
except:
    directory_name = os.getcwd()
    print(f'>>> No directory_name provided, so using {directory_name}',flush=True)

# This line makes sure script can run from command line without SM
if directory_name[len(directory_name)-1] != "/": directory_name += "/"

sys.path.append(directory_name + '../')

import globalsfile	# MUST HAVE to be able to reference global variables stored in globalsfile.py
import sd2Utils		# MUST HAVE. Contains functions used in this script and other helpful functions

from stardust_socket_listen import StardustSocketListen # MUST HAVE if you are going to use any real time stats

# Reference params and base auto test dictionaries 
paramsDict = globalsfile.paramsDict

REST_TIMEOUT = paramsDict['rest_timeout']['val'] # Used by REST API calls
print(f'\n>>> REST_TIMEOUT: {REST_TIMEOUT}')

#Get the location of the results directory, as far as script-manager is concerned
response = requests.get(f"http://{globalsfile.hostIpAddress}:5678/getResultsDirectory")
theJson = response.json()
resultsDirectory = theJson["resultsDirectory"]
print(f">>> The results directory is {resultsDirectory}.")

# This is to bring in alternate parameters set in Script Manager Arguments field
# This enables the same script to be run with a different set of test parameters stored in a json file
#-----  Look at the test parameter info, in arg[2]
try:
    test_param_alt_file=sys.argv[2]
    print(f">>> The parameters file name passed in is {test_param_alt_file}.")
except:
    print('>>> No parameters file name provided')
    test_param_alt_file = None

#Update paramsDict if there is a test_param_alt_file found
if test_param_alt_file:
	
	with open(directory_name+test_param_alt_file) as f:
	  test_params = json.load(f)
	f.close()
	
	if paramsDict['debug']['val']:
		print(f'>>> test_params: {test_params}')
	paramsDict.update(test_params)
	
# Create the output folder
globalsfile.outputDirPath = f"{resultsDirectory}{paramsDict['topDirectory']}/{paramsDict['subDirectory']}"

if not os.path.exists(globalsfile.outputDirPath):
	os.makedirs(globalsfile.outputDirPath)
print('')
print('##############################################################')
print (f'>>> Data will be stored in {globalsfile.outputDirPath}')
print('##############################################################')

testPrefix = paramsDict['testPrefix']['val']   	# for test record filenames
sd2Utils.getTimestampS()	# for test record filenames

# Create path to test result log file
globalsfile.resultsPath = os.path.join(globalsfile.outputDirPath,
    f"{globalsfile.timeStamp}_{paramsDict['dut']['val']['dutId']}_{paramsDict['dut']['val']['dutRevision']}_{testPrefix}_testresultlog.json"
)

# Bring in the testName. This is used by most REST API calls. 
# MAKE SURE there are no spaces in the test name used.
testName = paramsDict['testName']['val']
print(f'\n>>> testName: {testName}')

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

#Put iGen commands in here
iGenIP = paramsDict["iGen-A"]["val"]["address"]

#To control the iGen we have to use the basic-server, curl mechanism for now.
serverMgmtIp = paramsDict["oBox_server"]["val"]["publicip"]
execUrl = "http://" + serverMgmtIp + ":8383/exec?command="
spawnUrl = "http://" + serverMgmtIp + ":8383/spawn?command="

'''
modes = ["status","system","monitor","traffic","wave"]
for mode in modes:
    igenInfo = sd2Utils.getIgenInfo(mode)
    print("For mode {}, returned status is {}".format(mode,igenInfo))
    time.sleep(2)
'''

# WAVEFORM PART
doWaveForm = False
if doWaveForm:

    URL = "http://" + iGenIP + "/api/wave"
    curlPart = "curl http://"+iGenIP+"/api/wave"

    URL = execUrl+curlPart
    print("Getting iGen status with " + URL)
    resp = requests.get(url=URL)
    jsn = json.loads(resp.text)
    #print(json.dumps(jsn, indent=4,sort_keys=True))

    stdout = jsn["stdout"]
    print(stdout)
    iGenDict = json.loads(stdout)


    #To get the string version of the dictionary, use json.dumps
    iGenString = json.dumps(iGenDict)
    print(iGenString)

    apChannel = paramsDict["primaryChannel"]["val"]
    apFreq = sd2Utils.ChannelNumberToFrequency(apChannel)
    print("The AP channel is {}, and so the frequency is {}".format(apChannel,apFreq))

    iGenDict["mode"] = "waveform"
    iGenDict["waveform_mode"] = "radar"
    iGenDict["frequency"] = apFreq
    iGenDict["attenuation"] = 0
    iGenDict["RadarType"] = "radar1"

    iGenString = json.dumps(iGenDict)
    curlPart = "curl -X PUT -d '" + iGenString + "' " + "http://"+iGenIP+"/api/wave"

    URL = execUrl + curlPart

    #print("Putting URL {} with data {}".format(URL,iGenUpdate))
    #resp = requests.put(URL,json=iGenUpdate)
    #jsn = json.loads(resp.text)
    #print(jsn)
    print("Putting iGen data using URL {}".format(URL))
    resp = requests.get(url=URL)
    jsn = json.loads(resp.text)
    print(json.dumps(jsn, indent=4,sort_keys=True))

    #Give it time for the iGen start up.
    modeNow = "WhoCares"
    URL = "http://" + iGenIP + "/api/wave"
    curlPart = "curl http://"+iGenIP+"/api/wave"
    URL = execUrl+curlPart
    print("Getting iGen status with " + URL)
    while modeNow != "waveform":
        resp = requests.get(url=URL)
        jsn = json.loads(resp.text)
        stdout = jsn["stdout"]
        #print(stdout)
        iGenNow = json.loads(stdout)
        modeNow = iGenNow["mode"]
        time.sleep(1)

    print("The iGen mode is finally {}".format(modeNow))
    time.sleep(10)

    #Don't forget to shut off the iGen
    curlPart = "curl -X PUT -d '{\"mode\":\"standby\"}' http://172.16.25.1/api/traffic"
    URL = execUrl + curlPart
    print("Putting iGen data using URL {}".format(URL))
    resp = requests.get(url=URL)
    jsn = json.loads(resp.text)
    print(json.dumps(jsn, indent=4,sort_keys=True))


# TRAFFIC PART
doTraffic = True
if doTraffic:
    #Do the same thing for Wi-Fi traffic setting

    URL = "http://" + iGenIP + "/api/traffic"
    curlPart = "curl http://"+iGenIP+"/api/traffic"

    URL = execUrl+curlPart
    print("Getting iGen status with " + URL)
    resp = requests.get(url=URL)
    jsn = json.loads(resp.text)
    #print(json.dumps(jsn, indent=4,sort_keys=True))

    stdout = jsn["stdout"]
    print(stdout)
    iGenDict = json.loads(stdout)

    #To get the string version of the dictionary, use json.dumps
    iGenString = json.dumps(iGenDict)
    print(iGenString)

    apChannel = paramsDict["primaryChannel"]["val"]
    apFreq = sd2Utils.ChannelNumberToFrequency(apChannel)
    print("The AP channel is {}, and so the frequency is {}".format(apChannel,apFreq))

    iGenDict["mode"] = "traffic"
    iGenDict["interface"] = "ac"
    iGenDict["gapValue"] = 223

    iGenString = json.dumps(iGenDict)
    curlPart = "curl -X PUT -d '" + iGenString + "' " + "http://"+iGenIP+"/api/traffic"

    URL = execUrl + curlPart

    otherURL = "http://{}/traffic?mode=traffic".format(serverMgmtIp)
    for key in iGenDict:
        if key != "mode": otherURL += "&{}={}".format(key,iGenDict[key])
    print("\n\nThe other URL that you should be able to use with the new stardust API is:\n {}\n\n".format(otherURL))

    #print("Putting URL {} with data {}".format(URL,iGenUpdate))
    #resp = requests.put(URL,json=iGenUpdate)
    #jsn = json.loads(resp.text)
    #print(jsn)
    print("Putting iGen data using URL {}".format(URL))
    resp = requests.get(url=URL)
    jsn = json.loads(resp.text)
    print(json.dumps(jsn, indent=4,sort_keys=True))

    #Give it time for the iGen start up.
    modeNow = "WhoCares"
    URL = "http://" + iGenIP + "/api/traffoc"
    curlPart = "curl http://"+iGenIP+"/api/traffic"
    URL = execUrl+curlPart
    print("Getting iGen status with " + URL)
    while modeNow != "playback":
        resp = requests.get(url=URL)
        jsn = json.loads(resp.text)
        stdout = jsn["stdout"]
        #print(stdout)
        iGenNow = json.loads(stdout)
        modeNow = iGenNow["mode"]
        time.sleep(1)

    print("The iGen mode is finally {}".format(modeNow))
    time.sleep(10)

    #Don't forget to shut off the iGen
    curlPart = "curl -X PUT -d '{\"mode\":\"standby\"}' http://172.16.25.1/api/traffic"
    URL = execUrl + curlPart
    print("Putting iGen data using URL {}".format(URL))
    resp = requests.get(url=URL)
    jsn = json.loads(resp.text)
    print(json.dumps(jsn, indent=4,sort_keys=True))
