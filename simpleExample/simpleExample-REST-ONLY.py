'''
Test Description
================
Describe API concept
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

sys.path.append('../')   #Location of stardust_socket_listen.py
from stardust_socket_listen import StardustSocketListen

############### END SECTION: IMPORTS #########################

REST_TIMEOUT = 120 # Used by REST API calls
print('\n>>> REST_TIMEOUT: ', REST_TIMEOUT)

def validateMe(autotest_dict):
    #get the testbed components
    api_endpoint = "http://{}:4000/api/v1/testbedComponents".format(serverIP)
    print(api_endpoint)
    theResponse = requests.get(url=api_endpoint)
    theJson = json.loads(theResponse.text)

    tbPal6s = []
    tbPal7s = []
    for item in theJson:
        if item["devType"] == "pal6": tbPal6s.append(item)
        if item["devType"] == "pal7": tbPal7s.append(item)
    print("These are the Pal6s in the testbed, according to the configuration: \n{}".format(tbPal6s))
    print("\n\nThese are the Pal7s in the testbed, according to the configuration: \n{}".format(tbPal7s))

    pal6s = []
    if "pal6s" in autotest_dict:
        pal6s = autotest_dict["pal6s"]
    print("\n\nThese are the Pal6s in the configuration: \n{}".format(pal6s))
        
    pal7s = []
    if "pal7s" in autotest_dict:
        pal7s = autotest_dict["pal7s"]
    print("\n\nThese are the Pal7s in the configuration: \n{}".format(pal7s))

    tps = []
    if "trafficPairs" in autotest_dict:
        tps = autotest_dict["trafficPairs"]
    print("\n\nThese are the traffic pairs in the configuration: \n{}".format(tps))

    goodPal6s = []
    goodPal7s = []
    goodTps = tps

    for pal in pal6s:
        isPal7 = False
        for item in tbPal7s:
            if pal["managementAddr"] == item["address"]:
                print("The thing at {}, which you say is a Pal6, is really a Pal7.  So, fixing that.".format(pal["managementAddr"]))
                isPal7 = True
        if isPal7:
            if pal["palRadio"] == "RADIO_5": pal["palRadio"] = "RADIO_5A"
            goodPal7s.append(pal)
            for tp in tps:
                if tp["from"]["managementAddress"] == pal["managementAddr"]:
                    tp["from"]["devType"] = "pal7"
                    if tp["from"]["radio"] == "RADIO_5": tp["from"]["radio"] = "RADIO_5A" 
                if tp["to"]["managementAddress"] == pal["managementAddr"]:
                    tp["to"]["devType"] = "pal7"
                    if tp["to"]["radio"] == "RADIO_5": tp["to"]["radio"] = "RADIO_5A" 
        else:
            goodPal6s.append(pal)
            
    for pal in pal7s:
        isPal6 = False
        for item in tbPal6s:
            if pal["managementAddr"] == item["address"]:
                print("The thing at {}, which you say is a Pal7, is really a Pal6.  So, fixing that.".format(pal["managementAddr"]))
                isPal6 = True
        if isPal6:
            if pal["palRadio"] == "RADIO_5A" or pal["palRadio"] == "RADIO_5B": pal["palRadio"] = "RADIO_5"
            goodPal6s.append(pal)
            for tp in tps:
                if tp["from"]["managementAddress"] == pal["managementAddr"]: tp["from"]["devType"] = "pal6"
                if tp["to"]["managementAddress"] == pal["managementAddr"]: tp["to"]["devType"] = "pal6"
        else:
            goodPal7s.append(pal)

    print("\nThese are the actual Pal6s in the configuration: \n{}".format(goodPal6s))
    print("\nThese are the actual Pal7s in the configuration: \n{}".format(goodPal7s))
    print("\nThese are the actual traffic pairs in the configuration: \n{}".format(tps))
    autotest_dict["pal6s"] = goodPal6s
    autotest_dict["pal7s"] = goodPal7s
    autotest_dict["trafficPairs"] = tps
    
    return autotest_dict


def callback_status(data):
    print(data)
    if data:
        print("Here is the data in getPalStatus:\n{}".format(data))

    return


usePal6Stack = True
validateConfiguration = True

if usePal6Stack:
    #Pal6 stack
    serverIP = "10.100.103.89"
    ssid = "Calix_AP"
    password = "octoscope"
    security = "SECURITY_WPA2"
    mgmt = "172.16.27.3"

else:
    #Pal7 stack
    serverIP = "10.25.203.110"
    ssid = "DUT"
    password = "11111111@@"
    security = "SECURITY_WPA3"
    mgmt = "172.16.27.17"

autotest_dict = {'description': 'simpleExample Test\n Simple test to set up one traffic pair and one sniffer and run traffic while doing packet capture.\n Illustrates all the basic functions of setting up results file folder and names, setting attenuators, settting up traffic pairs, setting up and associating STA and setting up, starting and stopping sniffing.\n Assumes DUT in Box A. Sniffer and STA STApals in Box C', 'model': 'calix', 'name': 'simpleAutomationExample', 'revision': 'calix', 'rvrMode': 'RvR', 'synchroSnifferCapturing': False, 'trainingInterval': 5, 'stepDuration': 10, 'step': 10, 'wiresharkHost': '', 'trafficPairEndpointAddresses': [], 'version': 2, 'creationVersion': '2.5.0-8', 'quadAttens': [], 'virtualAttens': [], 'mpes': [{'devName': 'MPE2-A', 'address': '172.16.23.1', 'active': True, 'dB': 0, 'start': 0, 'stop': 10, 'mpeBypassValue': 63, 'devType': 'MPE', 'dbMax': 63, 'firmwareCreationVersion': '3.2.22', 'serialCreationVersion': 'MPE-00408-11', '_id': '65d91d4e9cd913d96ef80e19'}, {'devName': 'MPE2-B', 'address': '172.16.23.2', 'active': True, 'dB': 0, 'start': 0, 'stop': 10, 'mpeBypassValue': 63, 'devType': 'MPE', 'dbMax': 63, 'firmwareCreationVersion': '3.2.22', 'serialCreationVersion': 'MPE-00130-01', '_id': '65d91d4e9cd913d96ef80e1a'}], 'virtualMpes': [], 'pal6s': [{'advRatesEnable': False, 'alias': 'P6C_5', 'apStaMode': 'STA', 'bandConfig': 'BAND_DUAL', 'bandwidth': 'BANDWIDTH_ADAPT', 'beaconInterval': 100, 'beamformeeMUEnable': True, 'beamformeeSUEnable': True, 'beamformerMUEnable': False, 'beamformerSUEnable': False, 'bridgeEnable': False, 'bssid': '', 'bssidMode': 'BSSID_DISABLED', 'channelScanList': [], 'firmwareCreationVersion': '20230623-103147-pal6-v11.4.3.0', 'guardInterval': 'GUARD_0_8US', 'interface_': 'INTERFACE_AX', 'ipAddress': '192.168.60.135', 'ipGateway': '192.168.0.1', 'ipMode': 'IP_STATIC', 'ipv6Mode': 'IP_STATIC', 'ipNetmask': '255.255.0.0', 'managementAddr': mgmt, 'ofdmaDLEnable': True, 'ofdmaULEnable': True, 'palRadio': 'RADIO_5', 'password': password, 'primaryChannel': 36, 'priority': 'PRIORITY_BESTEFFORT', 'radioEnabled': True, 'rate': -1, 'replayAdvanced': False, 'roamTargetThreshold': -95, 'roamThreshold': -95, 'secondaryChannel_8080': 0, 'security': security, 'ssid': ssid, 'streams': 2, 'txAtten': 0, 'uApsdEnable': True, 'vEnable': False, 'vLogging': False, 'vstaConfig': [], 'vstaCount': 1, '_id': '65d91d4e9cd913d96ef80e1b'}], 'staPals': [], 'synchroSniffers': [], 'snifferDisplay': [], 'trafficPairs': [{'to': {'alias': 'P6C_5', 'managementAddress': mgmt, 'trafficAddress': '192.168.60.135', 'devType': 'pal6', 'radio': 'RADIO_5', 'linkMonitor': True}, 'from': {'alias': 'Server', 'managementAddress': '172.16.22.4', 'trafficAddress': '192.168.15.4', 'devType': 'server', 'radio': '', 'linkMonitor': True}, 'testDuration': 30, 'settlingTime': 2, 'active': True, 'alias': 'ServerToP6C_5', 'binCount': '1000', 'binWidth': '500', 'bitrate': '0M', 'histogram': False, 'interval': 200, 'length': '', 'name': '__ServerToP6C_5__(0.5790277801803843)', 'trafficType': 'iperf3', 'udp': 'tcp', 'ipVersion': 'ipv4', 'ipStreams': 4, 'window': '4M', '_id': '65d91d4e9cd913d96ef80e1c'}], 'turntables': []}


print("\n\n TEST CONFIGURATION IS CREATED")
#print(json.dumps(autotest_dict,indent=3))
testName = autotest_dict["name"]

print("\n\n DELETING THE TEST CASE")
api_endpoint = "http://{}:4000/api/v1/testConfigs/{}".format(serverIP,testName)
theResponse = requests.delete(url=api_endpoint)
theJson = json.loads(theResponse.text)
print(theJson)

if validateConfiguration:
    autotest_dict = validateMe(autotest_dict)
    print("\n After validation, the autotest dictionary is this: {}".format(autotest_dict))

print("\n\n CREATING THE TEST CASE")
api_endpoint = "http://{}:4000/api/v1/testConfigs".format(serverIP)
theResponse = requests.post(url=api_endpoint,json=autotest_dict)
theJson = json.loads(theResponse.text)
print(theJson)    

print("\n\n INITIALIZING THE TEST CASE")
api_endpoint = "http://{}:4000/api/v1/testConfigs/initialize/{}".format(serverIP,testName)
theResponse = requests.post(url=api_endpoint,json=autotest_dict)
theJson = json.loads(theResponse.text)
print(theJson)

print("\n\n CHECKING THE STATUS OF THE PAL")
SERVER_ADDR = serverIP
NAMESPACE = 'PAL_STATUS'
EVENT_NAME = mgmt
#EVENT_NAME = 'ALL'

COUNT = 0
associatedStatus = False

# The callback is optional, otherwise will just print
# all messages to console
def callback(data):
    print("Printing the data from the callback:\n{}".format(data))
    """ Example optional custom callback """
    if data['id']['radio'] == 'RADIO_5':
        print(data)
        global COUNT # pylint: disable=global-statement
        COUNT += 1
        global associatedStatus
        if data['radioState'] == 'Associated': associatedStatus = True
        print('-==-'*20)

# See recognized namespaces
print("NAMESPACES:")
print('\n', StardustSocketListen.get_namespaces(), '\n')
# See events table
print("EVENTS TABLE:")
print('\n', StardustSocketListen.get_events(), '\n')

print("THIS SOCKET:")
print("SERVER_ADDR = {}, NAMESPACE: {}, EVENT_NAME = {}".format(SERVER_ADDR,NAMESPACE,EVENT_NAME))

print('---> Creating...')
STATUS = StardustSocketListen(
    SERVER_ADDR, # required
    NAMESPACE, # required
    EVENT_NAME, # required
    callback=callback # optional
)
print('<-- Created')
print('Is connected:', STATUS.is_connected, '\n') # False

print('---> Starting...')
STATUS.start()
print('<-- Started')
print('Is connected:', STATUS.is_connected, '\n') # True

print('\n---> Stopping...')
STATUS.stop()
print('<-- Stopped')
print('Is connected:', STATUS.is_connected, '\n') # False

while not associatedStatus:
    STATUS.start()
    time.sleep(1)
    STATUS.stop()


print('Count:', COUNT)

'''
STATUS = StardustSocketListen(
    SERVER_ADDR, 
    NAMESPACE, 
    EVENT_NAME, 
    callback=callback_status
)

for i in range (0,10):
    STATUS.start()
    time.sleep(1)
    STATUS.stop()
'''
    
print("\n\n RUNNING THE TEST CASE")
api_endpoint = "http://{}:4000/api/v1/autotest/start/{}".format(serverIP,testName)
theResponse = requests.post(url=api_endpoint,json={"pushConfigs":False})
theJson = json.loads(theResponse.text)
print(theJson)
