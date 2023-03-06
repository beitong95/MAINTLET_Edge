#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu 
#  @repo           :  NA
#  @createdOn      :  02/01/2023   
#  @description    :  The entry point for MAINTLET
#===========================================================================

# TODO: 1. automatical gain control 2. user defined reference data 3. data sync with remote server

#===========================================================================
#                            IMPORT 
#===========================================================================
import argparse
from MaintletLog import logger
import os
from datetime import datetime
import traceback
import sys
import time
import numpy as np
import threading
from multiprocessing import Process
# MAINTLET modules
from MaintletDataCollection import MaintletDataCollection
from MaintletTimer import MaintletTimer
from MaintletConfig import config, getFormattedConfig, experimentFolderPath, deviceMac, networkConfig, experimentConfig, defaultVolumes
from MaintletDatabase import MaintletDatabase
from MaintletTable import TableEntryForRecordedFile
from MaintletFileSystem import MaintletFileSystem
from MaintletDataAnalysis import MaintletDataAnalysis
from MaintletSharedObjects import fileSystemToDataAnalysisQ, networkingOutQ
from MaintletNetworkManager import MaintletNetworkManager
import MaintletHTTPServer
from MaintletGainControl import setMultiMixers, currentVolumes
#============================= END OF IMPORT ==============================

#===========================================================================
#                              SYSTEM MODIFICATION
#===========================================================================
# Set this (data acquisition) process with the highest priority
pid = os.getpid()
os.system("sudo renice -n -19 -p " + str(pid))

# set numpy print size to maximum
np.set_printoptions(threshold=sys.maxsize)
#============================= END OF SYSTEM MODIFICATION ==============================

#===========================================================================
#                            PARSE ARGS
#===========================================================================
parser = argparse.ArgumentParser()
parser.add_argument( '-log',
                     '--loglevel',
                     default='warning',
                     help='Provide logging level. Example --loglevel debug, default=warning' )

args = parser.parse_args()
userSetLogLevel = args.loglevel.upper()
logger.setLevel(userSetLogLevel)
logger.warning(f"Logging now setup to {userSetLogLevel}")
#============================= END OF PARSE ARGS==============================

#===========================================================================
#                            START MAIN
#===========================================================================
configFilePath = './MaintletConfig.py'


if __name__ == "__main__":
    # print and save configs of this run
    logger.debug(getFormattedConfig(config))
    os.system(f"cp {configFilePath} {experimentFolderPath}/config.py")

    # create objects 
    table = TableEntryForRecordedFile()
    networkManager = MaintletNetworkManager()
    networkManager.connectMQTT(deviceMac=deviceMac, brokerIP=networkConfig['serverIP'], qos=networkConfig['MQTTQoS'])
    databaseManager = MaintletDatabase()
    databaseManager.addTable(tableName=config['pathNameConfig']['tableName'], tableObject=table)
    currentVolumes = defaultVolumes # setup the default gains
    setMultiMixers(currentVolumes)
    dataCollectionManager = MaintletDataCollection(databaseHandler=databaseManager)
    fileSystemManager = MaintletFileSystem()
    dataAnalyser = MaintletDataAnalysis(networkManager=networkManager)

    # start processes and threads
    dataAnalyserProcess = Process(target=dataAnalyser.run, args=(fileSystemToDataAnalysisQ, networkingOutQ), daemon=True)
    maintletHTTPServerProcess = Process(target=MaintletHTTPServer.run, daemon=True)
    dataCollectorThread = threading.Thread(target = dataCollectionManager.run, daemon=True)
    fileSystemManagerThread = threading.Thread(target = fileSystemManager.run, daemon=True)
    networkSendingThread = threading.Thread(target = networkManager.sendMessageLoop, daemon=True)
    networkReceivingThread = threading.Thread(target = networkManager.receiveMessageLoop, daemon=True)
    dataAnalyserProcess.start()
    maintletHTTPServerProcess.start()
    dataCollectorThread.start()
    fileSystemManagerThread.start()
    networkSendingThread.start()
    networkReceivingThread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.error(f"Maintlet Main KeyboardInterrupt")
        sys.exit(1)
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)
#============================= END OF MAIN ==============================

