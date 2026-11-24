import sys
import json
import os
import requests
import base64
import pprint
import time
pp = pprint.PrettyPrinter(indent=4)

from pathlib import Path

import doRoamingAnalysis2
import numpy as np

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

# Set up some text coloring
cRed=   '\033[33m'
cGreen= '\033[32m'
cNormal='\033[m'
        
def main(directory_name,json_dir,jsonFile,pcapFile,etc):
        #etc = {"endpointTag":endpointTag, "countRoams":countRoams, "roamSet":roamSet}
        endpointTag = etc["endpointTag"]
        countRoams = etc["countRoams"]
        roamSet = etc["roamSet"]
        upOrDown = etc["upOrDown"]


        #Grab the directory information as created by SM.
        if directory_name[len(directory_name)-1] != "/": directory_name += "/"
        dirFile = directory_name + "directories.json"
        try:
                f = open(dirFile)
                directoriesJson = json.load(f)
                subDir = directoriesJson["subDirectory"]
                splits = subDir.split("_")
                runNumber = splits[0]
                #print('>>> splits: ', splits)
                #theName = splits[2]
                theName = directoriesJson["title"]
                theTitle = theName.replace(" ","_")
        except:
                theTitle = "No Name Found"
                theName = theTitle.replace(" ","_")
                runNumber = "0"                

        pcapDir = json_dir
        
        print("Calling doRoamingAnalysis2 with: \n{} \n{} \n{} \n{} \n{}".format(pcapDir,directory_name,pcapFile,jsonFile,etc))
        myReport,roamTimes,allFTtimes,appGap,EAPOL_groups,throughputs = doRoamingAnalysis2.main(pcapDir,directory_name,pcapFile,jsonFile,etc)

        #print("After doRoamingAnalysis2: roamTimes are {}".format(roamTimes))
        
        roams = {}
        for roam in roamTimes:
                if roam["type"] not in roams: roams[roam["type"]] = roam["roamTime"]
                else:
                        existingTime = roams[roam["type"]]
                        newTime = roam["roamTime"]
                        if newTime < existingTime: roams[roam["type"]] = roam["roamTime"]
        #print(roams)

        #Generate the proper html for this report
        api_endpoint = "http://localhost:5678/jsonToHtmlReport"
        data = {'json':json.dumps(myReport,indent=4)}
        r = requests.post(url=api_endpoint,data=data)
        y = json.loads(r.text)
        html = y["html"]

        print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))

        #Verify where scriptManager is running
        api_endpoint = "http://localhost:5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        storageLocation = scriptManagerLocation + "/" + "storage/"
        #print("storageLocation is {}".format(storageLocation))
        #fileName = theName+".html"
        fileName = theName + "_" + runNumber + ".html"
        fullPath = storageLocation + fileName
        #print("The full path for the saved file is {}".format(fullPath))

        #Write out this html file
        f = open(fullPath, "w")
        f.write(html)
        f.close()

        print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

        #Also, store the JSON formatted plot, and put a link to it in ReportList.json.
        jsonName = theName+".json"
        plotPath = storageLocation + jsonName
        f = open(plotPath, "w")
        f.write(json.dumps(myReport,indent=3))
        f.close()
        #.........
        jsonPath = storageLocation + "ReportList.json"
        f = open(jsonPath, "r")
        try:    currentList = json.load(f)
        except: currentList = {}
        f.close()
        currentList[fileName] = plotPath
        f = open(jsonPath, "w")
        f.write(json.dumps(currentList,indent=3))
        f.close()
        #print("Updated the current list to {}".format(currentList))

        #Create a JSON file that will put a link to the previous file into script manager.
        jsonPlot = {}
        jsonPlot["reportLink"] = {
                "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
                "label": "Report for " + theTitle + ", " + runNumber
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'TestReport-'+theTitle+ "_" + runNumber + '.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

        return roams,allFTtimes,appGap,EAPOL_groups,throughputs,myReport

#===============================================================================================

def roamPlot(directory_name,json_dir,outlierLow,outlierHigh):

        print("Creating a report from the data found in '{}'".format(json_dir))

        myReport = {}
        myReport["Title"] = "Roaming Statistics"
        myReport["Report"] = []
        
        if json_dir[len(json_dir)-1] != "/": json_dir += "/"
        #Find the testlog file
        for x in os.listdir(json_dir):
                if "testresultlog" in x:
                        #print (x)
                        logFile = json_dir + x
                        #print(logFile)
        try:
                f = open(logFile)
                logs = json.load(f)
                roamData = logs["roamData"]
        except:
                print("no logfile")
                item = {
                        "elementType":"text",
                        "text": "<p/><b> Not able to get roam time information from file " + logFile + ".</b>"
                }
                myReport["Report"].append(item)
                return myReport

        item = {
            "elementType":"section",
            "headingType":"h1",
            "headingContent": "Roam Time Information"
        }
        myReport["Report"].append(item)


        item = {
            "elementType":"text",
            "text": "Roam Times are essentially the time between the last data packet on the first AP, and the first data packet on the second AP.  There are a number of different definitions of roam time.  In some of those, these must be ACKed data packets.  In some, the data packets cannot be retried.  In others we use only uplink packets, the time between block ACKs, etc.  Crucially, we have shown the plots here for the data in the {}th to {}th percentiles, to avoid allowing outliers to dominate the plot scaling.".format(outlierLow,outlierHigh)
        }
        myReport["Report"].append(item)
        
        
        myReport["Report"].append(item)
        item = {
	        "elementType": "gridFormatting",
	        "action": "start"
	}
        myReport["Report"].append(item)

        item = {
	        "elementType": "gridFormatting",
	        "action": "newItem"
	}
        myReport["Report"].append(item)
        
        item = {
            "elementType":"text",
            "text": "<p/><b> Individual roam times </b>"
        }
        myReport["Report"].append(item)

        timeData = []
        roams = []
        useType = "Cisco"
        #useType = "TCP-UDP"
        useTypes = [ "BothWaysData", "AllData", "TCP-UDP", "ULpackets", "Cisco", "experimental"]   #Use any roam of any type, in this order of preference.
        for item in roamData:
                foundOne = False
                for useType in useTypes:
                        if useType in roamData[item]:
                                timeData.append({"x":int(item), "y":roamData[item][useType]*1000})
                                roams.append(roamData[item][useType]*1000)
                                foundOne = True
                                break                        
                if not foundOne: roamData[item][useType] = -1/1000  #identify cases in which we don't have data.                

        posvals = []
        for item in roams:
                if item >=0 and item<=10000: posvals.append(item)  #Look only at roams that are shorter than 1 second, for now.
        if len(posvals)==0: posvals = roams  #Fall back if the roaming is really bad.

        if len(posvals) > 0:
                theLow = np.percentile(posvals,outlierLow)
                theHigh = np.percentile(posvals,outlierHigh)
                #print("5th percentile is {}, and 95th percentile is {}".format(the5,the95))
                hold = []
                for item in posvals: hold.append(item)
                posvals = []
                timeData = []
                roams = []
                count = 0
                outliers = 0
                for item in hold:
                        if item >= theLow and item <= theHigh:
                                count += 1
                                posvals.append(item)
                                timeData.append({"x":int(count), "y":item})
                                roams.append(item)
                        else:
                                outliers += 1
                theAverage = round(np.average(posvals),2)
                theStdDev  = round(np.std(posvals),2)
                                

                theData = {"label": useType + " Defined Roam Times",
                           "color": colors[2 % len(colors) + 4],
                           "width": 1,
                           "radius": 6,
                           "data": timeData,
                           "fill": -1,
                           "style": "solid"
                }
                item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "Roam time plot.  Ave={} msec., Std={} msec., Count={}, Out={}".format(theAverage,theStdDev,len(posvals),outliers),
                        "xaxis":{"string":"Run number"},
                        "yaxis":{"string":"Roam time (millisec)"},
                        "showTable": False,
                        "plotWidth": "500px",
                        "data": [theData] 
                }
                myReport["Report"].append(item)

                ea_root = "http://localhost:8080/"
                try:
                        theMax = max(posvals)
                except:
                        print("roams:  {}".format(roams))
                        print("posvals: {}".format(posvals))
                data = {"data":posvals, "bins":100, "minVal":0, "maxVal":theMax}
                api_endpoint = ea_root + "createHistogramFrom"
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }

                myReport["Report"].append(item)
                #print(theJson)
                item = {
                    "elementType":"text",
                    "text": "<p/><b> Roam time histogram </b>"
                }
                myReport["Report"].append(item)
                histogram = theJson["histogram"]
                labels = []
                data = []
                for x in histogram:
                        labels.append(str(round(x["binLabel"],2)))
                        data.append(x["binCount"])
                thisData = {
                        "label":"Roam time histogram",
                        "color":"red",
                        "width":1,
                        "data":data,
                        "fill": -1
                }
                item = {
                        "elementType":"plot",
                        "type": "bar",
                        "title": "Roam time histogram.  Ave={} msec., Std={} msec., Count={}".format(theAverage,theStdDev,len(posvals)),
                        "labels": labels,
                        "xaxis":{"string":"Roam time (millisec)"},
                        "yaxis":{"string":"Counts"},
                        "showTable": False,
                        "plotWidth": "500px",
                        "data": [thisData]
                }
                myReport["Report"].append(item)

                #print(posvals)

                data = {"data":posvals, "dir":1}
                api_endpoint = ea_root + "createCdfFrom"
                theResponse = requests.post(url=api_endpoint, data=data)
                theJson = json.loads(theResponse.text)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                #print(theJson)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> Roam time CDF </b>"
                }
                myReport["Report"].append(item)
                cdf = theJson["cdf"]
                #print(cdf)
                data = []
                for x in cdf:
                        data.append({"x":x["x"],"y":x["y"]})
                thisData = {
                        "label":"Roam time cdf",
                        "color":"red",
                        "width":1,
                        "data":data,
                        "fill": False,
                        "radius":2
                }
                item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "Roam time cdf.  Ave={} msec., Std={} msec., Count={}".format(theAverage,theStdDev,len(posvals)),
                        "xaxis":{"string":"Roam time (millisec)"},
                        "yaxis":{"string":"% of time < X axis"},
                        "showTable": False,
                        "plotWidth": "500px",
                        "data": [thisData]
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "end"
                }
                myReport["Report"].append(item)

        ###################################################################
        ###################################################################
        ###################################################################
        ###################################################################

        item = {
            "elementType":"section",
            "headingType":"h1",
            "headingContent": "Fast Transition Timing Information"
        }
        myReport["Report"].append(item)
        
        item = {
            "elementType":"text",
            "text": "The 'Fast Transition Time' is defined here to be the time between the Authentication Request packet (from the STA), and the Reassociation Response packet (from the AP.)  The reason that this is an interesting quantity is that, under BSS Fast Transitions, the STA is able to send packets at all times other than during this interval.  Before this AUTH packet, it can sent to the initial AP, and after the receipt of this second packet, it can send to the second AP."
        }
        myReport["Report"].append(item)
        
        allFTtimes = []
        for item in roamData:
                if "FTtimes" not in roamData[item]: continue
                if len(roamData[item]["FTtimes"])==0: roamData[item]["FTtimes"].append(-1)  #Identify cases in which you do not have data.
                for thisTime in roamData[item]["FTtimes"]:
                        allFTtimes.append(thisTime)

        posvals = []
        for item in allFTtimes:
                if item >=0: posvals.append(item)                        
        if len(posvals) > 0:
                theLow = np.percentile(posvals,outlierLow)
                theHigh = np.percentile(posvals,outlierHigh)
                #print("5th percentile is {}, and 95th percentile is {}".format(the5,the95))
                hold = []
                for item in posvals: hold.append(item)
                posvals = []
                timeData = []
                roams = []
                count = 0
                outliers = 0
                for item in hold:
                        if item >= theLow and item <= theHigh:
                                count += 1
                                posvals.append(item)
                                timeData.append({"x":int(count), "y":item})
                                roams.append(item)
                        else:
                                outliers += 1
                
                theAverage = round(np.average(posvals),2)
                theStdDev  = round(np.std(posvals),2)

                item = {
                        "elementType": "gridFormatting",
                        "action": "start"
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> Fast transition time plot </b>"
                }
                myReport["Report"].append(item)

                timeData = []
                x = 0
                for time in allFTtimes:
                        timeData.append({"x":x, "y":time})
                        x += 1

                theData = {"label": "Fast Transition Timing",
                           "color": colors[2 % len(colors) + 4],
                           "width": 1,
                           "radius": 6,
                           "data": timeData,
                           "fill": -1,
                           "style": "solid"
                }
                item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "Fast Transition time plot.  Ave={} msec., Std={} msec, Count={}, Out={}".format(theAverage,theStdDev,len(posvals),outliers),
                        "xaxis":{"string":"Fast transition number"},
                        "yaxis":{"string":"Fast transition time (msec)"},
                        "showTable": False,
                        "plotWidth": "500px",
                        "data": [theData] 
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> Fast transition histogram </b>"
                }
                myReport["Report"].append(item)

                if len(allFTtimes) > 0:
                        ea_root = "http://localhost:8080/"
                        theMax = max(allFTtimes)
                        data = {"data":allFTtimes, "bins":30, "minVal":0, "maxVal":theMax}
                        api_endpoint = ea_root + "createHistogramFrom"
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        histogram = theJson["histogram"]
                        labels = []
                        data = []
                        for x in histogram:
                                labels.append(str(round(x["binLabel"],2)))
                                data.append(x["binCount"])
                        thisData = {
                                "label":"Fast transition time histogram",
                                "color":"red",
                                "width":1,
                                "data":data,
                                "fill": -1
                        }
                        item = {
                                "elementType":"plot",
                                "type": "bar",
                                "title": "Fast transition time histogram.  Ave={} msec., Std={} msec., Count={}".format(theAverage,theStdDev,len(posvals)),
                                "labels": labels,
                                "xaxis":{"string":"Fast transition time (msec)"},
                                "yaxis":{"string":"Counts"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": [thisData]
                        }
                        myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> Fast transition time CDF </b>"
                }
                myReport["Report"].append(item)


                if len(allFTtimes) > 0:
                        data = {"data":allFTtimes, "dir":1}
                        api_endpoint = ea_root + "createCdfFrom"
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        cdf = theJson["cdf"]
                        data = []
                        for x in cdf:
                                data.append({"x":x["x"],"y":x["y"]})
                        thisData = {
                                "label":"Fast transition time cdf",
                                "color":"red",
                                "width":1,
                                "data":data,
                                "fill": False,
                                "radius":2
                        }
                        item = {
                                "elementType":"plot",
                                "type": "scatter",
                                "title": "Fast transition time cdf.  Ave={} msec., Std={} msec, Count={}".format(theAverage,theStdDev,len(posvals)),
                                "xaxis":{"string":"Fast transition time (msec)"},
                                "yaxis":{"string":"% of time < X axis"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": [thisData]
                        }
                        myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "end"
                }
                myReport["Report"].append(item)



        ###################################################################
        ###################################################################
        ###################################################################
        ###################################################################

        item = {
            "elementType":"section",
            "headingType":"h1",
            "headingContent": "Application Gap Based on Packet Analysis"
        }
        myReport["Report"].append(item)
        
        item = {
            "elementType":"text",
            "text": "The Application Gap Based on Packet Analysis examines the packets being sent by the traffic generator.  The last sent/received packet on the first AP, and the first sent/received packet on the second AP are used to define the gap seen in application traffic.  This may be longer than the roam time, above, because it also includes the time required for the application to adjust to a new connection.  It can also include the packet rate itself, so the test sends at a high rate of packets-per-second in order to avoid any effect due to packets simply not being sent."
        }
        myReport["Report"].append(item)
        
        allApplicationGaps = []
        allPPS = []
        for item in roamData:
                if "appGap" not in roamData[item]: continue
                else:
                        if "applicationGap" not in roamData[item]["appGap"]: continue
                        else: allApplicationGaps.append(roamData[item]["appGap"]["applicationGap"])
                        if "pps" not in roamData[item]["appGap"]: continue
                        else: allPPS.append(roamData[item]["appGap"]["pps"])

        posvals = []
        for item in allApplicationGaps:
                if item >=0: posvals.append(item)
        if len(posvals) > 0:
                theLow = np.percentile(posvals,outlierLow)
                theHigh = np.percentile(posvals,outlierHigh)
                #print("5th percentile is {}, and 95th percentile is {}".format(the5,the95))
                hold = []
                for item in posvals: hold.append(item)
                posvals = []
                timeData = []
                roams = []
                count = 0
                outliers = 0
                for item in hold:
                        if item >= theLow and item <= theHigh:
                                count += 1
                                posvals.append(item)
                                timeData.append({"x":int(count), "y":item})
                                roams.append(item)
                        else:
                                outliers += 1
                theAverage = round(np.average(posvals),2)
                theStdDev  = round(np.std(posvals),2)

                theAvePPS = round(np.average(allPPS),2)

                item = {
                        "elementType": "gridFormatting",
                        "action": "start"
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> Application Gap plot </b>"
                }
                myReport["Report"].append(item)

                timeData = []
                x = 0
                for time in allApplicationGaps:
                        timeData.append({"x":x, "y":time})
                        x += 1

                theData = {"label": "Application Gaps",
                           "color": colors[2 % len(colors) + 4],
                           "width": 1,
                           "radius": 6,
                           "data": timeData,
                           "fill": -1,
                           "style": "solid"
                }
                item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "Application Gap plot.  Ave={} msec., Std={} msec, Count={}, Out = {}, AvePPS={}".format(theAverage,theStdDev,len(posvals), outliers, theAvePPS),
                        "xaxis":{"string":"Application Gap number"},
                        "yaxis":{"string":"Application Gap time (msec)"},
                        "showTable": False,
                        "plotWidth": "500px",
                        "data": [theData] 
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> Application Gap histogram </b>"
                }
                myReport["Report"].append(item)

                if len(allApplicationGaps) > 0:
                        ea_root = "http://localhost:8080/"
                        theMax = max(allApplicationGaps)
                        data = {"data":allApplicationGaps, "bins":30, "minVal":0, "maxVal":theMax}
                        api_endpoint = ea_root + "createHistogramFrom"
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        histogram = theJson["histogram"]
                        labels = []
                        data = []
                        for x in histogram:
                                labels.append(str(round(x["binLabel"],2)))
                                data.append(x["binCount"])
                        thisData = {
                                "label":"Application Gap histogram",
                                "color":"red",
                                "width":1,
                                "data":data,
                                "fill": -1
                        }
                        item = {
                                "elementType":"plot",
                                "type": "bar",
                                "title": "Application Gap histogram.  Ave={} msec., Std={} msec., Count={}".format(theAverage,theStdDev,len(posvals)),
                                "labels": labels,
                                "xaxis":{"string":"Application Gap (msec)"},
                                "yaxis":{"string":"Counts"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": [thisData]
                        }
                        myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> Application Gap CDF </b>"
                }
                myReport["Report"].append(item)


                if len(allApplicationGaps) > 0:
                        data = {"data":allApplicationGaps, "dir":1}
                        api_endpoint = ea_root + "createCdfFrom"
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        cdf = theJson["cdf"]
                        data = []
                        for x in cdf:
                                data.append({"x":x["x"],"y":x["y"]})
                        thisData = {
                                "label":"Application Gap cdf",
                                "color":"red",
                                "width":1,
                                "data":data,
                                "fill": False,
                                "radius":2
                        }
                        item = {
                                "elementType":"plot",
                                "type": "scatter",
                                "title": "Application Gap cdf.  Ave={} msec., Std={} msec, Count={}".format(theAverage,theStdDev,len(posvals)),
                                "xaxis":{"string":"Application Gap (msec)"},
                                "yaxis":{"string":"% of time < X axis"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": [thisData]
                        }
                        myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "end"
                }
                myReport["Report"].append(item)

        else:
                theAverage = round(np.average(posvals),2)
                theStdDev  = round(np.std(posvals),2)
                theAvePPS = round(np.average(allPPS),2)

        ###################################################################
        ###################################################################
        ###################################################################
        ###################################################################

        item = {
            "elementType":"section",
            "headingType":"h1",
            "headingContent": "Application Gap Based on iPerf Reporting"
        }
        myReport["Report"].append(item)
        
        item = {
            "elementType":"text",
            "text": "The Application Gap Based on iPerf Reporting uses the fact that iPerf reports the number of lost packets, at least when running UDP traffic.  Since the packet rate sent by iPerf is constant (X packets/second), the number of lost packets can be turned into a time gap using the formula Gap = LostPackets/X.  Under the assumption that the lost packets will occur near the handoff event, this calculation finds the gap in packet transmission due to that handover.  The value of X is estimated by looking at the total number of packets sent by iPerf divided by the total time.  This is referred to as the Steady-State-Packet-Rate."
        }
        myReport["Report"].append(item)
        
        alliperfGaps = []
        ssrs = []
        for item in roamData:
                if "appGap" not in roamData[item]: continue
                else:
                        if "iperfGap" not in roamData[item]["appGap"]: continue
                        else: alliperfGaps.append(roamData[item]["appGap"]["iperfGap"])
                        if "steadyStateRate" not in roamData[item]["appGap"]: continue
                        else: ssrs.append(roamData[item]["appGap"]["steadyStateRate"])

        posvals = []
        for item in alliperfGaps:
                if item >=0: posvals.append(item)                        
        if len(posvals) > 0:
                theLow = np.percentile(posvals,outlierLow)
                theHigh = np.percentile(posvals,outlierHigh)
                #print("5th percentile is {}, and 95th percentile is {}".format(the5,the95))
                hold = []
                for item in posvals: hold.append(item)
                posvals = []
                timeData = []
                roams = []
                count = 0
                outliers = 0
                for item in hold:
                        if item >= theLow and item <= theHigh:
                                count += 1
                                posvals.append(item)
                                timeData.append({"x":int(count), "y":item})
                                roams.append(item)
                        else:
                                outliers += 1
                theAverage = round(np.average(posvals),2)
                theStdDev  = round(np.std(posvals),2)

                aveSSR = round(np.average(ssrs),2)
                item = {
                    "elementType":"text",
                    "text": "<p/>The Steady State Rate from iPerf data is {} pps, which can be compared to the rate found from packet analysis, which is {}".format(aveSSR,theAvePPS)
                }
                myReport["Report"].append(item)


                item = {
                        "elementType": "gridFormatting",
                        "action": "start"
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> iPerf Gap plot </b>"
                }
                myReport["Report"].append(item)

                timeData = []
                x = 0
                for time in alliperfGaps:
                        timeData.append({"x":x, "y":time})
                        x += 1

                theData = {"label": "iPerf Gaps",
                           "color": colors[2 % len(colors) + 4],
                           "width": 1,
                           "radius": 6,
                           "data": timeData,
                           "fill": -1,
                           "style": "solid"
                }
                item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "iPerf Gap plot.  Ave={} msec., Std={} msec, Count={}, Out={}".format(theAverage,theStdDev,len(posvals),outliers),
                        "xaxis":{"string":"iPerf Gap number"},
                        "yaxis":{"string":"iPerf Gap time (msec)"},
                        "showTable": False,
                        "plotWidth": "500px",
                        "data": [theData] 
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> iPerf Gap histogram </b>"
                }
                myReport["Report"].append(item)

                if len(alliperfGaps) > 0:
                        ea_root = "http://localhost:8080/"
                        theMax = max(alliperfGaps)
                        data = {"data":alliperfGaps, "bins":30, "minVal":0, "maxVal":theMax}
                        api_endpoint = ea_root + "createHistogramFrom"
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        histogram = theJson["histogram"]
                        labels = []
                        data = []
                        for x in histogram:
                                labels.append(str(round(x["binLabel"],2)))
                                data.append(x["binCount"])
                        thisData = {
                                "label":"iPerf Gap histogram",
                                "color":"red",
                                "width":1,
                                "data":data,
                                "fill": -1
                        }
                        item = {
                                "elementType":"plot",
                                "type": "bar",
                                "title": "iPerf Gap histogram.  Ave={} msec., Std={} msec., Count={}".format(theAverage,theStdDev,len(posvals)),
                                "labels": labels,
                                "xaxis":{"string":"iPerf Gap (msec)"},
                                "yaxis":{"string":"Counts"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": [thisData]
                        }
                        myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> iPerf Gap CDF </b>"
                }
                myReport["Report"].append(item)


                if len(alliperfGaps) > 0:
                        data = {"data":alliperfGaps, "dir":1}
                        api_endpoint = ea_root + "createCdfFrom"
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        cdf = theJson["cdf"]
                        data = []
                        for x in cdf:
                                data.append({"x":x["x"],"y":x["y"]})
                        thisData = {
                                "label":"iPerf Gap cdf",
                                "color":"red",
                                "width":1,
                                "data":data,
                                "fill": False,
                                "radius":2
                        }
                        item = {
                                "elementType":"plot",
                                "type": "scatter",
                                "title": "iPerf Gap cdf.  Ave={} msec., Std={} msec, Count={}".format(theAverage,theStdDev,len(posvals)),
                                "xaxis":{"string":"iPerf Gap (msec)"},
                                "yaxis":{"string":"% of time < X axis"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": [thisData]
                        }
                        myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "end"
                }
                myReport["Report"].append(item)

        ###################################################################
        ###################################################################
        ###################################################################
        ###################################################################

        item = {
            "elementType":"section",
            "headingType":"h1",
            "headingContent": "Time spent in EAPOL exchange"
        }
        myReport["Report"].append(item)
        
        item = {
            "elementType":"text",
            "text": "The Time Spent in EAPOL exchange looks at the various EAPOL exchanges and calculates the time between the first and last packets in the exchange."
        }
        myReport["Report"].append(item)
        
        allEapolGaps = []
        for item in roamData:
                if "EAPOL_groups" not in roamData[item]: continue
                else:
                        for group in roamData[item]["EAPOL_groups"]:
                                if "timeSpentMsec" not in group: continue
                                else: allEapolGaps.append(group["timeSpentMsec"])

        posvals = []
        for item in allEapolGaps:
                if item >=0: posvals.append(item)                        
        if len(posvals) > 0:
                theAverage = round(np.average(posvals),2)
                theStdDev  = round(np.std(posvals),2)

                item = {
                        "elementType": "gridFormatting",
                        "action": "start"
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> EAPOL Gap plot </b>"
                }
                myReport["Report"].append(item)

                timeData = []
                x = 0
                for time in allEapolGaps:
                        timeData.append({"x":x, "y":time})
                        x += 1

                theData = {"label": "EAPOL Gaps",
                           "color": colors[2 % len(colors) + 4],
                           "width": 1,
                           "radius": 6,
                           "data": timeData,
                           "fill": -1,
                           "style": "solid"
                }
                item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "EAPOL Gap plot.  Ave={} msec., Std={} msec, Count={}".format(theAverage,theStdDev,len(posvals)),
                        "xaxis":{"string":"EAPOL Gap number"},
                        "yaxis":{"string":"EAPOL Gap time (msec)"},
                        "showTable": False,
                        "plotWidth": "500px",
                        "data": [theData] 
                }
                myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> EAPOL Gap histogram </b>"
                }
                myReport["Report"].append(item)

                if len(alliperfGaps) > 0:
                        ea_root = "http://localhost:8080/"
                        theMax = max(alliperfGaps)
                        data = {"data":allEapolGaps, "bins":30, "minVal":0, "maxVal":theMax}
                        api_endpoint = ea_root + "createHistogramFrom"
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        histogram = theJson["histogram"]
                        labels = []
                        data = []
                        for x in histogram:
                                labels.append(str(round(x["binLabel"],2)))
                                data.append(x["binCount"])
                        thisData = {
                                "label":"EAPOL Gap histogram",
                                "color":"red",
                                "width":1,
                                "data":data,
                                "fill": -1
                        }
                        item = {
                                "elementType":"plot",
                                "type": "bar",
                                "title": "EAPOL Gap histogram.  Ave={} msec., Std={} msec., Count={}".format(theAverage,theStdDev,len(posvals)),
                                "labels": labels,
                                "xaxis":{"string":"EAPOL Gap (msec)"},
                                "yaxis":{"string":"Counts"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": [thisData]
                        }
                        myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "newItem"
                }
                myReport["Report"].append(item)

                item = {
                    "elementType":"text",
                    "text": "<p/><b> iPerf Gap CDF </b>"
                }
                myReport["Report"].append(item)


                if len(allEapolGaps) > 0:
                        data = {"data":allEapolGaps, "dir":1}
                        api_endpoint = ea_root + "createCdfFrom"
                        theResponse = requests.post(url=api_endpoint, data=data)
                        theJson = json.loads(theResponse.text)

                        cdf = theJson["cdf"]
                        data = []
                        for x in cdf:
                                data.append({"x":x["x"],"y":x["y"]})
                        thisData = {
                                "label":"EAPOL Gap cdf",
                                "color":"red",
                                "width":1,
                                "data":data,
                                "fill": False,
                                "radius":2
                        }
                        item = {
                                "elementType":"plot",
                                "type": "scatter",
                                "title": "EAPOL Gap cdf.  Ave={} msec., Std={} msec, Count={}".format(theAverage,theStdDev,len(posvals)),
                                "xaxis":{"string":"EAPOL Gap (msec)"},
                                "yaxis":{"string":"% of time < X axis"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": [thisData]
                        }
                        myReport["Report"].append(item)

                item = {
                        "elementType": "gridFormatting",
                        "action": "end"
                }
                myReport["Report"].append(item)
        
        #Throughput plots
        throughput_data = []
        for item in roamData:
                if "throughputs" not in roamData[item]: continue
                else:
                        #print (len(roamData[item]['throughputs']))
                        if len(roamData[item]["throughputs"]) > 0: throughput_data.append(roamData[item]["throughputs"]) 
        pairs = []
        for item in throughput_data:
                for key in item:
                        if key in pairs: continue
                        else: pairs.append(key)
        directions = []
        for item in throughput_data:
                for pair in item:
                        try:
                                direction = item[pair]["pre-roam"]["bssid"] + "___TO___" + item[pair]["post-roam"]["bssid"]
                                if direction in directions: continue
                                else: directions.append(direction)
                        except: print("Not enough throughput information")

        traffic = {}
        for pair in pairs:
                traffic[pair] = []
                for item in throughput_data:
                        if pair in item: traffic[pair].append(item[pair])

        item = {
            "elementType":"section",
            "headingType":"h1",
            "headingContent": "Throughput plots for all traffic pairs"
        }
        myReport["Report"].append(item)
        
        item = {
            "elementType":"text",
            "text": "Plots of the average throughput for each test, for each traffic pair, shown with the pre-roam and post-roam data broken out separately."
        }
        myReport["Report"].append(item)
        
        ## Basic throughput plots, broken into pre- and post-roam throughput averages.
        item = {"elementType": "gridFormatting","action": "start"}
        myReport["Report"].append(item)
        for pair in pairs:
                item = {"elementType": "gridFormatting","action": "newItem"}
                myReport["Report"].append(item)
                pre_roam_throughput = []
                post_roam_throughput = []
                allData = []
                preAve = 0
                postAve = 0
                preAndPost = True
                for i in range(0,len(traffic[pair])):
                        try:
                                pre_roam_throughput.append({"x":i, "y":traffic[pair][i]["pre-roam"]["ave"]})
                                preAve += traffic[pair][i]["pre-roam"]["ave"]
                        except:
                                print("No pre_roam data")
                                preAndPost = False
                        try:
                                post_roam_throughput.append({"x":i, "y":traffic[pair][i]["post-roam"]["ave"]})
                                postAve += traffic[pair][i]["post-roam"]["ave"]
                        except:
                                print("No post_roam data")
                                preAndPost = False
                if not preAndPost: continue
                if len(pre_roam_throughput) > 0: preAve = preAve/len(pre_roam_throughput)
                if len(post_roam_throughput) > 0: postAve = postAve/len(post_roam_throughput)
                thisData = {
                        "label":"Pre-roam Throughput, Ave = {:.2f}".format(preAve),
                        "color":"red",
                        "width":1,
                        "data":pre_roam_throughput,
                        "fill": False,
                        "radius":2
                }
                allData.append(thisData)
                thisData = {
                        "label":"Post-Roam Throughput, Ave= {:.2f}".format(postAve),
                        "color":"blue",
                        "width":1,
                        "data":post_roam_throughput,
                        "fill": False,
                        "radius":2
                }
                allData.append(thisData)
                item = {
                        "elementType":"plot",
                        "type": "scatter",
                        "title": "Traffic pair '{}'".format(pair),
                        "xaxis":{"string":"Roam number"},
                        "yaxis":{"string":"Average Throughput (Mbps)"},
                        "showTable": False,
                        "plotWidth": "500px",
                        "data": allData
                }
                myReport["Report"].append(item)

        item = {"elementType": "gridFormatting","action": "end"}
        myReport["Report"].append(item)

        item = {
            "elementType":"section",
            "headingType":"h1",
            "headingContent": "Direction-oriented throughput plots for all traffic pairs"
        }
        myReport["Report"].append(item)
        
        item = {
            "elementType":"text",
            "text": "Plots of the average throughput for each test, for each traffic pair, shown with the pre-roam and post-roam data broken out separately.\nIn this case, we show the data from forward and reverse roams separately."
        }
        myReport["Report"].append(item)
        
        ## Same as above, pre- and post-roam throughput averages, but for each direction of travel separately.
        for direction in directions:
                item = {"elementType": "gridFormatting","action": "start"}
                myReport["Report"].append(item)
                for pair in pairs:
                        item = {"elementType": "gridFormatting","action": "newItem"}
                        myReport["Report"].append(item)
                        pre_roam_throughput = []
                        post_roam_throughput = []
                        allData = []
                        preAve = 0
                        postAve = 0
                        preAndPost = True
                        for i in range(0,len(traffic[pair])):
                                try:
                                        thisDirection = traffic[pair][i]["pre-roam"]["bssid"] + "___TO___" + traffic[pair][i]["post-roam"]["bssid"]
                                except:
                                        message = "problematic"
                                        thisDirection = None
                                if thisDirection != direction: continue
                                pre_roam_throughput.append({"x":i, "y":traffic[pair][i]["pre-roam"]["ave"]})
                                post_roam_throughput.append({"x":i, "y":traffic[pair][i]["post-roam"]["ave"]})
                                try: preAve += traffic[pair][i]["pre-roam"]["ave"]
                                except:
                                        print("Again, no pre-roam data.")
                                        preAndPost = False
                                try: postAve += traffic[pair][i]["post-roam"]["ave"]
                                except:
                                        print("Again, no post-roam data.")
                                        preAndPost = False
                        if not preAndPost: continue
                        if len(pre_roam_throughput) > 0: preAve = preAve/len(pre_roam_throughput)
                        if len(post_roam_throughput) > 0: postAve = postAve/len(post_roam_throughput)
                        thisData = {
                                "label":"Pre-Roam Throughput, Ave = {:.2f}".format(preAve),
                                "color":"red",
                                "width":1,
                                "data":pre_roam_throughput,
                                "fill": False,
                                "radius":2
                        }
                        allData.append(thisData)
                        thisData = {
                                "label":"Post-Roam Throughput, Ave = {:.2f}".format(postAve),
                                "color":"blue",
                                "width":1,
                                "data":post_roam_throughput,
                                "fill": False,
                                "radius":2
                        }
                        allData.append(thisData)
                        item = {
                                "elementType":"plot",
                                "type": "scatter",
                                "title": "Direction{}, Pair '{}'".format(direction,pair),
                                "xaxis":{"string":"Roam number"},
                                "yaxis":{"string":"Average Throughput (Mbps)"},
                                "showTable": False,
                                "plotWidth": "500px",
                                "data": allData
                        }
                        myReport["Report"].append(item)
                
                item = {"elementType": "gridFormatting","action": "end"}
                myReport["Report"].append(item)

        #print(myReport)
        
        #Generate the proper html for this report
        api_endpoint = "http://localhost:5678/jsonToHtmlReport"
        data = {'json':json.dumps(myReport,indent=4)}
        r = requests.post(url=api_endpoint,data=data)
        y = json.loads(r.text)
        html = y["html"]

        print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))

        #Verify where scriptManager is running
        api_endpoint = "http://localhost:5678/exec?command=pwd"
        r = requests.get(url=api_endpoint)
        y = json.loads(r.text)
        scriptManagerLocation = y["stdout"]
        scriptManagerLocation = scriptManagerLocation.replace("\n","")
        storageLocation = scriptManagerLocation + "/" + "storage/"
        fileName = "Roam_Time_Plots.html"
        fullPath = storageLocation + fileName

        #Write out this html file
        f = open(fullPath, "w")
        f.write(html)
        f.close()

        print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

        #Create a JSON file that will put a link to the previous file into script manager.
        jsonPlot = {}
        jsonPlot["reportLink"] = {
                "val": {"htmlLink": "http://localhost:5678/storage/"+fileName},
                "label": "Roam Time Plots"
        }
        jsonPlot["_editable"] = False
        f = open(directory_name+'Roam_Time_Reports.json', "w")
        f.write(json.dumps(jsonPlot,indent=4))
        f.close()

        print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

        return myReport
        
#===
#Use this for debugging.  Otherwise, comment it out.
'''
print("This is the debug section of Roaming, createReport.  Comment it out if you see it and don't expect to.")
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/Roaming/1_2024-02-20_10-09_Roaming/"
json_dir = "/home/octoscope/Documents/automation/results/2025-12-11_14-23_DUTID/1_2025-12-11_14-23_Roaming/"
pcapFile = json_dir + "2025-12-11_14-25_DUTID_Vx-x_roaming.pcap"
jsonFile = json_dir + "2025-12-11_14-26_DUTID_Vx-x_roaming.zip"

endpointTag = "STA-50"
countRoams = 0
roamSet = 0
upOrDown = "dn"
etc = {"endpointTag":endpointTag, "countRoams":countRoams, "roamSet":roamSet}
roams,allFTtimes,appGap,EAPOL_groups,throughputs,myReport = main(directory_name,json_dir,jsonFile,pcapFile,etc)
print ("roams: {}\n allFTtimes: {}\n appGap: {}\n".format(roams,allFTtimes,appGap))

#roamPlot(directory_name,json_dir,0,100)
'''
