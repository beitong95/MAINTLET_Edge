#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian & Cody Wang
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  02/06/2023
#  @description    :  Handle Files in a folder
#===========================================================================
from MaintletConfig import pathNameConfig, targetFileSize, minimumDiskSpace, MAX_FILE_COUNT
from MaintletSharedObjects import timer, fileSystemToDataAnalysisQ
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from MaintletLog import logger
import os
import time
import threading 
import shutil
from os.path import isfile, join
from os import listdir
import pyprctl

class MaintletFileSystem:
    def __init__(self, networkHandler = -1):
        self.recordFolderPath = pathNameConfig['recordFolderPath']
        self.totalFileCounter = 0 # counter for total file count
        self.networkHandler = networkHandler # network handelr for sending data to remote server
        self.targetFileSize = targetFileSize
        self.curFilePath = ""
        patterns = ["*"]
        ignore_patterns = None
        ignore_directories = False
        case_sensitive = True
        self.event_handler = PatternMatchingEventHandler(patterns, ignore_patterns, ignore_directories, case_sensitive)
        self.event_handler.on_created = self.on_created
        path = self.recordFolderPath
        go_recursively = True
        self.observer = Observer()
        self.observer.schedule(self.event_handler, path, recursive=go_recursively)
        
    def on_created(self, event):
        filePath = event.src_path
        # The following while loop will block on_created until the wav file is completely saved in the file system
        # This is OK because we want to process these files in FIFO order
        while True:
            if os.path.getsize(filePath) == self.targetFileSize:
                self.curFilePath = filePath
                logger.info(f"File: {self.curFilePath} is saved successfully")
                self._newFileHandler(filePath)
                threading.Thread(target=self._checkAndCleanUpSpace).start()
                break
                
            time.sleep(0.05)

    def _newFileHandler(self, filePath):
        fileSystemToDataAnalysisQ.put(filePath)
    
    def getCurrentRemainingDiskSpace(self):
        """ Get the remaining disk space in MB """
        stat = shutil.disk_usage(self.recordFolderPath)
        diskSpaceInMB = round(stat.free/1024/1024, 2)
        return diskSpaceInMB

    def _checkAndCleanUpSpace(self):
        """ Remove the oldest file in the record folder """
        currentDiskSpace = self.getCurrentRemainingDiskSpace()
        logger.debug(f"Remaining Disk Space = {currentDiskSpace} MB")
        if currentDiskSpace < minimumDiskSpace:
            logger.error(f"Disk is Full: Remaining disk space = {currentDiskSpace} MB")        
            self._cleanUpSpace()
        # restrict the number of files
        filepaths = self._getAllRecordFilepaths(self.recordFolderPath)
        num_of_file = len(filepaths)
        while self.getCurrentRemainingDiskSpace() <= minimumDiskSpace or num_of_file > MAX_FILE_COUNT:
            self._cleanUpSpace()
            filepaths = self._getAllRecordFilepaths(self.recordFolderPath)
            num_of_file = len(filepaths)

    def _getAllRecordFilepaths(self, data_dir):
        """ Get all absolute file paths in a directory and sort them in alphabetical order """
        filepaths = []
        filepaths = sorted([join(data_dir, f) for f in listdir(data_dir) if isfile(join(data_dir, f)) and 'wav' in f])
        return filepaths

    def _getOldestRecordFilepath(self, filepaths):
        """ Get the latest file's filepath given filepaths sorted by create time in descending order """
        return filepaths[0]

    def _cleanUpSpace(self):
        """ Remove the oldest file in the record folder """
        #todo  Think about other cleanup strategies 
        # get all filepaths
        filepaths = self._getAllRecordFilepaths(self.recordFolderPath)
        # get the oldest
        filepath = self._getOldestRecordFilepath(filepaths)
        # remove it
        logger.warning(f"Delete file for more space: {filepath}")
        try:
            os.system(f"rm {filepath}")
        except Exception as e:
            logger.critical(f"Cannot remove {filepath}")
            raise     

    def run(self):
        pyprctl.set_name("FileSystemMgr")
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.debug(f"MaintletFileSystem KeyboardInterrupt")
            self.observer.stop()
            self.observer.join()




