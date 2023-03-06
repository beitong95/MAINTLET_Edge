import requests
alertSystemURL = f"http://10.193.199.26:8000/send-email"
alert = {}
alert['location'] = '123'
alert['model'] = '345'
alert['pumpHours'] = 10
alert['connectedTool'] = '678'
x = requests.get(alertSystemURL, json = alert)
