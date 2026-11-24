import os
import sys
import json
import requests
import time
import datetime
import math
from kafka import KafkaProducer
import numpy as np
import random

def main():
    ##############################################################################################################
    ###                                                                                                          #
    ###                                                                                                          #
    #                                                                                                            #
    #  The main script.  It pulls the statistics using whatever device-dependent mechanism is required, and      #
    #  then it puts that data into plots (if desired), and also into the databased (if desired.)                 #
    #                                                                                                            #
    ###                                                                                                          #
    ###                                                                                                          #
    ##############################################################################################################

    while True:

        global firstTime
        thisTimestamp = time.time()
        if firstTime==None: firstTime = thisTimestamp
        thisSecond = int(thisTimestamp - firstTime)

        getRealData = False

        if getRealData:
            calix_stats =  get_calix_stats()
            print("The Calix stats are {}".format(calix_stats))
            if "RSSI" in calix_stats: thisRSSI = calix_stats["RSSI"]
            else: thisRSSI = "#N/A"
            if "MAC" in calix_stats: thisMAC = calix_stats["MAC"]
            else: thisMAC = "#N/A"
            if "Channel" in calix_stats: thisChannel = calix_stats["Channel"]
            else: thisChannel = "#N/A"

        else:
            thisRSSI = random.randint(-40, -30)
            thisMAC = "AA.BB.CC.DD.EE.FF"
            thisChannel = 100

        if thisRSSI != "#N/A":
            rssiArray.append(thisRSSI)
            seconds.append(thisSecond)

        ##############################################################################################################
        ###                                                                                                          #
        ###                                                                                                          #
        #                                                                                                            #
        #  Creating a report structure to hold plots.                                                                #
        #                                                                                                            #
        ###                                                                                                          #
        ###                                                                                                          #
        ##############################################################################################################

        myReport = {}
        myReport["Title"] = "Custom Plots in Stardust"
        myReport["Report"] = []

        npArray = np.array(rssiArray)
        try:
            minVal = np.min(npArray)
            maxVal = np.max(npArray)
        except:
            sorted = []
            for val in rssiArray: sorted.append(val)
            sorted.sort()
            minVal = sorted[0]
            maxVal = sorted[len(sorted)-1]
        if minVal==maxVal:
            minVal -= 1
            maxVal += 1
        
        
        # Line plot
        thisData = [ {"label":"DUT RSSI Values","color":"blue","width":1,"radius":3,"data":rssiArray,"fill": False,"style": "solid"} ]
        item = {
            "elementType":"plot",
            "type": "line",
            "title": "External RSSI",
            "labels": seconds,
            "xaxis":{"string":"Array Index"},
            "yaxis":{"string":"RSSI (dBm)"},
            "showTable": True,
            "plotWidth": "500px",
            "datasets": thisData
        }
        myReport["Report"].append(item)

        randomPlot = random.randint(1,4)
        boolean = True
        
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

        barData = [{
            'label':'RSSI histogram',
            'color':'red',
            'width':1,
            'radius':0,
            'data':data,
            'fill': False,
            'style': 'solid'
        }]
        barItem =  {
            'elementType':'plot',
            'type': 'bar',
            'title': 'Histogram of RSSI',
            'labels': labels,
            'xaxis':{'string':'RSSI value (dBm)'},
            'yaxis':{'string':'Counts'},
            'datasets': barData
        }
        if randomPlot==3 or boolean:
            myReport["Report"].append(barItem)
                
        #CDF
        data = {"data":rssiArray, "dir":1}
        api_endpoint = ea_root + "createCdfFrom"
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        cdf = theJson["cdf"]
        data = []
        for x in cdf:
            data.append({"x":x["x"],"y":x["y"]})
        thisData=[{
            "label":"RSSI CDF",
            "color":"red",
            "width":1,
            "data":data,
            "fill":False,
            "radius":2
        }]
        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "CDF of RSSI values",
            "xaxis":{"string":"RSSI (dBm)"},
            "yaxis":{"string":"% of time < X axis"},
            "showTable": False,
            "plotWidth": "500px",
            "datasets": thisData
        }
        if randomPlot==4 or boolean:
            myReport["Report"].append(item)
            
        # Scatter plot
        data = []
        for i in range (0,len(rssiArray)):
            data.append({"x":seconds[i],"y":rssiArray[i]})
        scatterData = [
            {
                'label':'Scatter plot of RSSI data',
                'color':'black',
                'width':1,
                'data':data,
                'fill': False,
                'radius': 1
            }
        ]
        item = {
            'elementType':'plot',
            'type': 'scatter',
            'title': 'Scatter plot of RSSI data',
            'xaxis':{'string':'Time (sec)'},
            'yaxis':{'string':'RSSI (dBm)'},
            'datasets': scatterData
        }
        if randomPlot==2 or boolean:
            myReport["Report"].append(item)
        
        # Pie chart
        data = {"data":rssiArray, "bins":5, "minVal":minVal, "maxVal":maxVal}
        api_endpoint = ea_root + "createHistogramFrom"
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        histogram = theJson["histogram"]
        data = []
        labels = []
        for x in histogram:
            labels.append(str(round(x["binLabel"],2)))
            data.append(x["binCount"])

        plotData =   [{
            'label':'Data',
            'color':colors,
            'data':data
        }]
        plotItem = {
            'elementType':'plot',
            'type': 'pie',
            'title': 'Pie chart of RSSI values',
            'labels': labels,    
            'datasets': plotData
            
        }
        if randomPlot==1 or boolean:
            myReport["Report"].append(plotItem)

        ##############################################################################################################
        ###                                                                                                          #
        ###                                                                                                          #
        #                                                                                                            #
        #  Sending the updated plots to the plot window                                                              #
        #                                                                                                            #
        ###                                                                                                          #
        ###                                                                                                          #
        ##############################################################################################################
        # Sending the data to plot kafka topic
        my_producer.send('EXTERNAL_PLOT_STREAM', value = myReport)

        ##############################################################################################################
        ###                                                                                                          #
        ###                                                                                                          #
        #                                                                                                            #
        #  Placing data into the database                                                                            #
        #                                                                                                            #
        ###                                                                                                          #
        ###                                                                                                          #
        ##############################################################################################################
        # Data to be saved to database
        try:
            timestamp = time.time() # current timestamp
            #Model the timestamp for the data collection being "off"
            timestamp -= 55
            # Json structure for sending data
            my_data = {"timestamp":timestamp, "MAC":thisMAC, "RSSI":thisRSSI, "testName": testName}
            print("Writing this data to the database:\n{}".format(my_data))
            # Sending the data to database kafka topic
            #print("Sending {} to the database".format(my_data))
            my_producer.send('EXTERNAL_DATA_STREAM', value = my_data)
        except:
            print("The Kafka broker doesn't seem to be responding.")
            break

        time.sleep(1)  #wait time before pulling and storing the data again

