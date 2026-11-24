import sys
import json
import os
import requests
import time

#ipAddress = "172.16.28.50"
    
def main(ipAddress):

    myObject = {"staInfo":{}, "APinfo":{}}
    
    timeout = 10
    api_endpoint = "http://{}:8383".format(ipAddress)
    goodToGo = False
    try:
        resp = requests.get(url=api_endpoint, timeout=timeout)
        jsn = json.loads(resp.text)
        #print('>>> jsn: ', jsn)
        if jsn["status"] and jsn["status"] =="OK" and "reached" in jsn["msg"]:
            print("basic-server is reachable on {}".format(ipAddress))
            goodToGo = True
    except:
        print("basic-server is not reachable on {}".format(ipAddress))
    
    if goodToGo:
        staInfo = {}
        theCommand = "iw dev"
        api_endpoint = "http://{}:8383/exec?command={}".format(ipAddress,theCommand)
        r = requests.get(url=api_endpoint)
        theJson = json.loads(r.text)
        if theJson["status"] == "OK":
            theResponse = theJson["stdout"]
            #print(theResponse)
            intermediateString = theResponse.replace("\n"," ").replace("\t"," ")
            intermediateString = " ".join(intermediateString.split())
            theElements = intermediateString.split(" ")
            #print(theElements)
            Interface = None
            for i in range(0,len(theElements)):
                if theElements[i]=="Interface":
                    Interface = theElements[i+1]
                    break
            staInfo["Interface"] = Interface
            #print("Interface = {}".format(Interface))
            address = None
            for i in range(0,len(theElements)):
                if theElements[i]=="addr":
                    address = theElements[i+1]
                    break
            staInfo["address"] = address
            #print("address = {}".format(address))
            links = {}
            for i in range(0,len(theElements)):
                if theElements[i]=="link" and theElements[i+1]=="ID":
                    linkID = theElements[i+2]
                    if theElements[i+3]=="link" and theElements[i+4]=="addr":
                        links[linkID] = {"address":theElements[i+5]}
                        try:
                            if theElements[i+6]=="channel":
                                links[linkID]["channel"] = theElements[i+7]
                                links[linkID]["freq"] = theElements[i+8].replace("(","")
                        except:
                            message = "nope"
            staInfo["links"] = links
            #print("links = {}".format(links))

        APinfo = {}
        theCommand = "iw {} link".format(Interface)
        api_endpoint = "http://{}:8383/exec?command={}".format(ipAddress,theCommand)
        r = requests.get(url=api_endpoint)
        theJson = json.loads(r.text)
        if theJson["status"] == "OK":
            theResponse = theJson["stdout"]
            #print(theResponse)
            intermediateString = theResponse.replace("\n"," ").replace("\t"," ")
            intermediateString = " ".join(intermediateString.split())
            theElements = intermediateString.split(" ")
            #print(theElements)
            Connection = None
            for i in range(0,len(theElements)):
                if theElements[i]=="Connected" and theElements[i+1]=="to":
                    Connection = theElements[i+2]
                    break
            APinfo["Connection"] = Connection 
            SSID = None
            for i in range(0,len(theElements)):
                if theElements[i]=="SSID:":
                    SSID = theElements[i+1]
                    break
            APinfo["SSID"] = SSID
            links = {}
            for i in range(0,len(theElements)):
                if theElements[i]=="Link":
                    linkID = theElements[i+1]
                    if theElements[i+2]=="BSSID":
                        links[linkID] = {"bssid":theElements[i+3]}
                        if theElements[i+4]=="freq:": links[linkID]["freq"] = theElements[i+5]
            APinfo["links"] = links
            MLD = None
            for i in range(0,len(theElements)):
                if theElements[i]=="MLD":
                    MLD = theElements[i+1]
                    break
            APinfo["MLD"] = MLD

        myObject = {"staInfo":staInfo, "APinfo":APinfo}
        
    #print(myObject)
    return myObject

