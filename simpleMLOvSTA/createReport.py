import sys
import json
import os
import requests
import base64
import pprint
import time
import math
import re
pp = pprint.PrettyPrinter(indent=4)

from pathlib import Path

# sd2Utils.py and globalsfile.py live one directory above this file. The automation script
# already adds that path (via sys.path.append(directory_name + '../')) before importing
# createReport, but running this file directly from the command line skips that step -- so add
# it here too, based on this file's own location rather than the current working directory.
_thisDir = os.path.dirname(os.path.abspath(__file__))
_parentDir = os.path.abspath(os.path.join(_thisDir, '..'))
if _parentDir not in sys.path:
	sys.path.append(_parentDir)

# MUST HAVE. Contains functions used in this script and other helpful functions
import sd2Utils
import globalsfile

def _findHeader(headers, mustContainAll):
	"""Return the first header string containing every substring in mustContainAll, or None."""
	for h in headers:
		if all(sub in h for sub in mustContainAll):
			return h
	return None

def _findHeaderWithPrefix(headers, prefix, mustContainAll):
	"""Like _findHeader, but also requires the header to start with an exact prefix.
	Used for per-endpoint lookups, since e.g. "Pal Endpoint 1 " must NOT match headers
	for endpoint 10-16 (a plain substring check on "Pal Endpoint 1" would)."""
	for h in headers:
		if h.startswith(prefix) and all(sub in h for sub in mustContainAll):
			return h
	return None

def _findNumberedEntities(headers, entityPrefix):
	"""Scan headers for '<entityPrefix><N> ' (e.g. 'Pal Endpoint 3 ...' or 'Traffic Pair 12 ...')
	and return the sorted, de-duplicated list of N's found. Lets the report adapt to however many
	traffic pairs/radio endpoints a given test actually configured, rather than a fixed count."""
	pattern = re.compile(r'^' + re.escape(entityPrefix) + r'(\d+) ')
	found = set()
	for h in headers:
		m = pattern.match(h)
		if m:
			found.add(int(m.group(1)))
	return sorted(found)

def _extractSeries(dataSet, timeHeader, valueHeader, t0):
	"""Pull {x,y} points for one column, skipping non-numeric and non-finite (nan/inf) values."""
	points = []
	if not valueHeader:
		return points
	for row in dataSet:
		tVal = row.get(timeHeader)
		yVal = row.get(valueHeader)
		try:
			tVal = float(tVal)
			yVal = float(yVal)
		except (TypeError, ValueError):
			continue  # skips "#N/A" and similar non-numeric entries
		if not math.isfinite(tVal) or not math.isfinite(yVal):
			continue  # skips "nan"/"inf"/"-inf" strings -- float() parses these without error
		points.append({"x": round(tVal - t0, 3), "y": yVal})
	return points

def _addTimeSeriesPlot(myReport, sectionTitle, yAxisLabel, series):
	"""series: list of (label, points, color) tuples. Skips empty series; skips the whole
	plot (with a log message) if none of the series have any data."""
	plotData = []
	for label, points, color in series:
		if len(points) == 0:
			print(">>> No data for series '{}' in plot '{}'; leaving it out.".format(label, sectionTitle))
			continue
		plotData.append({
			"label": label,
			"color": color,
			"width": 1,
			"radius": 0,
			"data": points,
			"fill": -1,
			"style": "solid"
		})
	if len(plotData) == 0:
		print(">>> No data available at all for plot: {}; skipping it entirely.".format(sectionTitle))
		return

	item = {
			"elementType": "section",
			"headingType": "h2",
			"headingContent": sectionTitle,
			"text": ""
	}
	myReport["Report"].append(item)

	item = {
			"elementType": "plot",
			"type": "scatter",
			"title": "",
			"xaxis": {"string": "Elapsed Time (s)"},
			"yaxis": {"string": yAxisLabel},
			"showTable": False,
			"plotWidth": "800px",
			"data": plotData
	}
	myReport["Report"].append(item)

