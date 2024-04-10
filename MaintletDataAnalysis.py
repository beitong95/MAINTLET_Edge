#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian 
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  02/06/2023
#  @description    :  Maintlet Anomaly Detector Module
#===========================================================================

# todo add timer in this module
# todo add more info in the mqtt message

import cv2
import os
from MaintletConfig import experimentConfig, pathNameConfig, recordingConfig, deviceHeader, WiFiIP, HTTPPort, alertSystemURL, safezoneDuration, trainDuration, MessageType, when2Alert, alertSystemEnable, sendFileAnyway
from MaintletLog import logger
import numpy as np
import scipy.io.wavfile as wav
import librosa
import librosa.display
import pandas as pd 
import more_itertools as mit
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from MaintletNetworkManager import MaintletPayload
from MaintletGainControl import gainControl, channelNames
import requests
import pyprctl
import psutil


###############################
### some initialization
###############################
recordFileDuration = experimentConfig['recordFileDuration'] # unit s
recordInterval = experimentConfig['recordInterval'] # unit s
recordPeriod = recordInterval + recordFileDuration

AS_period = recordPeriod
safezone_duration = safezoneDuration # unit S
safezone_AS_count = int(safezone_duration / AS_period)
train_duration = trainDuration # unit S
train_AS_count = int(train_duration / AS_period)
step = 1
safezone_check_step = 1 
safezone_check_length = safezone_AS_count
min_check_length = 1
max_check_length = safezone_AS_count
safezone_outter_n_std = 3
safezone_inner_n_std = 3
safezone_detect_n_std = 3
mean_window_step = 1 
mean_std_multiplier = 3 
ewma_duration = 30
min_EWMA_window = int(ewma_duration / AS_period)

frameSize = (8, 8)
minMelSpec = -70
maxMelSpec = 30

sr = recordingConfig['samplingRate']
n_mels = 64
n_fft = 2048
hop_length = 512
power = 2.0

as_state_train = 0
as_state_test = 1

isPlot = False

