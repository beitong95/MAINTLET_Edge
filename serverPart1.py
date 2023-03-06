#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  02/01/2023
#  @description    :  A class for handling network operations (connection, disconnection, send, receive)
#===========================================================================

import paho.mqtt.client as paho
import time
import threading
from threading import Lock
from MaintletLog import logger
import os
import subprocess 
import traceback
import logging
# here we use the global variable messageQueue instead of an instance messageQueue which needs us to pass the network manager around
from MaintletMessage import *
from MaintletConfig import deviceHeader, deviceMac
import queue
import json


"""
Format for mqtt message

To server:
topic: MAINTLET/send/<deviceMac>/<format>/<messageTopic>
message: payload

From server:
topic: MAINTLET/receive/<deviceMac>/<messageTopic>
"""
replyTopic =  f"MAINTLET/send/#"

class MaintletNetworkManager:
    """
    Provide the following service
    1. MQTT
    TODO: Automatically reconnect after connection failure
    """    
    def __init__(self):
        # a flag for stopping threads
        self.stopThread = False
        self.mqttInMessageQ = queue.Queue(maxsize=-1)

    def leave(self):
        # stop MQTT
        # it will return MQTT_ERR_NO_CONN if we are trying to disconnect a client without connection
        self.client.disconnect()
        self.stopThread = True

    def connectMQTT(self, deviceMac, brokerIP, qos):
        """
        Connect to a MQTT broker

        Args:
            deviceMac (str): the device mac address used as client id 
            brokerIP (str): the broker IP address
            qos (int): the quality of service of the MQTT
            on_publish (func): handler when a message is published
            on_message (func): handler when receive a message
        """
        self.deviceMac = deviceMac
        self.MQTTBrokerIP = brokerIP
        self.MQTTQos = qos
        self.MQTTPort = 1883
        self.broker = brokerIP

        self.client = paho.Client(client_id=self.deviceMac+"_test")
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        self.client.on_message = self.on_message
        # if connect is failed, it will automatically reconnect
        self.client.connect(self.broker, self.MQTTPort)
        self.client.loop_start()

    def on_message(self, client, userdata, msg):
        print(f"""
Client: {client._client_id.decode("utf-8") }
Topic : {str(msg.topic)}
Msg   : {str(msg.payload)}""")
        self.mqttInMessageQ.put(msg)

    def on_publish(self, client, userdata, mid):
        logger.debug(f"""
Client: {client._client_id.decode("utf-8") }
Mid   : {str(mid)}""")
        # handle when message or file is successfully published
    
    def on_connect(self, client, userdata, flags, rc):
        """
        Common on_connect callback
        1. Print out the result code
        2. Subscribe reply channel
        """        
        logger.warning(f"Connected to Server: {self.MQTTBrokerIP} with result code {str(rc)}")
        # subscribe to the replyTopic
        if replyTopic != "":
            print(replyTopic)
            self.client.subscribe(replyTopic, 2)
    
    def _handleMessage(self, msg):
        topic = msg.topic
        print(topic)
        payload = msg.payload
        topicTokens = topic.split('/')
        macAddress = topicTokens[2]
        format = topicTokens[3]
        messageTopic = topicTokens[4]
        if format == 'message':
            print(f"receive message = {payload.decode('utf-8')}, from {macAddress} for {messageTopic}")
        elif format == 'dict':
            print(f"receive message = {json.loads(payload)}, from {macAddress} for {messageTopic}")
        elif format == 'wavFile':
            f = open('./testFolder/receive.wav', 'wb')
            f.write(payload)
            f.close()
            print(f"receive audiofile, from {macAddress} for {messageTopic}")
        elif format == 'dict_wavFile':
            payload = json.loads(payload)
            filePath = payload['filePath']
            fileName = filePath.split('/')[-1]
            wavFilePayload = bytes(payload['wavFile'], encoding='utf8')
            f = open(f"./testFolder/{fileName}", 'wb')
            f.write(wavFilePayload)
            f.close()
            print(f"receive audiofile, from {macAddress} for {messageTopic}")



    def run(self):
        """ start a loop for (1) mqtt (2) handling message """
        try:
            while True:
                msg = self.mqttInMessageQ.get()
                self._handleMessage(msg)
        except KeyboardInterrupt:
            logger.error("User Press Ctrl-C") 

#===========================================================================
#                            TEST CODE
# 1. Run "mosquitto_sub -h 91.121.93.94 -t MAINTLET/#&"" in any server installed mosquitto_client
# 2. Run 'MaintletNetworkManager'
# 3. You should see 'hi' on your server terminal
# 4. Run "mosquitto_pub -h 91.121.93.94 -t MAINTLET/11:22 -m '123'"
# 5. You should see the topic and payload on your local terminal
#===========================================================================
if __name__ == '__main__':
    deviceMac = '11:22'
    brokerIP = '130.126.137.48'   # test.mosquitto.org
    qos = 2
    networkManager = MaintletNetworkManager()
    networkManager.connectMQTT(deviceMac=deviceMac, brokerIP=brokerIP, qos=qos)
    networkManager.run()
    