def _runExpertAnalysis(ea_root, archiveFile):
	"""Run one archive through the zip2csv -> objectify -> crunch pipeline. Returns
	(headers, dataSet, crunchedData, notes, topLines) -- any of which may be None/empty on failure."""
	headers, dataSet, crunchedData, notes, topLines = None, None, None, {}, []
	try:
		with open(archiveFile, "rb") as f:
			encoded = base64.b64encode(f.read())

		api_endpoint = ea_root + "zip2csv"
		theResponse = requests.post(url=api_endpoint, data={'zip': encoded})
		theJson = json.loads(theResponse.text)
		if "error" in theJson:
			print(">>> zip2csv returned an error: {}".format(theJson["error"]))
		csv = theJson["csv"]

		api_endpoint = ea_root + "objectify"
		theResponse = requests.post(url=api_endpoint, data={'csv': csv})
		theJson = json.loads(theResponse.text)
		if "error" in theJson:
			print(">>> objectify returned an error: {}".format(theJson["error"]))
		headers = theJson["headers"]
		dataSet = theJson["dataSet"]
		topLines = theJson.get("topLines", [])

		# topLines carries the "# epMapping: ..." / "# tpMapping: ..." comment lines from the
		# original CSV, which is how crunch resolves real endpoint/traffic-pair names (epMap) --
		# without forwarding it, crunch defaults to an empty topLines and epMap never gets set.
		api_endpoint = ea_root + "crunch"
		theResponse = requests.post(url=api_endpoint, data={'headers': headers, 'dataSet': json.dumps(dataSet), 'topLines': json.dumps(topLines), 'run': 1})
		theJson = json.loads(theResponse.text)
		if "error" in theJson:
			print(">>> crunch returned an error: {}".format(theJson["error"]))
		crunchedData = theJson["crunchedData"]
		notes = theJson.get("Notes", {})
	except Exception as err:
		print(">>> Expert Analysis pipeline failed on {}: {}".format(archiveFile, err))
	return (headers, dataSet, crunchedData, notes, topLines)

def _endpointNamesFromTopLines(topLines):
	"""Parse the "# epMapping: Endpoint X is LABEL, X, LABEL" comment lines that Expert Analysis
	writes into the CSV (and returns to us via objectify's "topLines" field) directly in Python.
	This is done here instead of relying on crunchedData[a]["epMap"] (which crunch computes
	internally the same way) because that field is attached to a JS array object, and
	JSON.stringify() silently drops named properties attached to arrays -- it never survives the
	trip back to us over the /crunch REST response, regardless of what we send it.
	Returns {endpointNumber (1-indexed): name} for whichever endpoints have a resolved name."""
	names = {}
	flatLines = []
	for item in (topLines or []):
		if isinstance(item, list):
			flatLines.extend(item)
		else:
			flatLines.append(item)
	for line in flatLines:
		if not isinstance(line, str) or "epMap" not in line:
			continue
		parts = line.split(",")
		if len(parts) < 2:
			continue
		try:
			idx = int(parts[1].strip())  # 0-indexed, matching "Pal Endpoint idx+1"
		except ValueError:
			continue
		label = parts[2].strip() if len(parts) > 2 and parts[2].strip() not in ("", "undefined") else parts[1].strip()
		names[idx + 1] = label
	return names

