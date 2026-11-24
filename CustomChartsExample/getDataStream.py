import time
import sys
from stardust_socket.listen import StardustSocketListen
import json
import math
import requests
from kafka import KafkaProducer
import numpy as np

SERVER_ADDR = '127.0.0.1' # Stardust server
#NAMESPACE = 'PAL_STATUS'
#EVENT_NAME = '172.16.27.1'
NAMESPACE = 'PAL_TELEMETRY'
EVENT_NAME = 'ALL'

def definePlots():

    global rssiArray
    minVal = 0
    maxVal = 0
    if minVal==maxVal:
        minVal -= 1
        maxVal += 1
        
    #RSSI histogram
    #Bar Chart
    data = {"data":rssiArray, "bins":10, "minVal":minVal, "maxVal":maxVal}
    api_endpoint = ea_root + "createHistogramFrom"
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    histogram = theJson["histogram"]
    data = []
    labels = []
    for x in histogram:
        labels.append(str(round(x["binLabel"],2)))
        data.append(x["binCount"])

    barData=[{'label':'RSSIhistogram','color':'red','width':1,'radius':0,'data':data,'fill':False,'style':'solid'}]
    barItem =  {
        'elementType':'plot',
        'type': 'bar',
        'title': 'Histogram of RSSI',
        'labels': labels,
        'xaxis':{'string':'RSSI value (dBm)'},
        'yaxis':{'string':'Counts'},
        'datasets': barData
    }
    myReport["Report"].append(barItem)    

def use(data):
    global rssiArray
    #print(data)
    theRSSIs = data['rssiDataChains']
    sum = 0
    for rssi in theRSSIs:
        linear = 10**(rssi['mean']/10)
        sum += linear
    dB = 10*math.log(sum,10)
    #print(theRSSIs,dB)
    rssiArray.append(dB)

    npArray = np.array(rssiArray)
    minVal = np.min(npArray)
    maxVal = np.max(npArray)
    data = {"data":rssiArray, "bins":10, "minVal":minVal, "maxVal":maxVal}
    api_endpoint = ea_root + "createHistogramFrom"
    theResponse = requests.post(url=api_endpoint, data=data)
    theJson = json.loads(theResponse.text)
    histogram = theJson["histogram"]
    data = []
    labels = []
    for x in histogram:
        labels.append(str(round(x["binLabel"],2)))
        data.append(x["binCount"])

    barData = [{
        'label':'RSSI histogram',
        'color':'red',
        'width':1,
        'radius':0,
        'data':data,
        'fill': False,
        'style': 'solid'
    }]
    myReport["Report"][0]["datasets"] = barData
    myReport["Report"][0]["labels"] = labels

    # Send the data to plot kafka topic
    print("Sending {} to kafka".format(myReport))
    my_producer.send('EXTERNAL_PLOT_STREAM', value = myReport)
            
def callback(data):
  """ Example optional custom callback """
  #print(data)
  use(data)
  #print('-==-'*20)

###################################################################
###################################################################
###################################################################

# Connect to kafka
my_producer = KafkaProducer(  
    bootstrap_servers = ['localhost:9092'],
    value_serializer = lambda x:json.dumps(x).encode('utf-8')  
)

ea_root = "http://10.100.103.89:8080/"
rssiArray=[]
myReport = {}
myReport["Title"] = "Example Report"
myReport["Report"] = []

definePlots()
  
print('---> Creating...')
STATUS = StardustSocketListen(
  SERVER_ADDR, # required
  NAMESPACE, # required
  EVENT_NAME, # required
  callback=callback # optional
)
print('<-- Created')
print('Is connected:', STATUS.is_connected, '\n') # False

while True:

    print('---> Starting...')
    STATUS.start()
    print('<-- Started')
    print('Is connected:', STATUS.is_connected, '\n') # True

    time.sleep(1)

    print('\n---> Stopping...')
    STATUS.stop()
    print('<-- Stopped')
    print('Is connected:', STATUS.is_connected, '\n') # False
    
