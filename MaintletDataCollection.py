#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  01/24/2023
#  @description    :  MAINTLET data collection module
#                        (1) record data with user-specified configurations and save recorded data in local file system. 
#                        (2) save meta data to local database (SQLite 3)
#===========================================================================

#===========================================================================
#                            Import Required Modules
#===========================================================================
import pyaudio # for reading data from audio interface
import wave # for saving audio data to WAV files
import time # for calculating running time
from datetime import datetime # for get current time
import numpy as np # for data processing
import copy
# multi-threading related
import subprocess 
import threading

# Some system modules
import sys
from gpiozero import CPUTemperature # get current CPU temperature 
import shutil
import os
from os.path import isfile, join
from os import listdir
import traceback

# Other Maintlet modules
from MaintletSensor import MaintletSensor
from MaintletTable import TableEntryForRecordedFile
from MaintletLog import logger
from MaintletError import *
from MaintletConfig import config 
from MaintletSharedObjects import timer
from MaintletDatabase import MaintletDatabase
from MaintletMessage import MaintletMessage
import MaintletGainControl
#============================= END OF IMPORT ==============================

class MaintletDataCollection():
    """ MAINTLET data collection class """

    def __init__(self, databaseHandler, networkHandler = -1):
        self.timer = timer # get the global timer
        self.config = config # get the config
        self.databaseHandler = databaseHandler # an object which handles all database related operations
        self.networkHandler = networkHandler # an object which handles all network/communication related operations

    def configAll(self):
        """ do all configurations """
        # create pyaudio obj
        self.createPyaudio()

        # setup shared configurations
        self.configCommon()
        # setup playback configurations
        if self.enablePlayback:
            self.configPlayback()
        # setup record configurations
        if self.enableRecording: 
            self.configRecord()
        self.table = self.craeteTableTemplate()

    def configCommon(self):
        """ Config shared configurations """
        #todo  All variables initialized with -1 has not been used in the system.  
        # Check what modules are enabled 
        self.enableRecording = self.config['recordingConfig']['enableRecording']
        self.enablePlayback = self.config['playbackConfig']['enablePlayback']
        self.enableNetwork = self.config['networkConfig']['enableNetwork']  # If false, all data will be stored locally

        # Init some variables for performance tracking
        self.cpuTemperature = CPUTemperature() # CPU temperature
        self.maxCpuTemp = 0
        self.diskPath = os.getcwd() # we want to know the remaining space of the disk mounted to the current folder
        self.remainingSpace = self.getCurrentRemainingDiskSpace() # remaining space control
        self.minimumSpace = 100  # Unit: MB

        # Init some variables for threads and processes
        self.stopThread = False # a flag for killing threads

        # Load configurations (SQLite3 database)
        self.databaseName = self.config['pathNameConfig']['databaseName']
        self.databasePath = self.config['pathNameConfig']['databasePath']
        self.tableName = self.config['pathNameConfig']['tableName']

        # Load configurations (folders)
        self.recordFolderPath = self.config['pathNameConfig']['recordFolderPath']

        # Load configurations (edge device information)
        self.deviceMac = self.config['deviceConfig']['deviceMac']
        self.deviceRAM = -1
        self.deviceDescription = self.config['deviceConfig']['deviceDescription']

        # Load configurations (networking)
        self.serverIP = self.config['networkConfig']['serverIP'] # storage server
        self.serverUsername = self.config['networkConfig']['serverUserName']
        self.MQTTQos = int(self.config['networkConfig']['MQTTQoS'])

        # Load configurations (experiment related)
        self.experimentName = self.config['experimentConfig']['experimentName']
        self.experimentDescription = self.config['experimentConfig']['experimentDescription']
        self.recordCount = int(self.config['experimentConfig']['recordCount'])
        self.recordFileDuration = int(self.config['experimentConfig']['recordFileDuration'])
        self.recordInterval = int(self.config['experimentConfig']['recordInterval'])

        # Load configurations (sensor)
        self.sensor1 = MaintletSensor(self.config['sensorConfig']['sensor1'])
        self.sensor2 = MaintletSensor(self.config['sensorConfig']['sensor2'])
        self.sensor3 = MaintletSensor(self.config['sensorConfig']['sensor3'])
        self.sensor4 = MaintletSensor(self.config['sensorConfig']['sensor4'])
        self.sensor5 = MaintletSensor(self.config['sensorConfig']['sensor5'])
        self.sensor6 = MaintletSensor(self.config['sensorConfig']['sensor6'])
        self.sensors = [self.sensor1, self.sensor2, self.sensor3, self.sensor4, self.sensor5, self.sensor6]
        
        # After the device is rebooted, starting data collection module (driver or portAudio, we do not know the reason) will fail in the first several trials. 
        # Here we detect these failures and automatically retry to start the data collection module. 
        # We name this operation as autoRetry
        self.prevADCTime = -1