def _addIterationPlots(myReport, headers, dataSet, topLines, colors):
	"""Builds exactly 6 full-size plots (no grid formatting) for one result archive:
	1. Throughput vs. Time -- every header with 'throughput' and '[mbps]' in its name, combined.
	2. Bits Per Second vs. Time (Mbps) -- RX and TX, for every radio endpoint, combined on one chart.
	3. MCS (Mode) vs. Time -- RX and TX, for every radio endpoint, combined on one chart.
	4. PHY Rate vs. Time -- RX and TX, for every radio endpoint, combined on one chart.
	5. Streams (Nss) vs. Time -- RX and TX, for every radio endpoint, combined on one chart.
	6. Bandwidth vs. Time -- RX and TX, for every radio endpoint, combined on one chart.
	Radio endpoints are labeled with their real name (from Expert Analysis' epMap) when available,
	falling back to "Pal Endpoint N" otherwise.
	"""
	epNames = _endpointNamesFromTopLines(topLines)

	timeHeader = None
	for h in headers:
		if h == "Server timestamp" or (h.startswith("Server timestamp") and "MS" not in h):
			timeHeader = h
			break
	if not timeHeader:
		for h in headers:
			if "Time" in h:
				timeHeader = h
				break

	if not timeHeader:
		print(">>> Could not find a time column; skipping all time-series plots for this archive.")
		return

	t0 = None
	for row in dataSet:
		try:
			t0 = float(row.get(timeHeader))
			if math.isfinite(t0):
				break
		except (TypeError, ValueError):
			continue
	if t0 is None:
		print(">>> Could not find a usable starting time value; skipping all time-series plots for this archive.")
		return

	colorIdx = [0]  # shared mutable counter so every series across a plot gets a distinct color
	def _nextColor():
		c = colors[colorIdx[0] % len(colors)]
		colorIdx[0] += 1
		return c

	# --- Plot 1: Throughput vs. Time -- every header with "throughput" and "[mbps]" in its name ---
	colorIdx[0] = 0
	series = []
	for h in headers:
		if "throughput" in h.lower() and "[mbps]" in h.lower():
			series.append((h, _extractSeries(dataSet, timeHeader, h, t0), _nextColor()))
	_addTimeSeriesPlot(myReport, "Throughput vs. Time", "Throughput (Mbps)", series)

	endpointNumbers = _findNumberedEntities(headers, "Pal Endpoint ")
	if not endpointNumbers:
		print(">>> No 'Pal Endpoint <N>' columns found; skipping bits-per-second/MCS/rate/streams/bandwidth plots.")
		return

	# --- Plot 2: Bits Per Second vs. Time -- RX and TX, every endpoint, one chart ---
	# Values come out of Expert Analysis in raw bps; converted to Mbps (divide by 1E6) for display.
	def _toMbps(points):
		return [{"x": p["x"], "y": p["y"] / 1E6} for p in points]

	colorIdx[0] = 0
	series = []
	for epNum in endpointNumbers:
		prefix = "Pal Endpoint {} ".format(epNum)
		epLabel = epNames.get(epNum, "Pal Endpoint {}".format(epNum))
		# Note: unlike the other PHY stats (which use fully-capitalized "RX"/"TX"), Expert
		# Analysis names this field with mixed case: "Rx Bits Per Second" / "Tx Bits Per Second".
		rxH = _findHeaderWithPrefix(headers, prefix, ["Rx Bits Per Second"])
		txH = _findHeaderWithPrefix(headers, prefix, ["Tx Bits Per Second"])
		series.append(("{} RX".format(epLabel), _toMbps(_extractSeries(dataSet, timeHeader, rxH, t0)), _nextColor()))
		series.append(("{} TX".format(epLabel), _toMbps(_extractSeries(dataSet, timeHeader, txH, t0)), _nextColor()))
	_addTimeSeriesPlot(myReport, "Bits Per Second vs. Time (Mbps)", "Mbps", series)

	# --- Plots 3-6: MCS / PHY Rate / Streams / Bandwidth vs. Time -- RX and TX, every endpoint ---
	def _combinedAcrossEndpoints(statSubstrings):
		colorIdx[0] = 0
		series = []
		for epNum in endpointNumbers:
			prefix = "Pal Endpoint {} ".format(epNum)
			epLabel = epNames.get(epNum, "Pal Endpoint {}".format(epNum))
			rxH = _findHeaderWithPrefix(headers, prefix, ["RX"] + statSubstrings)
			txH = _findHeaderWithPrefix(headers, prefix, ["TX"] + statSubstrings)
			series.append(("{} RX".format(epLabel), _extractSeries(dataSet, timeHeader, rxH, t0), _nextColor()))
			series.append(("{} TX".format(epLabel), _extractSeries(dataSet, timeHeader, txH, t0), _nextColor()))
		return series

	_addTimeSeriesPlot(myReport, "MCS (Mode) vs. Time", "MCS Index", _combinedAcrossEndpoints(["MCS", "Mode"]))
	_addTimeSeriesPlot(myReport, "PHY Rate vs. Time", "PHY Rate (Mbps)", _combinedAcrossEndpoints(["Rate [Mbps]", "Mode"]))
	_addTimeSeriesPlot(myReport, "Streams (Nss) vs. Time", "Streams (Nss)", _combinedAcrossEndpoints(["Nss", "Mode"]))
	_addTimeSeriesPlot(myReport, "Bandwidth vs. Time", "Bandwidth (MHz)", _combinedAcrossEndpoints(["Bandwidth [MHz]", "Mode"]))