##################################################################################
    
def get_calix_stats():

    ##############################################################################################################
    ###                                                                                                          #
    ###                                                                                                          #
    #                                                                                                            #
    #  This is the device-specific interaction to get statistics.  Here we show a mechanism used on a specific   #
    #  AP.  Other devices will have other mechanisms.  The mechanisms themselves are outside the scope of        #
    #  the octoBox.  The model here is (1) extract proprietary data, (2) put it on the octobox interface,        #
    #  (3) see that data either as plot or in the test record, or both.                                          #
    #                                                                                                            #
    ###                                                                                                          #
    ###                                                                                                          #
    ##############################################################################################################

    '''
    urlIP = "10.100.103.89" #paramsDict["oBox_server"]["val"]["publicip"]
    serverServer =  "http://" + urlIP + ":8383/"
    serverExec   =  "http://" + urlIP + ":8383/exec?command="
    serverSpawn  =  "http://" + urlIP + ":8383/spawn?command="
    REST_TIMEOUT = 150
    
    command = "python3 /home/octoscope/Desktop/Calix-Firmware/ssh-to-calix.py"
    url = serverExec+command
    print("\n>>> Getting the AP information with command {}".format(url))
    resp = requests.get(url=url, timeout=REST_TIMEOUT)
    jsn = json.loads(resp.text)
    print('>>> Pulling information from the AP, with result: ', jsn)
    text = jsn["stdout"]
    '''
    
    timestamp = time.time()
    text = ssh_to_calix()
    list = text.split(";")
    
    dataSet = []
    for item in list:
        parts = item.split(",")
        dataItem = {}
        for piece in parts:
            segments = piece.split("=")
            if segments[0] == "MAC": dataItem["MAC"] = segments[1]
            if segments[0] == "CHAN": dataItem["CHAN"] = int(segments[1])
            if segments[0] == "RSSI": dataItem["RSSI"] = int(segments[1])
        if "MAC" in dataItem and "CHAN" in dataItem and "RSSI" in dataItem: dataSet.append(dataItem)
    #print(dataSet)
        
    if len(dataSet) > 0:
        linearSum = 0
        for item in dataSet:
            rssi = item["RSSI"]
            lrssi = 10 ** (rssi/10)
            linearSum += lrssi
        linearAve = linearSum / len(dataSet)
        dBAve = 10*math.log10(linearAve)
        retObj = {"timestamp":timestamp, "MAC":dataSet[0]["MAC"],"Channel":dataSet[0]["CHAN"], "RSSI":dBAve}                  
    else:
        dBAve = "#N/A"
        retObj = {"timestamp":timestamp, "MAC":None,"Channel":None, "RSSI":dBAve}                  
            
    #print("Average signal level of {} dBm".format(dBAve))
    return retObj

################################################################################################