#===========================================================================
#                            Utility Methods
#===========================================================================

    def getCurrentRemainingDiskSpace(self):
        """ Get the remaining disk space in MB """
        stat = shutil.disk_usage(self.diskPath)
        return(round(stat.free/1024/1024,2))

    def getAllFilepaths(self, data_dir):
        """ Get all absolute file paths in a directory and sort them in alphabetical order """
        filepaths = []
        filepaths = sorted([join(data_dir, f) for f in listdir(data_dir) if isfile(join(data_dir, f)) and 'wav' in f])
        return filepaths

    def getOldestFilepath(self, filepaths):
        """ Get the latest file's filepath given filepaths sorted by create time in descending order """
        return filepaths[0]

    
    def getDeviceIndex(self, targetDeviceName):
        """
        get the system index given index name or part of the name

        Args:
            targetDeviceName (str): output device: ac101; input device: seeed

        Returns:
            int: -1 means fail, other number is the index of the device
        """
        info = self.pyaudio.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')

        for i in range(0, numdevices):
            deviceName = self.pyaudio.get_device_info_by_host_api_device_index(0, i).get('name')
            print(deviceName)
            if targetDeviceName in deviceName:
                print("Device name", deviceName, "id -", i)
                return i

        raise GetDeviceIndexError(targetDeviceName)
    
    def flipDoubleBufferSelector(self):
        """ Flip the doubleBufferSelector after one buffer is full. """        
        self.doubleBufferSelector = 1 - self.doubleBufferSelector

    def safeQuery(self, variable, default = -1):
        """
        Dereference the variable after checking if it exists in this instance
        Sometimes some configs might not be initialized

        Args:
            variable (string): name of the variable
            default (any, optional): the default value. Defaults to -1.

        Returns:
            The value of the variable
        """

        return eval(f"self.{variable}") if hasattr(self, variable) else default

    def craeteTableTemplate(self):
        """ create a template based on configs """
        table = TableEntryForRecordedFile()
        table.duration = self.safeQuery("recordFileDuration")
        table.samplingRate = self.safeQuery("samplingRate")
        table.sampleWidth = self.safeQuery("sampleWidth")
        table.recordChunk = self.safeQuery("recordChunk")
        table.playbackSamplingRate = self.safeQuery("playbackRate")
        table.playbackSampleWidth = self.safeQuery("playbackSampleWidth")
        table.playbackChunk = self.safeQuery("playChunk")
        table.playbackFileNames = ';'.join(self.safeQuery("self.playbackAudioFilesPathList", default=['-1']))
        table.sensor1Type = self.safeQuery("sensor1").type
        table.sensor1Location = self.safeQuery("sensor1").location
        table.sensor2Type = self.safeQuery("sensor2").type
        table.sensor2Location = self.safeQuery("sensor2").location
        table.sensor3Type = self.safeQuery("sensor3").type
        table.sensor3Location = self.safeQuery("sensor3").location
        table.sensor4Type = self.safeQuery("sensor4").type
        table.sensor4Location = self.safeQuery("sensor4").location
        table.sensor5Type = self.safeQuery("sensor5").type
        table.sensor5Location = self.safeQuery("sensor5").location
        table.sensor6Type = self.safeQuery("sensor6").type
        table.sensor6Location = self.safeQuery("sensor6").location
        table.volumes = ','.join(str(e) for e in MaintletGainControl.currentVolumes)
        table.experimentName = self.safeQuery("experimentName")
        table.experimentDescription = self.safeQuery("experimentDescription")
        table.deviceMac = self.safeQuery("deviceMac")
        table.deviceDescription = self.safeQuery("deviceDescription")
        table.tableName = self.safeQuery("tableName")
        table.transactionStatus = 'Unfinished'
        table.filename = "recordOutputFileName"
        table.recordTime = "recordTime"
        table.key = f"{table.recordTime}_{table.deviceMac}"
        return table

    def createTableEntry(self, tableTemplate):
        """ create database entry """ 
        table = copy.deepcopy(tableTemplate)
        return table
    
    def createPyaudio(self):
        """ Create the PyAudio object"""
        self.pyaudio = pyaudio.PyAudio()

    def terminatePyaudio(self):
        """ Terminate the PyAudio object """
        self.pyaudio.terminate()

    def start(self):
        """ Start the loop for record or playback or both"""
        if self.enableRecording:
            self.openRecordStream()
        if self.enablePlayback:
            self.openPlayStream()
        while True and self.stopThread == False:
            try:
                time.sleep(0.5)
                # track some statistics
                # cpu temperature
                temp = self.cpuTemperature.temperature
                if temp > self.maxCpuTemp:
                    self.maxCpuTemp = temp
                # RAM ... 
                # log or send results to server
                logger.info(f"CPU Temperature {temp}, MAX Temp {self.maxCpuTemp}")

            except KeyboardInterrupt:
                # if use want to leave, we close everything and exit
                print("User press CTRL-C")
                self.closeAndExit()
        
    def closeAll(self):
        """ close everything in this instance (threads, opened streams, files...)"""
        if self.enableRecording:
            self.stopRecordStream()
        if self.enablePlayback:
            self.stopPlayStream()
            self.closePlayFile()
        #self.terminatePyaudio()
        self.stopThread = True

    def prepareRestart(self):
        """ close everything in this instance for retry """
        self.closeAll()
        
    def closeAndExit(self):
        """ close everyting in this instance and exit """
        self.timer.saveTimeToFile()
        self.closeAll()
        sys.exit(0)

    def run(self):
        """ wrapper for start, autoRetry """
        start = True
        # auto retry
        while True:
            try:
                if start != True:
                    # only run this step when restart
                    self.prepareRestart()
                self.configAll()
                self.start()
                start = False 
            except Exception as e:
                traceback.print_exc()
                logger.error(f"RESTART: {e}")
                time.sleep(1)