def main(directory_name,json_dir,ea_root=None):

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

	#Expert Analysis normally runs on port 8080 on the same box as script manager.
	if not ea_root:
		ea_root = "http://"+globalsfile.hostIpAddress+":8080/"
	if ea_root[len(ea_root)-1] != "/": ea_root += "/"

	#Grab the directory information as created by SM.
	if directory_name[len(directory_name)-1] != "/": directory_name += "/"
	dirFile = directory_name + "directories.json"
	try:
	    f = open(dirFile)
	    directoriesJson = json.load(f)
	    subDir = directoriesJson["subDirectory"]
	    splits = subDir.split("_")
	    runNumber = splits[0]
	    theName = directoriesJson["title"]
	    theTitle = theName.replace(" ","_")
	except:
	    theTitle = "No Name Found"
	    theName = theTitle.replace(" ","_")
	    runNumber = "0"

	print('>>> theTitle: ', theTitle)

	if json_dir[len(json_dir)-1] != "/": json_dir += "/"
	print('>>> createReport_main json_dir', json_dir)

	#For this test, pull the JSON information created.
	jsonFile = None
	for x in os.listdir(json_dir):
	    if "testresultlog" in x:
	            jsonFile = json_dir + x
	if jsonFile is None:
	    print(">>> No testresultlog JSON found in {}; cannot build a report.".format(json_dir))
	    return

	f = open(jsonFile)
	testResultLogJson = json.load(f)
	f.close()

	#Get all of the zip files in the json directory.
	#Exclude the CSV-only zip, the time-aligned ("-TAJ") zip, and anything with "taJSON" in the
	#name -- none of those is the full result archive that Expert Analysis' zip2csv endpoint
	#expects; they're alternate representations of the SAME data, not a separate test iteration.
	#Unlike other scripts, this one can produce MULTIPLE real result archives in a single run
	#(one per test iteration, named "..._0.zip", "..._1.zip", etc. by the main script's
	#totalTests loop), so we keep all of the real ones rather than just the most recent, and
	#report on each iteration separately.
	theZips = []
	for x in os.listdir(json_dir):
	    if ".zip" in x and "CSV" not in x and "-TAJ" not in x and "taJSON" not in x:
	            theZips.append(json_dir + x)
	theZips.sort()

	# Copy report image(s) to script-manager/storage
	#Verify where scriptManager is running
	api_endpoint = "http://"+globalsfile.hostIpAddress+":5678/exec?command=pwd"
	r = requests.get(url=api_endpoint)
	y = json.loads(r.text)
	scriptManagerLocation = y["stdout"]
	scriptManagerLocation = scriptManagerLocation.replace("\n","")
	if scriptManagerLocation[len(scriptManagerLocation)-1] != "/": scriptManagerLocation += "/"
	print('>>> scriptManagerLocation: ', scriptManagerLocation)
	storageLocation = scriptManagerLocation+'storage/'
	print('>>> storageLocation: ', storageLocation)

	imageStorage = 'reportImages/'
	pathToImages = storageLocation+imageStorage
	print(">>> createReport: Copy report image(s) to ", pathToImages)
	if not os.path.exists(pathToImages):
		    os.makedirs(pathToImages)
	for file in os.listdir(directory_name):
		if ".png" in file or ".jpg" in file:
			command = 'cp ' + directory_name + file + ' ' + pathToImages + file
			os.popen(command)
			time.sleep(1)

	#Write a report
	myReport = {}
	myReport["Title"] = theTitle
	myReport["Report"] = []

	item = {
		    "elementType": "section",
		    "headingType": "h2",
		    "headingContent":"System Diagram",
		    "text": ""
	}
	myReport["Report"].append(item)

	imgPath = imageStorage+"STACK-MAX-Diagram.png"
	item ={
		    "elementType":"image",
		    "path":imgPath,
		    "alt":"STACK-MAX System Diagram",
		    "width":"800"
		    }
	myReport["Report"].append(item)

	item = {
		    "elementType": "section",
		    "headingType": "h2",
		    "headingContent":"Test Information Summary",
		    "text": ""
	}
	myReport["Report"].append(item)

	testInfo = testResultLogJson.get("testInfo", {})
	testname = testInfo.get("name", theTitle)
	new_testname = testname.replace("_", " ")
	from datetime import datetime
	now = datetime.now()
	dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
	fwString = ""
	palFw = testInfo.get("palFWversions", {})
	i = 0
	j = 0
	for key in palFw:
	    if "STApal" in key:
	        m = str(key)
	        new = m.replace("-STApal", "")
	        if i == 0 :
	            fwString = fwString + "STApal Version :<br>" + new + " :" + palFw[key] + "<br>"
	        else :
	            fwString = fwString + new + " :" + palFw[key] + "<br>"
	        i = i + 1
	    if "Pal-" in key:
	        if j == 0 :
	            fwString = "{} PAL Version :<br/> {} : {} <br/>".format(fwString,key, palFw[key])
	        else :
	            fwString = fwString + key + " :" + palFw[key] + "<br>"
	        j = j + 1

	item = {
		    "elementType": "table",
		    "type": "table",
		    "title": "",
		    "tableWidth": "700px",
		    "data": [
		        {
		            "data": [
		            "Spirent OCTOBOX Software Version",
		            "DUT Model Name",
		            "DUT Firmware Version",
		            "Pal/STApal Version",
		            "MLO Bands",
		            "vSTA Count",
		            "Total Run Time (HH:MM:SS)",
		            "Date and Time",
		            "Test Name"
		            ]
		        },
		        {
		            "data": [
		                testInfo.get("starDustVersion", ""),
		                testInfo.get("model", ""),
		                testInfo.get("revision", ""),
		                fwString,
		                ", ".join(testInfo.get("mloBands", [])),
		                testInfo.get("vstaCount", ""),
		                testResultLogJson.get("testRunTime", ""),
		                dt_string,
		                new_testname
		            ]
		        }
		    ]
	}
	myReport["Report"].append(item)

	item = {
		    "elementType": "section",
		    "headingType": "h2",
		    "headingContent":"Path to stored data",
		    "text": json_dir
	}
	myReport["Report"].append(item)

	item = {
		    "elementType": "section",
		    "headingType": "h2",
		    "headingContent":"Test Description",
		    "text": testInfo.get("description", "")
	}
	myReport["Report"].append(item)

	item = {"elementType": "pagebreak"}
	myReport["Report"].append(item)

	# #################### EXPERT ANALYSIS + PLOTS, PER TEST ITERATION #######################
	# This test can run its traffic multiple times in a single script invocation (the
	# "totalTests" loop in simpleMLOvSTA.py), producing one result archive per iteration. We
	# process each archive separately -- and label the plots by iteration if there's more than
	# one -- rather than concatenating unrelated runs into one misleading timeline.
	# There is no attenuation sweep in this test (no avgDataPost calls), so there are no
	# RvR-vs-attenuation plots here -- only the time-series plots below.

	if len(theZips) == 0:
		print(">>> No result archive zip found in {}; skipping Expert Analysis and all plots.".format(json_dir))
	else:
		multiIteration = len(theZips) > 1
		allAlerts = []
		for iterNum, archiveFile in enumerate(theZips):
			print(">>> Running Expert Analysis on archive: {}".format(archiveFile))
			(headers, dataSet, crunchedData, notes, topLines) = _runExpertAnalysis(ea_root, archiveFile)

			if notes and "Alerts" in notes:
				allAlerts.extend(["[Iteration {}] {}".format(iterNum, a) for a in notes["Alerts"]])

			if not headers or not dataSet:
				print(">>> No usable data from {}; skipping its plots.".format(archiveFile))
				continue

			if multiIteration:
				myReport["Report"].append({
					"elementType": "section", "headingType": "h1",
					"headingContent": "Test Iteration {}".format(iterNum), "text": ""
				})

			_addIterationPlots(myReport, headers, dataSet, topLines, colors)

		item = {
			"elementType": "section",
			"headingType": "h2",
			"headingContent": "Expert Analysis Alerts",
			"text": "\n".join(allAlerts) if allAlerts else "There are no Alerts to report."
		}
		myReport["Report"].append(item)

	print("{} JSON report is complete. {}".format(cGreen,cNormal))

	# Safety net: strip any non-finite floats (nan/inf/-inf) anywhere in the report.
	# json.dumps() will silently emit invalid "NaN"/"Infinity" tokens for these instead of
	# raising an error, and the HTML/Chart.js side then fails to parse it.
	def _sanitizeForJSON(obj):
		if isinstance(obj, float):
			return obj if math.isfinite(obj) else None
		elif isinstance(obj, dict):
			return {k: _sanitizeForJSON(v) for k, v in obj.items()}
		elif isinstance(obj, list):
			return [_sanitizeForJSON(v) for v in obj]
		else:
			return obj
	myReport = _sanitizeForJSON(myReport)

	#Generate the proper html for this report
	api_endpoint = "http://"+globalsfile.hostIpAddress+":5678/jsonToHtmlReport"
	data = {'json':json.dumps(myReport,indent=4)}
	r = requests.post(url=api_endpoint,data=data)
	y = json.loads(r.text)
	html = y["html"]

	print("{} JSON report has been converted to HTML. {}".format(cGreen,cNormal))

	#Verify where scriptManager is running
	api_endpoint = "http://"+globalsfile.hostIpAddress+":5678/exec?command=pwd"
	r = requests.get(url=api_endpoint)
	y = json.loads(r.text)
	scriptManagerLocation = y["stdout"]
	scriptManagerLocation = scriptManagerLocation.replace("\n","")
	storageLocation = scriptManagerLocation + "/" + "storage/"
	fileName = theName + "_" + runNumber + ".html"
	fullPath = storageLocation + fileName

	#Write out this html file
	f = open(fullPath, "w")
	f.write(html)
	f.close()

	print("{} HTML report has been written to {}. {}".format(cGreen,fullPath,cNormal))

	#Also, store the JSON formatted plot, and put a link to it in ReportList.json.
	jsonName = theName + ".json"
	plotPath = storageLocation + jsonName
	f = open(plotPath, "w")
	f.write(json.dumps(myReport,indent=3))
	f.close()

	jsonPath = storageLocation + "ReportList.json"
	try:	f = open(jsonPath, "r")
	except:	f = open(jsonPath, "w+")
	try:    currentList = json.load(f)
	except: currentList = {}
	f.close()
	currentList[fileName] = plotPath
	f = open(jsonPath, "w")
	f.write(json.dumps(currentList,indent=3))
	f.close()

	#Create a JSON file that will put a link to the previous file into script manager.
	jsonPlot = {}
	jsonPlot["reportLink"] = {
			"val": {"htmlLink": "http://"+globalsfile.hostIpAddress+":5678/storage/"+fileName},
			"label": "Report for " + theTitle + ", " + runNumber
	}
	jsonPlot["_editable"] = False
	f = open(directory_name+'TestReport-'+theTitle+ "_" + runNumber + '.json', "w")
	f.write(json.dumps(jsonPlot,indent=4))
	f.close()

	print("{} Link to HTML has been generated. {}".format(cGreen,cNormal))

#===
#Use this for debugging.  Otherwise, comment it out.
'''
directory_name = "./"
json_dir = "/home/octoscope/Documents/automationResults/2026-xx-xx_simpleMLOvSTA/1_2026-xx-xx_simpleMLOvSTA/"
main(directory_name,json_dir)
'''
