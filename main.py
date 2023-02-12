#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu 
#  @repo           :  NA
#  @createdOn      :  02/01/2023   
#  @description    :  The entry point for MAINTLET
#===========================================================================

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
from MaintletConfig import config, getFormattedConfig, experimentFolderPath
from MaintletDatabase import MaintletDatabase
from MaintletTable import TableEntryForRecordedFile
from MaintletFileSystem import MaintletFileSystem
from MaintletDataAnalysis import MaintletDataAnalysis
from MaintletSharedObjects import fileSystemToDataAnalysisQ, networkingOutQ
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
#                            START DATA COLLECTION
#===========================================================================
configFilePath = './MaintletConfig.py'


if __name__ == "__main__":
    # print and save configs of this run
    logger.debug(getFormattedConfig(config))
    os.system(f"cp {configFilePath} {experimentFolderPath}/config.py")
    table = TableEntryForRecordedFile()
    databaseManager = MaintletDatabase()
    databaseManager.addTable(tableName=config['pathNameConfig']['tableName'], tableObject=table)
    dataCollectionManager = MaintletDataCollection(databaseHandler=databaseManager)
    filesystemManager = MaintletFileSystem()
    dataAnalyser = MaintletDataAnalysis()
    p = Process(target=dataAnalyser.run, args=(fileSystemToDataAnalysisQ, networkingOutQ), daemon=True)
    t1 = threading.Thread(target = dataCollectionManager.run, daemon=True)
    t2 = threading.Thread(target = filesystemManager.run, daemon=True)
    p.start()
    t1.start()
    t2.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.debug(f"Main KeyboardInterrupt")
        sys.exit(1)
    
    # # Init network
    # if self.enableNetwork:
    #     # todo  We need to rewrite the network part 
    #     self.networkManager = MaintletNetworkManager()
    #     self.syncManager = MaintletClientServerSyncManager(networkManager=self.networkManager, audioInterface=self)
    #     self.syncManager.start()
        
    #     self.DVNetworkManager = MaintletNetworkManager()
    #     self.DVNetworkManager.connectMQTT(self.deviceMac, self.DVserverIP, 2, "", "", None, None)

    # networkManager = MaintletNetworkManager()
    # networkManager.connectMQTT(deviceMac=deviceMac, brokerIP=serverIP, qos=MQTTQoS)
    # try:
    #     maintletDataCollector = MaintletDataCollection(experimentFolderPath = experimentFolderPath, timer = timer)
    # except Exception as e:
    #     traceback.print_exc()
    #     logger.critical(f"Init Error: \n {str(e)}")
    #     sys.exit(1)

    # while True:
    #     try:
    #         maintletDataCollector.start()
    #     except Exception as e:
    #         logger.error("RESTART")
    #         logger.error(e)
    #         maintletDataCollector.prepareRestart()
    #         time.sleep(1)
    #         maintletDataCollector = MaintletDataCollection(experimentFolderPath = experimentFolderPath, timer = timer)
#============================= END OF CODE ==============================

