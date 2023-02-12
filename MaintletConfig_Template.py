#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  02/02/2023
#  @description    :  Set up global variables (shared by multiple modules)
#===========================================================================

import getmac
import os
from datetime import datetime
import json
#===========================================================================
#                           HELPER FUNCTIONS 
#===========================================================================
def createExperimentFolder():
    """
    Create a folder with the name of current timestamp for storing all information of this experiment

    Returns:
        str: The experiment folder path. 
    """
    if not os.path.exists('./results'):
        os.system("mkdir results")
    experimentFolderPath = "./results/" + datetime.now().strftime("%m-%d-%Y-%H-%M-%S")
    os.system(f"mkdir {experimentFolderPath}")
    return experimentFolderPath

def getFormattedConfig(config):
    return json.dumps(config, indent = 4)

#============================= END OF SECTION ==============================


#===========================================================================
#                            CONFIGS
#===========================================================================

#=================== For Logger ===================
mailhost = 'outbound-relays.techservices.illinois.edu'
fromaddr = 'beitong2@illinois.edu'
toaddrs = 'beitong2@illinois.edu'
logFileName = 'test.log'
#=================== PATH AND FOLDER NAME ===================
pathNameConfig = {}
# set names
pathNameConfig["logFolderName"] = 'logs'
pathNameConfig["datasetFolderName"] = 'datasets'
pathNameConfig["outputFolderName"] = 'outputs'
pathNameConfig["recordFolderName"] = 'records'
pathNameConfig["tmpFolderName"] = 'tmp'
pathNameConfig["databaseName"] = 'MaintletTest'
pathNameConfig["tableName"] = 'experiment'   # (1) experiment, or (2) test
# create paths and make folders
experimentFolderPath = createExperimentFolder() # createExperimentFolder will only be executed once because of the import cache mechanism
pathNameConfig["experimentFolderPath"] = experimentFolderPath
pathNameConfig["logFolderPath"] = f"{experimentFolderPath}/{pathNameConfig['logFolderName']}"
pathNameConfig["recordFolderPath"] = f"{experimentFolderPath}/{pathNameConfig['recordFolderName']}"
pathNameConfig["outputFolderPath"] = f"{experimentFolderPath}/{pathNameConfig['outputFolderName']}"
pathNameConfig["datasetFolderPath"] = f"{experimentFolderPath}/{pathNameConfig['datasetFolderName']}"
pathNameConfig["tmpFolderPath"] = f"{experimentFolderPath}/{pathNameConfig['tmpFolderName']}"
os.system(f"mkdir {pathNameConfig['logFolderPath']}")
os.system(f"mkdir {pathNameConfig['recordFolderPath']}")
os.system(f"mkdir {pathNameConfig['outputFolderPath']}")
os.system(f"mkdir {pathNameConfig['datasetFolderPath']}")
os.system(f"mkdir {pathNameConfig['tmpFolderPath']}")
pathNameConfig["databasePath"] = f"{pathNameConfig['datasetFolderPath']}/{pathNameConfig['databaseName']}.sqlite3"
messageQMaxSize = 100

#=================== DEVICE ===================
deviceMac = getmac.get_mac_address()
deviceConfig = {}
deviceConfig["deviceMac"] = deviceMac
deviceConfig["deviceDescription"] = "rpi4 for experiment"

#=================== NETWORKING ===================
networkConfig = {}
networkConfig["enableNetwork"] = False,      
networkConfig["serverIP"] = '192.168.0.104'
networkConfig["serverUserName"] = 'beitongt'
networkConfig["serverFileFolder"] = '/home/beitongt/maintlet/NoiseAware/server/webserver/audio'
networkConfig["MQTTQoS"] = 2

#=================== RECORDING ===================
recordingConfig = {}
recordingConfig["enableRecording"] = True 
recordingConfig["samplingRate"] = 48000 
recordingConfig["channelCount"] = 8 
# 2 -> int16
# 3 -> int24
# 4 -> int32
recordingConfig["sampleWidth"] = 2
recordingConfig["recordChunk"] = 4800 

#=================== PLAYBACK ===================
playbackConfig = {}
playbackConfig["enablePlayback"] = False
playbackConfig["playChunk"] = 4800
# playbackMode 
# (1) files : play a audio file
# (2) follow: play the recorded file (with echo cancellation) - current not avaialble in this version
playbackConfig["playbackMode"] = 'files'
# if you choose (2), you have to provide a playbackAudioFileList
# We assume these files have the same format and has a length longer than the playChunk
playbackConfig["files"] = ['testAudio/testRecordAndPlay.wav',
            'testAudio/testRecordAndPlay.wav']

#=================== EXPERIMENT ===================
sensorConfig = {}
sensorConfig['sensor1'] = {}
sensorConfig['sensor1']['type'] = 'vibration'
sensorConfig['sensor1']['location'] = 'top'
sensorConfig['sensor2'] = {}
sensorConfig['sensor2']['type'] = 'vibration'
sensorConfig['sensor2']['location'] = 'top'
sensorConfig['sensor3'] = {}
sensorConfig['sensor3']['type'] = 'vibration'
sensorConfig['sensor3']['location'] = 'top'
sensorConfig['sensor4'] = {}
sensorConfig['sensor4']['type'] = 'vibration'
sensorConfig['sensor4']['location'] = 'top'
sensorConfig['sensor5'] = {}
sensorConfig['sensor5']['type'] = 'vibration'
sensorConfig['sensor5']['location'] = 'top'
sensorConfig['sensor6'] = {}
sensorConfig['sensor6']['type'] = 'vibration'
sensorConfig['sensor6']['location'] = 'top'

experimentConfig = {}
experimentConfig["experimentName"] = 'Test'
experimentConfig["experimentDescription"] = 'Test'
# How many files we want to record? 0 means record until Ctrl-C
experimentConfig["recordCount"] = 0 
# unit: second
experimentConfig["recordFileDuration"] = 1 
experimentConfig["recordInterval"] = 2
#============================= END OF CONFIGS ==============================

#===========================================================================
#                            Formatted INFO and STRUCTURE 
#===========================================================================

globalConfig = {
    'macAddress':deviceMac,
    'experimentFolderPath': experimentFolderPath,
}

description = f"""###Description###
Device MAC: {deviceMac}
Device description: {deviceConfig['deviceDescription']}
Experiment description: {experimentConfig['experimentDescription']}
"""

config = {}
config['pathNameConfig'] = pathNameConfig
config['deviceConfig'] = deviceConfig
config['networkConfig'] = networkConfig
config['recordingConfig'] = recordingConfig
config['playbackConfig'] = playbackConfig
config['sensorConfig'] = sensorConfig
config['experimentConfig'] = experimentConfig

targetFileSize = recordingConfig["samplingRate"] * recordingConfig["channelCount"] * recordingConfig["sampleWidth"] * experimentConfig["recordFileDuration"] + 44 # for wav

minimumDiskSpace = 100 # unit: MB
#============================= END OF SECTION ==============================


#===========================================================================
#                            TEST CODE
#===========================================================================
if __name__ == '__main__':
    print(config)
    print(globalConfig)
    print(description)
    print(getFormattedConfig(config))
#============================= END OF TEST CODE ==============================