#============================= END OF Utility Methods ==============================

#===========================================================================
#                            Record Methods
#===========================================================================
    def configRecord(self):
        """ Config record interface """
        # placeholder for recordStream object
        self.recordStream = None

        # Load configurations (recording)
        self.samplingRate = int(self.config['recordingConfig']['samplingRate'])
        self.channelCount = int(self.config['recordingConfig']['channelCount'])
        self.sampleWidth = int(self.config['recordingConfig']['sampleWidth'])
        self.recordChunk= int(self.config['recordingConfig']['recordChunk'])

        # Calculate other values for recording
        self.recordFormat = self.pyaudio.get_format_from_width(self.sampleWidth)
        self.recordDeviceIndex = self.getDeviceIndex("seeed")
        self.callbackCountBeforeSaveFile = self.recordFileDuration * self.samplingRate / self.recordChunk
        self.callbackCountBeforeRestartRecording = self.recordInterval * self.samplingRate / self.recordChunk
        self.outputBufferSizeInByte = self.samplingRate * self.sampleWidth * self.channelCount * self.recordFileDuration
        self.outputWAVFileSizeInByte = self.outputBufferSizeInByte + 44
        self.callbackInDataSize = int(self.outputBufferSizeInByte / self.callbackCountBeforeSaveFile)
        self.systemBootTime = float(subprocess.check_output(['./getclock']))
        
        # Init some variables for recording
        self.doubleBufferSelector = 0
        self.recordData = [bytearray(self.outputBufferSizeInByte), bytearray(self.outputBufferSizeInByte)]
        self.recordOutputFilepath = ""
        self.recordCallbackCounter = 0
        self.totalRecordCallback = 0 
        self.allowRecord = True # True when recording, False wait for interval to finish 
        self.totalRecordOverflow = 0
        self.recordCounter = 0 # track the number of recorded files

        # autoRetry related variables
        self.ADCInterval = self.recordChunk / self.samplingRate
        logger.debug(f"adc interval is {self.ADCInterval}")

    def openRecordStream(self):
        """
        Open the record stream
        All parameters are defined in the config.ini file
        """        
        self.recordStream = self.pyaudio.open(
            rate = self.samplingRate,
            channels = self.channelCount,
            format = self.recordFormat,
            input = True,
            input_device_index= self.recordDeviceIndex,
            frames_per_buffer= self.recordChunk,
            start = True,
            stream_callback= self.recordCallback
        )

    def stopRecordStream(self):
        """
        stop the record stream from Port Audio 

        If a stream is in callback mode we will have to inspect whether the background thread has
        finished, or we will have to take it out. In either case we join the thread before
        returning. In blocking mode, we simply tell ALSA to stop abruptly (abort) or finish
        buffers (drain)
        
        Stream will be considered inactive (!PaAlsaStream::isActive) after a call to this function
        """
        # check if recordStream is created
        if self.recordStream != None:
            self.recordStream.stop_stream() # I assume when we stop the stream the buffer is cleaned and we cannot read or write the stream anymore
            self.recordStream.close() # the difference is that after stop the stream, we can resume it while it is not true for close

    def isRecordDataEnough(self):
        ''' check if we have collected enough number of files '''
        return not (self.recordCounter < self.recordCount or self.recordCount == 0)

    def generateRecordFilepath(self, time_info):
        ''' given the current time info, return the formatted (<timestamp>_<macAddress>.wav) record file path'''
        systemBoottimeInUnixTime = self.systemBootTime + time_info['input_buffer_adc_time']
        systemBoottimeInDatetime = datetime.fromtimestamp(systemBoottimeInUnixTime)
        recordOutputFilePath = self.recordFolderPath + "/" + systemBoottimeInDatetime.strftime("%m_%d_%Y_%H_%M_%S_%f") + "_" + self.deviceMac + ".wav"
        return recordOutputFilePath

    def recordCallback(self, in_data, frame_count, time_info, status):
        ''' this is the handler for each chunk of data'''

        # For autoRetry
        if self.prevADCTime == -1:
            self.prevADCTime = float(time_info['input_buffer_adc_time'])
        else:
            adcTime = float(time_info['input_buffer_adc_time'])
            if adcTime - self.prevADCTime < self.ADCInterval * 0.1:
                raise ADCTimeError
            else:
                self.prevADCTime = adcTime

        # If we are waiting for the end of interval between two records
        if self.allowRecord == False:
            self.recordCallbackCounter += 1
            # If it is the end of interval
            if self.recordCallbackCounter == self.callbackCountBeforeRestartRecording:
                # We will start recording in the next callback
                self.recordCallbackCounter = 0
                self.allowRecord = True

        # If we are allowed to record
        else:
            # If this is the first chunk of the data for this recording, we will create the filename
            if self.recordCallbackCounter == 0:
                self.recordOutputFilepath = self.generateRecordFilepath(time_info)

            # Update the callback counters
            self.recordCallbackCounter += 1 # this is a counter which will be reset after enough data is collected for a file
            self.totalRecordCallback += 1 # this is an always running counter

            # Check the status of this callback. (From our experience, all error outputs are caused by overflow)
            # Update the overflow counter 
            # Overflow will cause the data collection module stops in an undetermined time in the future.
            if status != 0:
                logger.warning(f"Record Callback in Wrong Status: {status}")
                self.totalRecordOverflow += 1

            # Update the data buffer
            self.recordData[self.doubleBufferSelector][(self.recordCallbackCounter-1)*self.callbackInDataSize:(self.recordCallbackCounter)*self.callbackInDataSize] = in_data

            logger.debug(f"{'RecordCallback Count:':<30} {self.recordCallbackCounter:>5} \
    {'Input Data length (Byte):':<30} {len(in_data):>7} \
    {'CPU load:':<10} {round(self.recordStream.get_cpu_load(),4):>5} \
    {'Input Latency:':<15} {round(self.recordStream.get_input_latency(),4):>5} \
    {'Input ADC time:':<15} {round(time_info['input_buffer_adc_time'],5):>10} \
    {'Status:':<15} {status:>10} \
    {'Total Overflow:':<15} {self.totalRecordOverflow:>10} \
    {'Total Callback:':<15} {self.totalRecordCallback:>10} \
    ")
            # If we have recorded enough data, we will save the data in another thread
            if self.recordCallbackCounter == self.callbackCountBeforeSaveFile and not self.isRecordDataEnough():
                thread = threading.Thread(target=self.handleRecordData, args=(self.recordData[self.doubleBufferSelector], self.recordOutputFilepath, ))
                thread.name = 'handleRecordData'

                # clean buffer
                self.recordData[self.doubleBufferSelector] = bytearray(self.outputBufferSizeInByte)
                self.flipDoubleBufferSelector()
                self.recordOutputFilepath = ""

                # start the thread
                thread.start()

                self.recordCounter += 1
                self.recordCallbackCounter = 0
                if self.callbackCountBeforeRestartRecording != 0:
                    self.allowRecord = False 

        # Continue the recording
        return None, pyaudio.paContinue

    def convertRawToNpArray(self, dataBuffer):
        """ Convert raw data in the databuffer to numpy array format"""
        # ! Add handler for 32 bit and 16 bit PCM data
        # data processing
        # step 1: convert bytearray to numpy array
        #y = np.frombuffer(dataBuffer, dtype=np.int16) # does not support 24 bit
        #y = rawutil.unpack(f"{int(len(dataBuffer)/2)}b",dataBuffer) # slow takes 1.5 S

        #==========================================================================
        #                              Parameter Explanation
        #  dx: x byte PCM data
        #  dt: data type
        #  y: data in numpy array format
        #==========================================================================
        y = np.array([])
        if self.sampleWidth == 2:
            # todo
            pass
        elif self.sampleWidth == 3:
            d3 = np.frombuffer(dataBuffer, dtype=np.uint8).reshape(-1, 3) # This is the fastest solution and only takes several ms, reference https://stackoverflow.com/questions/49183514/more-pythonic-way-to-convert-24-bit-ints-to-32-bit-ints
            signs = np.array((d3[:, 2] >= 0x80) * 0xFF)
            d4 = np.concatenate((d3, signs.reshape(-1, 1)), axis=1)
            d4 = d4.flatten()
            d4 = d4.astype(np.ubyte)
            d4 = d4.tobytes()
            dt = np.dtype(np.int32)
            dt = dt.newbyteorder('<')
            y = np.frombuffer(d4, dtype=dt)
        elif self.sampleWidth == 4:
            # todo 
            pass

        return y

    def processData(self, y, timestamp):
        """ Compute simple stats of a piece of data (in numpy array format) and stream them to the server """

        mac = self.deviceMac
        pump = self.deviceDescription
        tt = timestamp

        for i, sensorConfig in enumerate(self.sensors):
            if sensorConfig.type == "NC":
                continue
            sensor = f"sensor_{i}_{sensorConfig.type}_{sensorConfig.location}"
            topic = f"maintletDV/{mac}/{pump}/{sensor}" 
            
            channelData = y[i::8] / 100

            # step 2: calculate useful stats
            # we use value for RMS for back compatability
            fieldNames = []
            fieldValues = []
            fieldNames.append('RMS')
            fieldValues.append(np.sqrt(np.mean(channelData**2)))
            fieldNames.append('Range')
            fieldValues.append(np.max(channelData) - np.min(channelData))
            fieldNames.append('MAX')
            fieldValues.append(np.max(channelData))
            fieldNames.append('MIN')
            fieldValues.append(np.min(channelData))
            fieldNames.append('STD')
            fieldValues.append(np.std(channelData))
            

            # compose message with format time_field1_value1_field2_value2...
            # ! maybe we can change to send struct instead? 
            message=f"{tt}_"
            for name, value in zip(fieldNames, fieldValues):
                message+=f"{name}_{value}_"
            # remove the last _
            message = message[:-1]
            
            logger.info(topic)
            logger.info(message)

    def handleRecordData(self, dataBuffer, recordOutputFilepath):
        # We should not write variables with states in any thread, because these states will be undetermined.
        with self.timer.getTime(f"<SaveRecordDataThread>_<{os.path.basename(__file__)}:#x_#x>") as mt:
            if recordOutputFilepath == "" or len(dataBuffer) <= self.outputBufferSizeInByte - 100:
                logger.critical(f"file name is not ready or data is not ready, size: {len(dataBuffer)}, target: {self.outputBufferSizeInByte}") 
                self.closeAndExit()

            # extract metadata
            recordOutputFilename = recordOutputFilepath.split('/')[-1]
            recordTime = recordOutputFilename.split(':')[0][:-3]

            # create a table entry and send it to database handler
            tableEntry = self.createTableEntry(tableTemplate=self.table)
            tableEntry.filename = recordOutputFilename
            tableEntry.recordTime = recordTime
            tableEntry.volumes = ','.join(str(e) for e in MaintletGainControl.currentVolumes)
            # print(tableEntry.volumes)
            tableEntry.updateKey()
            #todo implement a message Queue Qos = 0 # MQTT QoS 2? 
            self.databaseHandler.messageQPut(MaintletMessage(f"insert_{config['pathNameConfig']['tableName']}", tableEntry))
            logger.debug(tableEntry)
            
            # save the data
            with self.timer.getTime(f"<Save wave file wtih Duration {self.recordFileDuration} S>_<{os.path.basename(__file__)}:#x_#x>") as mt:
                wf = wave.open(recordOutputFilepath, 'wb')
                wf.setnchannels(self.channelCount)
                wf.setsampwidth(self.sampleWidth)
                wf.setframerate(self.samplingRate)
                wf.writeframes(dataBuffer) 
                wf.close()

