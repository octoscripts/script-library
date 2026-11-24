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

REST_TIMEOUT = 200
urlIP = "10.100.103.89"

test_name = "simpleAutomationExample"
print("The test you will be running is {} ".format(test_name))

howManyTimes = 3
print("You will be running {} {} times.".format(test_name,howManyTimes))

expectedTime = 30
timeout = expectedTime*3

for index in range (0,howManyTimes):
    fois = index + 1
    print("Running {} this time: #{}.".format(test_name,fois))

    print("Initializing the test.")
    URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/testConfigs/initialize/{}".format(test_name)
    print(URL)
    myresponse = requests.post(URL, json={}, timeout=REST_TIMEOUT)
    print("Done.")

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
        print("The valid test names are these.  Pick one.\n{}".format(list))
        print("Done.")
        sys.exit(45)


    ####Starting Autotest
    autotest_push = {"pushConfigs": False}
    URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/autotest/start/{}".format(test_name)
    print("Starting Autotest with {}...".format(URL))
    myresponse = requests.post(URL,json=autotest_push, timeout=REST_TIMEOUT)
    print (myresponse.json())

    #########Checking for test status
    URL = 'http://'+urlIP+':4000/api/v1/activeTest/get'
    TestIsRunning = True
    runningFor = 0
    while TestIsRunning:
        if runningFor >= timeout:
            TestIsRunning = False
            print("Assuming the end of the test at {} seconds.".format(runningFor))
        else:
            myresponse = requests.get(URL,json={}, timeout=REST_TIMEOUT)
            if myresponse.status_code != 200:
                print("Failed to get the active test information with {}".format(URL))
                runningFor += 1
                time.sleep(1)
            else:
                if test_name not in myresponse.text: # Test has run to end
                    TestIsRunning = False
                    print("Based on {}, test is no longer running at {} seconds.".format(URL,runningFor))
                else:
                    print("Test still running at {} seconds. (Will wait until {} seconds.)".format(runningFor,timeout))
                    runningFor += 1
                    time.sleep(1)


    jsonZipPath = "json_{}.zip".format(fois)
    print('>>> getAutotestResults jsonZipPath:', jsonZipPath)

    URL = "http://" + "{}:4000".format(urlIP) + "/api/v1/reports/json/{}".format(test_name)
    json_report = requests.get(URL,timeout=REST_TIMEOUT)
    with open(jsonZipPath, 'wb') as f:
        for chunk in json_report.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    print("Zipped file of all JSONs at: {} ".format(jsonZipPath))

