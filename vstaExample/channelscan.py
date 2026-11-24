#!/usr/bin/python3

""" Base code by David Mozzoni """

import time
import sys
import os
import pprint

pp = pprint.PrettyPrinter(indent=4)

# Find working directory
try:
    directory_name=sys.argv[1]
    #print('>>> foo: The directory name passed in is {}.'.format(directory_name),flush=True)
except:
    #print('>>> foo: No directory_name provided, so using ./',flush=True)
    directory_name = './'
sys.path.append(directory_name + '../')

#import globalsfile
#import sd2Utils
from stardust_socket_listen import StardustSocketListen

# Get params and base auto test dictionaries 
#paramsDict = globalsfile.paramsDict
#autotest_dict = globalsfile.autotest_dict

class objectview(object):
  def __init__(self, d):
    self.__dict__ = d

SERVER_ADDR = '10.100.103.183' 	# Stardust server IP 
NAMESPACE = 'PAL_STATUS'
EVENT_NAME = '172.16.27.3'		# Pal IP address
COUNT = 0
myglobals = objectview({'scanValue': []})

# The callback is optional, otherwise will just print all messages to console
def callback(data):
  """ Example optional custom callback """
  global myglobals 
  global COUNT 
  if data:
    #print(data)
    COUNT += 1
    myglobals.scanValue.append(data)

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

sleepTime = 1
runningFor = 0
timeout = 100

while runningFor <= timeout:
	while len(myglobals.scanValue):
		val = myglobals.scanValue.pop(0)
		if val:
			print("\n##############################################################")
			print (">>> scanResult %s: myglobals.scanValue:" % (runningFor))
			pp.pprint(val)
		time.sleep(sleepTime)
		runningFor += sleepTime


print('\n---> Stopping...')
STATUS.stop()
print('<-- Stopped')
print('Is connected:', STATUS.is_connected, '\n') # False

print('Count:', COUNT)