#============================= END OF Record Methods ==============================

#===========================================================================
#                            Playback Methods
#===========================================================================
    def configPlayback(self):
        self.playStream = None
        self.playbackMode = self.config['playbackConfig']['playbackMode']
        self.playChunk = int(self.config['playbackConfig']['playChunk'])
        self.playDeviceIndex = self.getDeviceIndex("ac101")
        self.playbackCallbackCount = 0

        if self.playbackMode == 'files':
            self.playbackAudioFilesPathList = list(self.config['playbackConfig']['files'])
            if len(self.playbackAudioFilesPathList) == 0:
                pass
            else:
                self.currentPlaybackFileIndex = 0
                self.currentPlaybackFilePath = self.playbackAudioFilesPathList[self.currentPlaybackFileIndex]
                self.configOnePlaybackFile()

        elif self.playbackMode == 'follow':
            pass
    
    def configOnePlaybackFile(self):
        self.wf = wave.open(self.currentPlaybackFilePath)
        self.playbackSampleWidth = self.wf.getsampwidth()
        self.playbackFormat = self.pyaudio.get_format_from_width(self.playbackSampleWidth)
        self.playbackChannelCount = self.wf.getnchannels()
        self.playbackRate = self.wf.getframerate()

    def openPlayStream(self):
        """
        Open the play stream
        All parameters are determined by the audio file we would like to play
        When output=True and out_data does not contain at least frame_count frames, paComplete is assumed for flag.
        """        
        self.playStream = self.pyaudio.open(
            rate = self.playbackRate,
            channels = self.playbackChannelCount,
            format = self.playbackFormat,
            output = True,
            output_device_index= self.playDeviceIndex,
            frames_per_buffer=self.playChunk,
            stream_callback= self.playCallback
        )
    
    def stopPlayStream(self):
        if self.playStream != None:
            self.playStream.stop_stream()
            self.playStream.close()

    def playCallback(self, in_data, frame_count, time_info, status):

        data = self.wf.readframes(self.playChunk)
        self.playbackCallbackCount += 1
        if len(data) < self.playChunk * self.playbackSampleWidth * self.playbackChannelCount:
            # end of the file
            if self.currentPlaybackFileIndex == len(self.playbackAudioFilesPathList)-1:
                # end of list
                pass
            else:
                # increase the playbackfile index
                self.currentPlaybackFileIndex += 1
                # close the previous file
                self.wf.close()
                # get the new file path
                self.currentPlaybackFilePath = self.playbackAudioFilesPathList[self.currentPlaybackFileIndex]
                # open the new file
                self.wf = wave.open(self.currentPlaybackFilePath)
                # extract and append
                tempData = self.wf.readframes(self.playChunk - int(len(data)/self.playbackSampleWidth/self.playbackChannelCount))
                data = data + tempData
                self.playbackCallbackCount = 0

        logger.debug(f"{'Plackback Callback Count:':<30} {self.playbackCallbackCount:>5} \
{'Output Data Length (Byte):':<30} {len(data):>7} \
{'Output DAC time:':>20} {round(time_info['output_buffer_dac_time'],5):>20} \
                ")

        return (data, pyaudio.paContinue)
    
    def closePlayFile(self):
        self.wf.close()
#============================= END OF Playback Methods ==============================


if __name__ == "__main__":
    databaseHandler = MaintletDatabase()
    maintletDataCollector = MaintletDataCollection(databaseHandler=databaseHandler)
    maintletDataCollector.run()
