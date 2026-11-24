import sys
import json
import os
import requests
import base64
from pathlib import Path
#import boto3
from datetime import datetime

#######################################################################
def info(text,another=None):
    now = datetime.now()
    if(another==None):
        print("[INFO]: " +"{"+str(now)+"}; "+ text)
    else:
        print("[INFO]: " +"{"+str(now)+"}; "+ text + " , " + str(another))

#######################################################################
def main(directory_name,json_dir,ea_root):

    # Set up some text coloring
    cRed=   '\033[33m'
    cGreen= '\033[32m'
    cNormal='\033[m'

    colors = [
        "#000000", "#FFFF00", "#1CE6FF", "#FF34FF", "#FF4A46", "#008941", "#006FA6", "#A30059",
        "#FFDBE5", "#7A4900", "#0000A6", "#63FFAC", "#B79762", "#004D43", "#8FB0FF", "#997D87",
        "#5A0007", "#809693", "#FEFFE6", "#1B4400", "#4FC601", "#3B5DFF", "#4A3B53", "#FF2F80",
        "#61615A", "#BA0900", "#6B7900", "#00C2A0", "#FFAA92", "#FF90C9", "#B903AA", "#D16100",
        "#DDEFFF", "#000035", "#7B4F4B", "#A1C299", "#300018", "#0AA6D8", "#013349", "#00846F",
        "#372101", "#FFB500", "#C2FFED", "#A079BF", "#CC0744", "#C0B9B2", "#C2FF99", "#001E09",
        "#00489C", "#6F0062", "#0CBD66", "#EEC3FF", "#456D75", "#B77B68", "#7A87A1", "#788D66",
        "#885578", "#FAD09F", "#FF8A9A", "#D157A0", "#BEC459", "#456648", "#0086ED", "#886F4C",
        "#34362D", "#B4A8BD", "#00A6AA", "#452C2C", "#636375", "#A3C8C9", "#FF913F", "#938A81",
        "#575329", "#00FECF", "#B05B6F", "#8CD0FF", "#3B9700", "#04F757", "#C8A1A1", "#1E6E00",
        "#7900D7", "#A77500", "#6367A9", "#A05837", "#6B002C", "#772600", "#D790FF", "#9B9700",
        "#549E79", "#FFF69F", "#201625", "#72418F", "#BC23FF", "#99ADC0", "#3A2465", "#922329",
        "#5B4534", "#FDE8DC", "#404E55", "#0089A3", "#CB7E98", "#A4E804", "#324E72", "#6A3A4C"
    ]

    #Grab the directory information as created by SM.
    if directory_name[len(directory_name)-1] != "/": directory_name += "/"
    dirFile = directory_name + "directories.json"

    try:
        f = open(dirFile)
        directoriesJson = json.load(f)
        subDir = directoriesJson["subDirectory"]
        splits = subDir.split("_")
        CL = ""
        for i in range(2,len(splits)):CL += splits[i] + "_"
        CL = CL[0:len(CL)-1]
        theTitle = directoriesJson["title"]
        theName = theTitle.replace(" ","_")
    except:
        CL = ""
        theTitle = "multiPair_EA"
        theName = theTitle.replace(" ","_")

    #print("Command line part is " + CL)

    if directory_name[len(directory_name)-1] != "/": directory_name += "/"
    if json_dir[len(json_dir)-1] != "/": json_dir += "/"
    info('>>> createReport_main json_dir', json_dir)
    #Get all of the zip files in the json directory
    theZips = []
    for x in os.listdir(json_dir):
        if ".zip" in x:
            #info(x)
            if "CSV" not in x: theZips.append(json_dir + x)
            '''
            theURL = upload_file_to_s3_using_file_object(directory_name,json_dir + x)
            info("Zip file uploaded to S3 at: " + theURL)
            theLink = "Zip file " + x + " on S3"
            print("ArtifactLink:Description:\"" + theLink + "\",Link:",theURL)
            '''

    #info(theZips)

    #theTitle = "Simple Automation Example"
    #if len(CL) > 0: theTitle += " (" + CL + ")"        

    #Write a report
    myReport = {}
    myReport["Title"] = theTitle
    myReport["Report"] = []

    item = {
        "elementType": "section",
        "headingType": "h1",
        "headingContent": theTitle
    }
    myReport["Report"].append(item)

    item = {
        "elementType": "section",
        "headingType": "h2",
        "headingContent":"Overview",
        "text": "In this test run traffic between the device under test (DUT) and a Pal6 used as a station (STA)."
    }
    myReport["Report"].append(item)

    #Do the whole analysis part using the data in this zip file.
    #fileName = theZips[0]
    for fileName in theZips:
        info('>>> createReport_main Using file %s.', fileName)
        parts = fileName.split("/")
        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"File: " + parts[len(parts)-1]
        }
        myReport["Report"].append(item)
        
        with open(fileName, "rb") as f:
            bytes = f.read()
            encoded = base64.b64encode(bytes)
            #info(encoded)
            #api_endpoint = "http://localhost:8080/zip2csv"
            api_endpoint = ea_root + "zip2csv"
            data = {'zip':encoded}
            theResponse = requests.post(url=api_endpoint, data=data)
            theJson = json.loads(theResponse.text)
            #info(theJson)

        f = open(directory_name+'csv.csv', 'w')
        f.write(theJson["csv"])
        f.close()

        # Analyze the CSV file
        csv_path = directory_name+'csv.csv'
        csv = Path(csv_path).read_text()
        #location = "local"
        api_endpoint = ea_root + "objectify"
        data = {'csv':csv}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)

        headers = theJson["headers"]
        dataSet = theJson["dataSet"]
        if "error" in theJson: info("objectify: This data returned an error: {}".format(theJson["error"]))

        api_endpoint = ea_root + "crunch"
        run = 1
        data = {'headers':headers, 'dataSet':json.dumps(dataSet), 'run':run}
        theResponse = requests.post(url=api_endpoint, data=data)
        theJson = json.loads(theResponse.text)
        if "error" in theJson: info("crunch: This data returned an error: {}".format(theJson["error"]))
        analyzedData = theJson["crunchedData"]
        theNotes = theJson["Notes"]
        #info(theNotes)
        #info(json.dumps(analyzedData,indent=4))

        #info("The number of pal Endpoints for which you have data is {}".format(len(analyzedData)))

        numberOfPalEndpoints = len(analyzedData)
        if numberOfPalEndpoints == 0:
            info("No pal Endpoints found")
            sys.exit(24)
        else:
            thisData = analyzedData[0]
            numTraffic = thisData[0]["tpaircount"]
            _analyzedData = thisData            

        #Get basic test results information
        #api_endpoint = "http://localhost:8080/getStats"
        api_endpoint = ea_root + "getStats"
        data = {
            'csv':csv,
            'filter':'counts'
        }

        try:
            r = requests.post(url=api_endpoint, data=data, timeout=5)
        except requests.exceptions.RequestException as error:
            info("Error: ", error)
            sys.exit(44)
            
        y = json.loads(r.text)
        #info(json.dumps(y,indent=4))
        trafficPairs = y["filteredData"]["trafficPairs"]["map"]
        palEndpoints = y["filteredData"]["palEndpoints"]["map"]
        pingPairs = y["filteredData"]["pingPairs"]["map"]
        print("Traffic pairs: {}".format(trafficPairs))
        print("Ping pairs: {}".format(pingPairs))
        print("Pal endpoints: {}".format(palEndpoints))
        
        tpName = y["filteredData"]["trafficPairs"]["map"]["0"]
        #info(tpName)
        if y["filteredData"]["pingPairs"]["length"] > 0:
            ppName = y["filteredData"]["pingPairs"]["map"]["0"]
            #info(ppName)
        
        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Throughput vs Attenuation",
            "text": "Throughput vs. attenuation, where each attenuation step is the throughput averaged over the duration time."
        }
        myReport["Report"].append(item)

        rvrPlot = []
        for data in _analyzedData:
            try:thisAttenuation = data["attenuation"]
            except:continue
            try:thisThroughput = data["throughput"]["mean"]
            except:continue
            try:rvrPlot.append({"x":thisAttenuation,"y":round(thisThroughput,2)})
            except: rvrPlot.append({"x":thisAttenuation,"y":round(0,2)})

        rvrPlots = []
        rvrPlots.append(
	    {
	        "label":"Throughput",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": rvrPlot,
	        "fill": -1,
	        "style": "solid"
	    }
        )
        
        for pair in trafficPairs:
            index = int(pair)
            thisPlot = []
            for data in _analyzedData:
                try:thisAttenuation = data["attenuation"]
                except:continue
                try:thisThroughput = data["tpairData"][index]["throughput"]["mean"]
                except:continue
                try:thisPlot.append({"x":thisAttenuation,"y":round(thisThroughput,2)})
                except: thisPlot.append({"x":thisAttenuation,"y":round(0,2)})
            thisData = {
                "label": "Throughput for " + trafficPairs[pair],
                "color": colors[index % len(colors)],
                "width": 1,
                "radius": 0,
                "data": thisPlot,
                "fill": -1,
                "style": "solid"
            }
            rvrPlots.append(thisData)                                        

        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "Rate vs. Attenuation plot",
            "xaxis":{"string":"Attenuation (dB)"},
            "yaxis":{"string":"Throughput (Mbps)"},
            "showTable": True,
            "plotWidth":"800px",
            "data": rvrPlots
        }
        myReport["Report"].append(item)

        #iperf2 data if you have any
        iHaveIperf2 = False
        iperf2Plot = []
        for data in _analyzedData:
            try:thisAttenuation = data["attenuation"]
            except:continue
            try:thisLatency = data["iPerf2Latency"]["Mean"]["mean"]
            except:continue
            try:
                iperf2Plot.append({"x":thisAttenuation,"y":round(thisLatency,2)})
                iHaveIperf2=True
            except: iperf2Plot.append({"x":thisAttenuation,"y":round(0,2)})

        iperf2Plots = []
        iperf2Plots.append(
	    {
	        "label":"Latency",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": iperf2Plot,
	        "fill": -1,
	        "style": "solid"
	    }
        )
        if iHaveIperf2:
            for pair in trafficPairs:
                index = int(pair)
                thisPlot = []
                for data in _analyzedData:
                    try:thisAttenuation = data["attenuation"]
                    except:continue
                    try:thisLatency = data["tpairData"][index]["iPerf2Latency"]["Mean"]["mean"]
                    except:continue
                    try:thisPlot.append({"x":thisAttenuation,"y":round(thisLatency,2)})
                    except: thisPlot.append({"x":thisAttenuation,"y":round(0,2)})
                thisData = {
                    "label": "Latency for " + trafficPairs[pair],
                    "color": colors[index % len(colors)],
                    "width": 1,
                    "radius": 0,
                    "data": thisPlot,
                    "fill": -1,
                    "style": "solid"
                }
                iperf2Plots.append(thisData)                                        
                    
            item = {
                "elementType": "section",
                "headingType": "h3",
                "headingContent":"iPerf2 Latency vs Attenuation",
                "text": "Iperf2 latency vs. attenuation, where each attenuation step is the iperf2 Mean latency averaged over the duration time."
            }
            myReport["Report"].append(item)
            
            item = {
                "elementType":"plot",
                "type": "scatter",
                "title": "iPerf2 Latency vs. Attenuation plot",
                "xaxis":{"string":"Attenuation (dB)"},
                "yaxis":{"string":"iPerf2 Mean Latency (msec)"},
                "showTable": True,
                "plotWidth":"800px",
                "data": iperf2Plots
            }
            myReport["Report"].append(item)
        

        #Ping data, if you've got any.
        iHavePing = False
        pingPlot = []
        for data in _analyzedData:
            try:thisAttenuation = data["attenuation"]
            except:continue
            try:thisLatency = data["pingLatency"]["mean"]
            except:continue
            try:
                pingPlot.append({"x":thisAttenuation,"y":round(thisLatency,2)})
                iHavePing=True
            except: pingPlot.append({"x":thisAttenuation,"y":round(0,2)})

        if iHavePing:
            item = {
                "elementType": "section",
                "headingType": "h3",
                "headingContent":"Ping Latency vs Attenuation",
                "text": "Ping latency vs. attenuation, where each attenuation step is the ping latency averaged over the duration time."
            }
            myReport["Report"].append(item)
            
            item = {
                "elementType":"plot",
                "type": "scatter",
                "title": "Ping Latency vs. Attenuation plot",
                "xaxis":{"string":"Attenuation (dB)"},
                "yaxis":{"string":"Ping Latency (msec)"},
                "showTable": True,
                "plotWidth":"800px",
                "data":[
	            {
	                "label":"Latency",
	                "color":"blue",
	                "width":1,
	                "radius":0,
	                "data": pingPlot,
	                "fill": -1,
	                "style": "solid"
	            }
                ]	    
            }
            myReport["Report"].append(item)
        

        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Throughput vs Control RSSI",
            "text": "Throughput vs. control RSSI, where each attenuation step is the throughput averaged over the duration time, and the RSSI of the control packets linearly averaged."
        }
        myReport["Report"].append(item)

        rvrPlot = []
        for data in _analyzedData:
            try:thisRSSI = data["rssi"]["controlMean"]
            except:continue
            try:thisThroughput = data["throughput"]["mean"]
            except:continue
            try:rvrPlot.append({"x":thisRSSI,"y":round(thisThroughput,2)})
            except: rvrPlot.append({"x":thisRSSI,"y":round(0,2)})

        tolPrvr = []
        for i in range(len(rvrPlot),0,-1): tolPrvr.append(rvrPlot[i-1])

        plotData = [
	    {
	        "label":"Throughput",
	        "color":"green",
	        "width":1,
	        "radius":0,
	        "data": rvrPlot,
	        "fill": -1,
	        "style": "solid"
	    }
        ]

        #Let's do an analysis of the "expected" throughput at each point.
        expected = []
        standards = ["11ax", "11ac", "11n"]
        for standard in standards:
            thisObject = {"standard":standard}
            thisData = []
            if standard == "11ax":
                GI="800"
                scale=0.75
            if standard == "11ac":
                GI="400"
                scale=0.70
            if standard == "11n":
                GI="400"
                scale=0.60
            thisObject["scale"] = scale
            for data in _analyzedData:
                try:thisRSSI = data["rssi"]["controlMean"]
                except:continue
                try:thisBW = data["BW"]["rxMode"]
                except:continue
                try:thisNSS = data["streams"]["rxMode"]
                except:continue
                api_endpoint = ea_root + "getMCS" + "?standard="+standard + "&BW="+str(thisBW) + "&streams="+str(thisNSS) + "&RSSI="+str(thisRSSI)
                theResponse = requests.get(url=api_endpoint)
                theJson = json.loads(theResponse.text)
                thisMCS = theJson["MCS"]
                api_endpoint = ea_root + "getDRate" + "?standard="+standard + "&BW="+str(thisBW) + "&streams="+str(thisNSS) + "&MCS="+str(thisMCS) + "&GI="+GI
                theResponse = requests.get(url=api_endpoint)
                theJson = json.loads(theResponse.text)
                thisRate = theJson["rate"]
                if thisRate>=0: thisThroughput = thisRate*scale
                else: thisThroughput = -1
                thisItem = {"rssi":thisRSSI, "BW":thisBW, "NSS":thisNSS, "MCS":thisMCS, "rate":thisRate, "throughput":thisThroughput}
                #if thisRate>=0: thisData.append(thisItem)
                thisData.append(thisItem)
            thisObject["data"]=thisData
            expected.append(thisObject)
        #info(json.dumps(expected,indent=3))

        idx = -1
        for item in expected:
            if len(item["data"])==0: continue
            idx += 1
            label = "Expected throughput for 802." + item["standard"] + " at " + str(item["scale"]*100) + "% of the data rate"
            color = colors[idx % len(colors) + 6]
            thisData = []
            for result in item["data"]:
                thisData.append({"x":result["rssi"],"y":round(result["throughput"],2)})
            plotData.append({"label":label,"color":color,"width":1,"radius":0,"data":thisData,"fill": -1,"style": "short-dash"})

        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "Rate vs. Control RSSI plot",
            "xaxis":{"string":"Control RSSI (dBm)","reverse":True},
            "yaxis":{"string":"Throughput (Mbps)"},
            "showTable": True,
            "plotWidth":"800px",
            "data": plotData
        }
        myReport["Report"].append(item)

        if iHavePing:
            item = {
                "elementType": "section",
                "headingType": "h3",
                "headingContent":"Ping Latency vs Control RSSI",
                "text": "Ping latency vs. control RSSI, where each attenuation step is the ping latency averaged over the duration time, and the RSSI of the control packets linearly averaged."
            }
            myReport["Report"].append(item)

            pingPlot = []
            for data in _analyzedData:
                try:thisRSSI = data["rssi"]["controlMean"]
                except:continue
                try:thisLatency = data["pingLatency"]["mean"]
                except:continue
                try:pingPlot.append({"x":thisRSSI,"y":round(thisLatency,2)})
                except: rvrPlot.append({"x":thisRSSI,"y":round(0,2)})

            plotData = [
	        {
	            "label":"Throughput",
	            "color":"green",
	            "width":1,
	            "radius":0,
	            "data": pingPlot,
	            "fill": -1,
	            "style": "solid"
	        }
            ]	   
            item = {
                "elementType":"plot",
                "type": "scatter",
                "title": "Ping Latency vs. Control RSSI plot",
                "xaxis":{"string":"Control RSSI (dBm)","reverse":True},
                "yaxis":{"string":"Ping Latency (msec)"},
                "showTable": True,
                "plotWidth":"800px",
                "data": plotData
            }
            myReport["Report"].append(item)
                    
        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Throughput time series",
            "text": "All measured throughput values."
        }
        myReport["Report"].append(item)

        allData = []
        timeSeries = []
        for data in dataSet:
            try:thisTime = float(data["Time [ms]"])
            except:continue
            try:thisThroughput = float(data["Aggregated Throughput [Mbps]"])
            except:continue
            timeSeries.append({"x":thisTime/1000,"y":round(thisThroughput,2)})
        allData.append({
	            "label":"Aggregate Throughput",
	            "color":"blue",
	            "width":1,
	            "radius":0,
	            "data": timeSeries,
	            "fill": -1,
	            "style": "solid"
        })
        idx = 0
        for pair in trafficPairs:
            idx += 1
            tpName = trafficPairs[pair]
            timeSeries = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisThroughput = float(data[tpName + " Throughput [Mbps]"])
                except:continue
                timeSeries.append({"x":thisTime/1000,"y":round(thisThroughput,2)})
            allData.append({
	        "label":"Throughput for " + tpName,
	        "color": colors[idx % len(colors) + 4],
	        "width":1,
	        "radius":0,
	        "data": timeSeries,
	        "fill": -1,
	        "style": "solid"
            })                
            
        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "Throughput time plot",
            "xaxis":{"string":"Time (sec)"},
            "yaxis":{"string":"Throughput (Mbps)"},
            "showTable": False,
            "plotWidth":"800px",
            "data": allData
        }
        myReport["Report"].append(item)

        if iHaveIperf2:
            item = {
                "elementType": "section",
                "headingType": "h3",
                "headingContent":"iperf2 Latency time series",
                "text": "All measured iperf2 latency values."
            }
            myReport["Report"].append(item)

            allData = []
            timeSeries = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisLatency = float(data["Aggregated iPerf2 Latency Mean [ms]"])
                except:continue
                timeSeries.append({"x":thisTime/1000,"y":round(thisLatency,2)})
            allData.append({
	        "label":"Aggregate iPerf2 Latency",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": timeSeries,
	        "fill": -1,
	        "style": "solid"
            })
            idx = 0
            for pair in trafficPairs:
                idx += 1
                tpName = trafficPairs[pair]
                timeSeries = []
                for data in dataSet:
                    try:thisX = float(data["Time [ms]"])
                    except:continue
                    try:thisY = float(data[tpName + " iPerf2 Latency Mean [ms]"])
                    except:continue
                    timeSeries.append({"x":thisX/1000,"y":round(thisY,2)})
                allData.append({
	            "label":"iPerf2 Mean Latency for " + tpName,
	            "color": colors[idx % len(colors) + 4],
	            "width":1,
	            "radius":0,
	            "data": timeSeries,
	            "fill": -1,
	            "style": "solid"
                })                
                
            item = {
                "elementType":"plot",
                "type": "scatter",
                "title": "iperf2 Latency time plot",
                "xaxis":{"string":"Time (sec)"},
                "yaxis":{"string":"Latency (ms)"},
                "showTable": False,
                "plotWidth":"800px",
                "data":allData
            }
            myReport["Report"].append(item)
            
        if iHavePing:
            item = {
                "elementType": "section",
                "headingType": "h3",
                "headingContent":"Ping Latency time series",
                "text": "All measured ping latency values."
            }
            myReport["Report"].append(item)

            allData = []
            timeSeries = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisLatency = float(data["Aggregated Ping Latency (ms)"])
                except:continue
                timeSeries.append({"x":thisTime/1000,"y":round(thisLatency,2)})
            allData.append({
	        "label":"Aggregate Ping Latency",
	        "color":"blue",
	        "width":1,
	        "radius":0,
	        "data": timeSeries,
	        "fill": -1,
	        "style": "solid"
            })
            idx = 0
            for pair in pingPairs:
                idx += 1
                ppName = pingPairs[pair]
                timeSeries = []
                for data in dataSet:
                    try:thisX = float(data["Time [ms]"])
                    except:continue
                    try:thisY = float(data[ppName + " Ping Latency (ms)"])
                    except:continue
                    timeSeries.append({"x":thisX/1000,"y":round(thisY,2)})
                allData.append({
	            "label":"Ping Latency for " + ppName,
	            "color": colors[idx % len(colors) + 4],
	            "width":1,
	            "radius":0,
	            "data": timeSeries,
	            "fill": -1,
	            "style": "solid"
                })                
                
            item = {
                "elementType":"plot",
                "type": "scatter",
                "title": "Latency time plot",
                "xaxis":{"string":"Time (sec)"},
                "yaxis":{"string":"Latency (ms)"},
                "showTable": False,
                "plotWidth":"800px",
                "data": allData
            }
            myReport["Report"].append(item)
            

        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Data rate time series",
            "text": "All measured PHY data rates."
        }
        myReport["Report"].append(item)

        allData = []
        for p in range(0,len(palEndpoints)):
            pe = str(p+1)
            timeSeries1 = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisRateRx = float(data["Pal Endpoint " + pe + " RX rate [Mbps] Mode"])
                except:continue
                timeSeries1.append({"x":thisTime/1000,"y":round(thisRateRx,2)})
            timeSeries2 = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisRateTx = float(data["Pal Endpoint " + pe + " TX rate [Mbps] Mode"])
                except:continue
                timeSeries2.append({"x":thisTime/1000,"y":round(thisRateTx,2)})
            thisColor = colors[len(allData) % len(colors) + 4]
            allData.append(
	        {
	            "label":"PE " + pe + " Rx data rate, mode (Mbps)",
	            "color": thisColor,
	            "width":1,
	            "radius":0,
	            "data": timeSeries1,
	            "fill": -1,
	            "style": "solid"
	        })
            allData.append(
	        {
	            "label":"PE " + pe + " Tx data rate, mode (Mbps)",
	            "color": thisColor,
	            "width":1,
	            "radius":0,
	            "data": timeSeries2,
	            "fill": -1,
	            "style": "long-dash"
	        })

        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "Data rate time plot",
            "xaxis":{"string":"Time (sec)"},
            "yaxis":{"string":"PHY data rates (Mbps)"},
            "showTable": False,
            "plotWidth":"800px",
            "data":allData
        }
        myReport["Report"].append(item)

        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"MCS time series",
            "text": "All measured MCS values."
        }
        myReport["Report"].append(item)

        allData = []
        for p in range(0,len(palEndpoints)):
            pe = str(p+1)        
            timeSeries1 = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisValRx = float(data["Pal Endpoint " + pe + " RX MCS Mode"])
                except:continue
                timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
            timeSeries2 = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisValTx = float(data["Pal Endpoint " + pe + " TX MCS Mode"])
                except:continue
                timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})
            thisColor = colors[len(allData) % len(colors) + 4]
            allData.append(
	        {
	            "label":"PE " + pe + " Rx MCS, mode",
	            "color": thisColor,
	            "width":1,
	            "radius":0,
	            "data": timeSeries1,
	            "fill": -1,
	            "style": "solid"
	        })
            allData.append(
	        {
	            "label":"PE " + pe + " Tx MCS. mode",
	            "color": thisColor,
	            "width":1,
	            "radius":0,
	            "data": timeSeries2,
	            "fill": -1,
	            "style": "long-dash"
	        })

        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "MCS time plot",
            "xaxis":{"string":"Time (sec)"},
            "yaxis":{"string":"MCS value"},
            "showTable": False,
            "plotWidth":"800px",
            "data":allData
        }
        myReport["Report"].append(item)

        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Stream time series",
            "text": "All measured spatial stream values."
        }
        myReport["Report"].append(item)

        allData = []
        timeSeries1 = []
        for p in range(0,len(palEndpoints)):
            pe = str(p+1)
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisValRx = float(data["Pal Endpoint " + pe + " RX Nss Mode"])
                except:continue
                timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
            timeSeries2 = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisValTx = float(data["Pal Endpoint " + pe + " TX Nss Mode"])
                except:continue
                timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})
            thisColor = colors[len(allData) % len(colors) + 4]
            allData.append(
	        {
	            "label":"PE " + pe + " Rx spatial streams, mode",
	            "color": thisColor,
	            "width":1,
	            "radius":0,
	            "data": timeSeries1,
	            "fill": -1,
	            "style": "solid"
	        })
            allData.append(
	        {
	            "label":"PE " + pe + " Tx spatial streams, mode",
	            "color": thisColor,
	            "width":1,
	            "radius":0,
	            "data": timeSeries2,
	            "fill": -1,
	            "style": "long-dash"
	        })

        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "Spatial Stream time plot",
            "xaxis":{"string":"Time (sec)"},
            "yaxis":{"string":"Number of spatial streams"},
            "showTable": False,
            "plotWidth":"800px",
            "data":allData
        }
        myReport["Report"].append(item)

        item = {
            "elementType": "section",
            "headingType": "h3",
            "headingContent":"Bandwidth time series",
            "text": "All measured bandwidth values."
        }
        myReport["Report"].append(item)

        allData = []
        for p in range(0,len(palEndpoints)):
            pe = str(p+1)
            timeSeries1 = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisValRx = float(data["Pal Endpoint " + pe + " RX Bandwidth [MHz] Mode"])
                except:continue
                timeSeries1.append({"x":thisTime/1000,"y":round(thisValRx,2)})
            timeSeries2 = []
            for data in dataSet:
                try:thisTime = float(data["Time [ms]"])
                except:continue
                try:thisValTx = float(data["Pal Endpoint " + pe + " TX Bandwidth [MHz] Mode"])
                except:continue
                timeSeries2.append({"x":thisTime/1000,"y":round(thisValTx,2)})
            thisColor = colors[len(allData) % len(colors) + 4]
            allData.append(
	        {
	            "label":"PE " + pe + " Rx bandwidth (MHz), mode",
	            "color": thisColor,
	            "width":1,
	            "radius":0,
	            "data": timeSeries1,
	            "fill": -1,
	            "style": "solid"
	        })
            allData.append(
	        {
	            "label":"PE " + pe + " Tx bandwidth (MHz), mode",
	            "color": thisColor,
	            "width":1,
	            "radius":0,
	            "data": timeSeries2,
	            "fill": -1,
	            "style": "long-dash"
	        })
        
        item = {
            "elementType":"plot",
            "type": "scatter",
            "title": "Bandwidth time plot",
            "xaxis":{"string":"Time (sec)"},
            "yaxis":{"string":"Bandwidth [MHz]"},
            "showTable": False,
            "plotWidth":"800px",
            "data":allData
        }
        myReport["Report"].append(item)

        item = {
            "elementType": "section",
            "headingType": "h2",
            "headingContent":"Alerts",
            "text": "List of any Alerts generated in the running of this test."
        }
        myReport["Report"].append(item)

        alerts = []
        if len(alerts) == 0:
            item = {
                "elementType": "text",
                "text": "\nThere are no Alerts to report."
            }
        else:
            html = "<ul>";
            for alert in alerts: html += "<li>" + alert + "</li>"
            html += "</ul>";
            item = {
                "elementType": "text",
                "text": html
            }
        myReport["Report"].append(item)


    info("{} JSON report is complete. {}".format(cGreen,cNormal))
    
    #Generate the proper html for this report
    '''
    #api_endpoint = "http://localhost:5678/jsonToHtmlReport"
    api_endpoint = "http://octapi.tech:7568/jsonToHtmlReport"
    data = {'json':json.dumps(myReport,indent=4)}
    r = requests.post(url=api_endpoint,data=data)
    y = json.loads(r.text)
    #html = y["html"]
    link = y["link"]
    
    info("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))
    info("{} HTML report has been written to {}. {}".format(cGreen,link,cNormal))
    print("ArtifactLink:Description:\"HTML Report, cloud\",Link:",link)

    #Create a JSON file that will put a link to the previous file into script manager.
    jsonPlot = {}
 
    jsonPlot["zipLink"] = {
        "val": {"htmlLink": theURL},
        "label": theLink,
        "withTitle": theTitle
    }
   
    jsonPlot["reportLink"] = {
        "val": {"htmlLink": link},
        "label": "Online HTML Report for " + theTitle,
        "withTitle": theTitle
    }
    jsonPlot["_editable"] = False
    f = open(directory_name+'TestReportCloud.json', "w")
    f.write(json.dumps(jsonPlot,indent=4))
    f.close()

    info("{} Link to HTML has been generated. {}".format(cGreen,cNormal))
    '''
    
    #Put the local link anyway.

    # Let's see if we can find script manager running here.  If so, put some local copies
    try:
        #Verify where scriptManager is running
        localSM = True
        api_endpoint = "http://localhost:5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
    except requests.exceptions.RequestException as error:
        print(">>> initializeAutotest: Unable to find a local copy of script manager.  So not going to do anything here.")
        print("initializeAutotest: Error: ", error)
        localSM = False

    if localSM:
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        storageLocation = scriptManagerLocation + "/" + "storage/"
        #print("storageLocation is {}".format(storageLocation))
        fileName = theName + ".html"
        fullPath = storageLocation + fileName
        #print("The full path for the saved file is {}".format(fullPath))

        #Generate the proper html for this report
        api_endpoint = "http://localhost:5678/jsonToHtmlReport"
        data = {'json':json.dumps(myReport,indent=4)}
        r = requests.post(url=api_endpoint,data=data)
        y = json.loads(r.text)
        html = y["html"]
        print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))

        #Write out this html file
        f = open(fullPath, "w")
        f.write(html)
        f.close()    
        print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

        #Create a JSON file that will put a link to the previous file into script manager.
        jsonPlot = {}
        jsonPlot["reportLink"] = {
            "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
            "label": "Report for " + theName,
            "withTitle": theTitle            
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'TestReportLocal.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))
    

#===
#Use this for debugging.  Otherwise, comment it out.
'''
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-10-12_11-27_calix/1_2026-10-12_11-27_multiPair/"
ea_root = "http://localhost:8080/"
main(directory_name,json_dir,ea_root)
'''