class MaintletDataAnalysis:
    def __init__(self, networkManager):
        self.networkManager = networkManager
        self.tmpFolderPath = pathNameConfig['tmpFolderPath']
        # clean up the tmp folder
        os.system(f"rm {self.tmpFolderPath}/*.mp4 > /dev/null 2>&1")
        os.system(f"rm {self.tmpFolderPath}/*.avi > /dev/null 2>&1")
        self.state = as_state_train
        self.recordFilePathList = []
        self.anomalyScores = []
        self.anomalyScoresForTraining = []
        self.labels = []
        self.safezones = {}
        self.referenceFilePath = ""
        self.referenceSpectrogram = ""
        self.frameSequenceTemplate = ""
        self.counter = 0
        self.key = 0
        self.safezone_check_length = safezone_AS_count
        self.outputPath = pathNameConfig['outputFolderPath']
        self.curFilePath = ''
        self.curFileName = ''
        self.rawDataToPlot = ''
        self.spectrogramToPlot = ''
        self.channel = 0
        # for plots
        if isPlot:
            self.means_x = []
            self.means = []
            self.train_stds_x = []
            self.train_stds = []
            self.test_stds_x = []
            self.test_stds = []

    def _loadData(self, filePath):
        self.curFilePath = filePath
        self.curFileName = filePath.split('/')[-1].split('.wav')[0]
        data, _ = librosa.load(filePath, sr=sr, mono=False)
        dataCh1 = data[self.channel, :]
        self.rawDataToPlot = dataCh1
        return dataCh1    

    def _setReferenceData(self, data):
        testDataCh1 = data
        # make spectrogram
        testMelSpectrogram = librosa.feature.melspectrogram(y=testDataCh1, sr=sr, n_mels=64, n_fft=n_fft, hop_length=hop_length)
        # expected shape should be (?, 64)
        testMelSpectrogram = librosa.power_to_db(testMelSpectrogram).T
        # reshape
        testFrameSequence = np.reshape(testMelSpectrogram, (testMelSpectrogram.shape[0], frameSize[0], frameSize[1]))
        self.frameSequenceTemplate = np.zeros((testMelSpectrogram.shape[0]*2,frameSize[0], frameSize[1]))
        for i in range(0,testMelSpectrogram.shape[0]*2,2):
            self.frameSequenceTemplate[i,:,:] = testFrameSequence[int(i/2),:,:]

    def _prepareFrameSequence(self, data):
        # todo later we will change the algorithm from monochannel to multichannel
        testDataCh1 = data
        # make spectrogram
        testMelSpectrogram = librosa.feature.melspectrogram(y=testDataCh1, sr=sr, n_mels=64, n_fft=n_fft, hop_length=hop_length)
        # expected shape should be (?, 64)
        testMelSpectrogram = librosa.power_to_db(testMelSpectrogram).T
        
        self.spectrogramToPlot = testMelSpectrogram.T

        # reshape
        testFrameSequence = np.reshape(testMelSpectrogram, (testMelSpectrogram.shape[0], frameSize[0], frameSize[1]))

        frameSequence = self.frameSequenceTemplate.copy()
        for p in range(1,len(testFrameSequence)*2,2):
            frameSequence[p,:,:] = testFrameSequence[int(p/2),:,:]
        
        return frameSequence

    def _videoCompression(self, data):
        """ anomaly scoring """
        out = cv2.VideoWriter(f"{self.tmpFolderPath}/test.avi",cv2.VideoWriter_fourcc(*'RGBA'), 60, frameSize, 0)

        data = ((data - minMelSpec) / (maxMelSpec - minMelSpec)) * 255
        data = data.astype(np.uint8)

        for s in data:
            out.write(s)
        out.release()

        originalSize = os.path.getsize(f"{self.tmpFolderPath}/test.avi")

        os.system(f"ffmpeg -i {self.tmpFolderPath}/test.avi -c:v libx264 -preset ultrafast {self.tmpFolderPath}/test.mp4 > /dev/null 2>&1")
        compressedSize = os.path.getsize(f"{self.tmpFolderPath}/test.mp4")
        # we need to remove tmp files 
        os.system(f"rm {self.tmpFolderPath}/*.mp4 > /dev/null 2>&1")
        os.system(f"rm {self.tmpFolderPath}/*.avi > /dev/null 2>&1")

        return originalSize, compressedSize

    def _getScore(self, data):
        frameSequence = self._prepareFrameSequence(data=data)
        originalSize, compressedSize = self._videoCompression(frameSequence)
        anomalyScore = compressedSize / originalSize
        return anomalyScore

    def _classification(self):
        # algorithm 2
        prevLabel = self.labels[-1]
        current_anomaly_score = self.anomalyScores[-1]
        
        # algorithm 3-4
        curLabel = -1
        test_end = len(self.anomalyScores)
        test_start = test_end - min_EWMA_window
        window = self.anomalyScores[test_start:test_end]
        ewma = self._ewma(window)
        if isPlot:
            self.means.append(ewma)
            self.means_x.append(self.counter - 2)

        # check if it is in stable zone
        # algorighm 5-14
        for index in sorted(list(self.safezones.keys())):
            safezone = self.safezones[index]
            # this safezone has ended
            if safezone[-1] < self.counter:
                continue
            innerUpperTh = safezone[1]
            innerLowerTh = safezone[0]
            mean = (innerUpperTh + innerLowerTh) / 2
            if ewma < innerUpperTh and ewma > innerLowerTh:
                if prevLabel == -1 and ewma > mean:
                    continue
                curLabel = index
                break  
        
        # alorithm 15-20
        if prevLabel > 0:
            # check if the current value is way out of range of the cloest stable zone 
            outerUpperTh = self.safezones[prevLabel][4]
            outerLowerTh = self.safezones[prevLabel][3]
            if current_anomaly_score > outerUpperTh or curLabel == -1:
                curLabel = -1
                # normal to abnormal, we will assume in the near future there is no safezone
                self.safezone_check_length = min_check_length

        # algorithm 21-27
        safezone_index = -1
        if curLabel == -1 and safezone_AS_count == self.safezone_check_length:
            safezone_check_array = self.anomalyScores[-self.safezone_check_length:][::-1]
            std = np.std(safezone_check_array)
            if isPlot:
                self.test_stds_x.append(self.counter-2)
                self.test_stds.append(std)
            logger.debug(f"std: {std:1.5f}. th: {self.safezone_std_th}")
            if std < self.safezone_std_th:
                logger.debug("build new safezone")
                # we can add a new stable zone
                safezone = self._buildSafezone(safezone_check_array)  
                safezone_index = self._insertSafezone(safezone)
                if safezone_index > 0:
                    curLabel = safezone_index
                else:
                    # we failed to install the stable zone
                    pass

        self.safezone_check_length = min(self.safezone_check_length+safezone_check_step, safezone_AS_count)
        isBuildSafezone = False if safezone_index < 0 else True
        return curLabel, isBuildSafezone 

    def _ewma(self, data):
        return pd.DataFrame(data).ewm(span=len(data)).mean().values.flatten()[-1]
    
    def _buildSafezone(self, train_samples):
        train_means = []
        start = 0
        end = min_EWMA_window
        while end <= len(train_samples):
            window = train_samples[start:end]
            train_means.append(self._ewma(window))
            start += mean_window_step
            end += mean_window_step
        train_means = np.array(train_means)

        safezone = [np.mean(train_means) - np.std(train_means) * safezone_inner_n_std, 
                   np.mean(train_means) + np.std(train_means) * safezone_inner_n_std, 
                   self.counter, 
                   np.mean(train_samples) - np.std(train_samples) * safezone_outter_n_std, 
                   np.mean(train_samples) + np.std(train_samples) * safezone_outter_n_std, train_means, train_samples, 999999]
        return safezone
                                      
    def _getKey(self):
        self.key += 1
        return self.key
                                                              
    def _insertSafezone(self, newSafezone):
        curKey = self._getKey()
        keys = sorted(list(self.safezones.keys()))
        check = True
        for key in keys:
            safezone = self.safezones[key]
            if safezone[-1] < self.counter:
                continue
            if (safezone[1] > newSafezone[1] and safezone[0] < newSafezone[1]) or (safezone[1] > newSafezone[0] and safezone[1] < newSafezone[1]) or (safezone[1] < newSafezone[1] and safezone[0] > newSafezone[0]):
                self.safezones[key][-1] = self.counter
            elif (safezone[1] > newSafezone[1] and safezone[0] < newSafezone[0]):
                check = False
                break
            else:
                pass
        if check == True:
            self.safezones[curKey] = newSafezone
            return curKey
        else:
            return -1
    
    def _calculateThresholds(self):
        # calculate std thresold of safezone 
        start = 0
        end = safezone_AS_count
        safezone_stds = []
        while end <= len(self.anomalyScoresForTraining):  
            window = self.anomalyScoresForTraining[start:end]
            std = np.std(window)
            safezone_stds.append(std)
            start += 1
            end += 1
            if isPlot:
                self.train_stds_x.append(self.counter-2)
                self.train_stds.append(std)
        self.safezone_std_th = np.mean(safezone_stds) + np.std(safezone_stds) * safezone_detect_n_std
        self.safezone_std_th = 1.05 * self.safezone_std_th
        logger.debug(f"safezone_std_th = {self.safezone_std_th}")
        # build the first safe zone, start from 1
        safezone = self._buildSafezone(self.anomalyScoresForTraining)  
        self._insertSafezone(safezone)
        
        # print(self.safezones)
                                      
    def _anomalyDetection(self, data):
        isBuildSafezone = False
        anomalyScore = -1
        label = -999
        anomalyScore = 0
        if self.counter == 1:
            # only get the reference frame
            self._setReferenceData(data)
        elif self.counter > 1 and self.counter <= train_AS_count:
            # training
            anomalyScore = self._getScore(data)
            self.anomalyScores.append(anomalyScore)
            self.anomalyScoresForTraining.append(anomalyScore)
            if self.counter == train_AS_count:
                self._calculateThresholds()
                isBuildSafezone = True
            label = 1
        elif self.counter > train_AS_count:
            # testing
            if self.counter == train_AS_count + 1:
                self.state = as_state_test
            anomalyScore = self._getScore(data)
            self.anomalyScores.append(anomalyScore)
            label, isBuildSafezone = self._classification()
        # skip the first label (referenece data)
        if label != -999:
            self.labels.append(label)
        logger.error(f"counter = {self.counter}, anomalyScore = {anomalyScore: 1.5f}, state = {'Train' if self.state == as_state_train else 'Test'}, label = {'0' if label > 0 or label == -999 else '1'}")
        return isBuildSafezone, anomalyScore, 0 if label > 0 or label == -999 else 1
   
    def _basicAnalysis(self, data):
        std = np.std(data)
        range = np.ptp(data)
        _max = np.max(data)
        _min = np.min(data)
        absMax = max(_max, _min)
        rms = np.sqrt(np.mean(data**2))
        # send range to autogaincontrol
        # send these data to network handler
        logger.info(f"std = {std}, range = {range}")
        return std, range, absMax, rms


    def plot(self):
        pass

    def _getSetupImageAddress(self):
        return "setup.png", f"http://{WiFiIP}:{HTTPPort}/pics/setup.png", "./pics/setup.png"
    
    def _getAnomalyScoreImageAddress(self):
        ASPlot = self.anomalyScores[-100:]
        fig, ax = plt.subplots()
        ax.plot(ASPlot)
        ax.set_xlabel("Anomaly Score Index")
        ax.set_ylabel("Anomaly Score")
        plt.close(fig)
        imageName = f"anomalyScore_{self.curFileName}".replace(':', '')
        imagePath = f"{self.outputPath}/{imageName}.png"
        fig.savefig(imagePath, bbox_inches='tight')
        return imageName + '.png', f"http://{WiFiIP}:{HTTPPort}/{imagePath}", imagePath
    
    def _getRawDataImageAddress(self):
        fig, ax = plt.subplots()
        librosa.display.waveplot(self.rawDataToPlot,sr=sr, ax=ax, offset=1)
        ax.set_xlabel("Offset Time (S)")
        ax.set_ylabel("Amplitude")
        plt.close(fig)
        imageName = f"rawData_{self.curFileName}".replace(':', '')
        imagePath = f"{self.outputPath}/{imageName}.png"
        fig.savefig(imagePath, bbox_inches='tight')
        return imageName + '.png', f"http://{WiFiIP}:{HTTPPort}/{imagePath}", imagePath
    
    def _getSpectrogramImageAddress(self):
        fig, ax = plt.subplots()
        img = librosa.display.specshow(self.spectrogramToPlot, x_axis='time',
                                y_axis='mel', sr=sr,
                                fmax=int(sr/2), ax=ax)
        ax.set_xlabel("Offset Time (S)")
        ax.set_ylabel("Frequency (Hz)")
        plt.close(fig)
        imageName = f"spectrogram_{self.curFileName}".replace(':', '')
        imagePath = f"{self.outputPath}/{imageName}.png"
        fig.savefig(imagePath, bbox_inches='tight')
        return imageName + '.png', f"http://{WiFiIP}:{HTTPPort}/{imagePath}", imagePath

    def getTimeFromFileName(self, filename):
        """sample file name: 03_06_2023_14_45_03_079359_e4:5f:01:5a:15:9c.wav"""
        return filename.split(':')[0][:-3]

    def run(self, fileSystemToDataAnalysisQ, networkingOutQ):

        # assign cpu
        process = psutil.Process()
        process.cpu_affinity([0])

        pyprctl.set_name("DataAnalysis")

        try:
            while True:
                filePath = fileSystemToDataAnalysisQ.get() # if there is no new file, we will block here
                self.counter += 1
                data = self._loadData(filePath=filePath)
                # get some basic analysis results
                std, range, absMax, rms = self._basicAnalysis(data=data)
                # gain control
                #channelName = channelNames[0]
                #gainControl(absMax, channelName)
                if experimentConfig['enableDataAnalysis']:
                    isBuildSafezone, anomalyScore, label = self._anomalyDetection(data=data)
                    prevLabel = self.labels[-1] if len(self.labels) > 0 else 0
                    tt = self.getTimeFromFileName(self.curFileName)
                    payload = {}
                    if when2Alert == -1:
                        if prevLabel == 0 and label == 1:
                            # send alert
                            if alertSystemEnable:
                                payload = self.prepareAlertPayload()
                                networkingOutQ.put(payload)

                        payload = self.preparePayload(std=std, rms=rms, _range=range, anomalyScore=anomalyScore, label = label, isBuildSafezone = isBuildSafezone, filePath=filePath, tt = tt, sensor=self.channel)
                    else:
                        # simulation
                        if self.counter < when2Alert:
                            label = 0
                            payload = self.preparePayload(std=std, rms=rms, _range=range, anomalyScore=anomalyScore, label = label, isBuildSafezone = isBuildSafezone, filePath=filePath, tt = tt, sensor=self.channel)
                        elif self.counter == when2Alert:
                            if alertSystemEnable:
                                payload = self.prepareAlertPayload()
                                networkingOutQ.put(payload)
                            label = 1
                            payload = self.preparePayload(std=std, rms=rms, _range=range, anomalyScore=anomalyScore, label = label, isBuildSafezone = isBuildSafezone, filePath=filePath, tt = tt, sensor=self.channel)
                        elif self.counter < when2Alert + 5:
                            label = 1
                            payload = self.preparePayload(std=std, rms=rms, _range=range, anomalyScore=anomalyScore, label = label, isBuildSafezone = isBuildSafezone, filePath=filePath, tt = tt, sensor=self.channel)
                        else:
                            label = 0
                            payload = self.preparePayload(std=std, rms=rms, _range=range, anomalyScore=anomalyScore, label = label, isBuildSafezone = isBuildSafezone, filePath=filePath, tt = tt, sensor=self.channel)

                    networkingOutQ.put(payload)
        except KeyboardInterrupt:
            logger.error(f"MaintletAnomalyDetector KeyboardInterrupt")

    def prepareAlertPayload(self):
        # Message type 1
        # Type: alert to Janam

        payload = {}
        payload['type'] = MessageType.ALERT

        # later we will replace alertMeta to an ID
        alertMeta = {}
        alertMeta['location'] = deviceHeader['location']
        alertMeta['model'] = deviceHeader['pumpModel']
        alertMeta['pumpHours'] = 10
        alertMeta['connectedTool'] = deviceHeader['connectedTool']
        payload['metaData'] = alertMeta

        alertFiles = []
        imageName, httpAddress, imageAddress = self._getAnomalyScoreImageAddress()
        tempEntry = (imageName, imageAddress)
        alertFiles.append(tempEntry)
        imageName, httpAddress, imageAddress = self._getRawDataImageAddress()
        tempEntry = (imageName, imageAddress)
        alertFiles.append(tempEntry)
        imageName, httpAddress, imageAddress = self._getSpectrogramImageAddress()
        tempEntry = (imageName, imageAddress)
        alertFiles.append(tempEntry)
        payload['filesInfo'] = alertFiles
        return payload
    
    def preparePayload(self, std, rms, _range, anomalyScore, label, isBuildSafezone, filePath = "", tt = "", sensor = 0):
        """ we load everything here """
        payload= {}
        payload['std'] = str(round(std,3))
        payload['range'] = str(round(_range,3))
        payload['anomalyScore'] = str(round(anomalyScore, 3))
        payload['label'] = label
        payload['buildSafezone'] = isBuildSafezone # later we will add more info for safezone
        payload['tt'] = tt
        payload['sensor'] = sensor
        payload['pump'] = deviceHeader['pumpModel'] # as pump id
        payload['isTest'] = (self.state == as_state_test)
        payload['rms'] = str(round(rms,3))

        # other algorithm results




        if label == 1 or sendFileAnyway:
            messageType  = MessageType.ALERTTRACKING 
            payload['filePath'] = filePath 
            payload = MaintletPayload(topic=messageType.value, format='dict_wavFile', payload=payload)
        else:
            messageType = MessageType.NORMAL
            payload = MaintletPayload(topic=messageType.value, format='dict', payload=payload)
        return payload