def ssh_to_calix():

    import sys
    import paramiko

    theReturn = ""

    client = paramiko.SSHClient()
    #client.load_system_host_keys()
    #client.load_host_keys('~/.ssh/known_hosts')
    #client.set_missing_host_key_policy(AutoAddPolicy())
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    #client.connect('192.168.15.1', port=30007, username='support', password='Support!Support1')
    client.connect('192.168.0.1', port=30007, username='support', password='Support!Support1')

    # Run a command
    theCommand = 'wlanconfig ath0 list -h'
    stdin, stdout, stderr = client.exec_command(theCommand.encode('utf-8'))
    #stdin.close()

    output = stdout.readlines()
    #print (output)
    #print (len(output))
    for item in output:
        #print (item)
        #item = item.replace(" ",":")
        if "RSSI" in item:
            item = item.replace(" ",":")
            while "::" in item: item = item.replace("::",":")
            #print (item)
            split = item.split(":")
            #print (split)
            address = None
            channel = None
            rssi = None
            for i in range(0,len(split)):
                #print("'{}'".format(split[i]))
                if split[i].strip() == "ADDR":
                    address = ""
                    for j in range(i+1,i+6): address += split[j].strip() + ":"
                    #address += split[i+6].strip()
                    #print("address {}".format(address))
                if split[i].strip() == "CHAN":
                    channel = int(split[i+1])
                    #print("channel {}".format(channel))
                if split[i].strip() == "RSSI":
                    rssi = int(split[i+1])
                    #print("rssi {}".format(rssi))
            print("radio=ATH0,MAC={},CHAN={},RSSI={};".format(address,channel,rssi))
            theReturn += "radio=ATH0,MAC={},CHAN={},RSSI={};".format(address,channel,rssi)
    #print(type(stdin))  # <class 'paramiko.channel.ChannelStdinFile'>
    #print(type(stdout))  # <class 'paramiko.channel.ChannelFile'>
    #print(type(stderr))  # <class 'paramiko.channel.ChannelStderrFile'>
    #print (output.decode('ascii'))
    #output = stderr.read()
    #print (output.decode('ascii'))

    # Run a command
    theCommand = 'wlanconfig ath1 list -h'
    stdin, stdout, stderr = client.exec_command(theCommand.encode('utf-8'))

    output = stdout.readlines()
    for item in output:
        if "RSSI" in item:
            item = item.replace(" ",":")
            while "::" in item: item = item.replace("::",":")
            split = item.split(":")
            address = None
            channel = None
            rssi = None
            for i in range(0,len(split)):
                if split[i].strip() == "ADDR":
                    address = ""
                    for j in range(i+1,i+6): address += split[j].strip() + ":"
                if split[i].strip() == "CHAN":
                    channel = int(split[i+1])
                if split[i].strip() == "RSSI":
                    rssi = int(split[i+1])
            print("radio=ATH1,MAC={},CHAN={},RSSI={};".format(address,channel,rssi))
            theReturn += "radio=ATH1,MAC={},CHAN={},RSSI={};".format(address,channel,rssi)

    # Run a command
    theCommand = 'wlanconfig ath2 list -h'
    stdin, stdout, stderr = client.exec_command(theCommand.encode('utf-8'))

    output = stdout.readlines()
    for item in output:
        if "RSSI" in item:
            item = item.replace(" ",":")
            while "::" in item: item = item.replace("::",":")
            split = item.split(":")
            address = None
            channel = None
            rssi = None
            for i in range(0,len(split)):
                if split[i].strip() == "ADDR":
                    address = ""
                    for j in range(i+1,i+6): address += split[j].strip() + ":"
                if split[i].strip() == "CHAN":
                    channel = int(split[i+1])
                if split[i].strip() == "RSSI":
                    rssi = int(split[i+1])
            print("radio=ATH2,MAC={},CHAN={},RSSI={};".format(address,channel,rssi))
            theReturn += "radio=ATH2,MAC={},CHAN={},RSSI={};".format(address,channel,rssi)


    client.close()
    return theReturn

################################################################################################
################################################################################################
################################################################################################
################################################################################################

#Get the test name
testName = sys.argv[1]
print(testName)

# Connect to kafka
my_producer = KafkaProducer(  
    bootstrap_servers = ['localhost:9092'],
    value_serializer = lambda x:json.dumps(x).encode('utf-8')  
)

#Define some thing necessary for this specific test.
colors = ["#000000", "#FFFF00", "#1CE6FF", "#FF34FF", "#FF4A46"]
rssiArray = []
seconds = []
firstTime = None

#Use EA for some plotting purposes.  Not required, of course.  This would require EA to be running ON THE SERVER.
#(Remember, this script ill be moved to the server, and executed there!)
ea_root = "http://10.160.81.80:8080/"

main()          #Data extraction.  In this case, this runs in a continual loop once started.  It needs to be explicitly stopped by the test script.
