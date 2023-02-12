#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  02/01/2023
#  @description    :  This is the MaintletTimer module
#===========================================================================

#==========================================================================
#                              MaintletTimer
#   Provide a way to record the time consumption of any segment of code
#   record bool : If we want to record the time and display the time on the screen
#   logging bool: If we want to log the time to a file (E.g., for evaluation)
#   Usage:
#   1. Create a global timer
#       timer = MaintletTimer(record = True, logging = True)
#   2. Record time
#       with timer.getTime("the-task-name"):
#           your-task()
#       # A suggestion for "the-task-name"： "<task-name>_<file:#startline-#endline>"
#       # E.g., <saveData>_<MaintletEdge.py:#123-#456>
#       # the recorded time will be in (start time, duration) format. The unit is second.
#       # you can retrive time records of a specific task by calling:
#       timer.timeRecords["the-task-name"]
#==========================================================================

import time
from MaintletLog import logger
from contextlib import contextmanager
import pickle
from MaintletConfig import pathNameConfig

class MaintletTimer:
    #===========================================================================
    #                            Init logger
    # The logger can be shared among all instances, so we set it as a class variable. 
    # spawn a child logger from the root logger
    # the root logger is configered in MaintLog.py
    # MaintletLog.py is imported in the entry python file (currently MaintletEdge.py)
    #===========================================================================
    def __init__(self, experimentFolderPath, record=True, logging=False):
        self.experimentFolderPath = experimentFolderPath
        self.startTime = 0
        self.measuredTask = ""
        self.fileSize = 0
        self.timeRecords = {}
        self.record = record
        self.logging = logging

    @contextmanager 
    def getTime(self, taskName):
        if self.record:
            startTime = 0
            try:
                startTime = time.time()
                yield
            finally:
                elapsedTime = time.time() - startTime
                logger.info(f"{taskName}: {round(elapsedTime,5)} Seconds.")
                if self.logging:
                    timeRecord = [round(startTime,5), round(elapsedTime, 5)]
                    if taskName not in self.timeRecords.keys():
                        self.timeRecords[taskName] = []
                    self.timeRecords[taskName].append(timeRecord)
        else:
            yield
    
    def saveTimeToFile(self):
        if self.logging:
            f = open(f"{pathNameConfig['outputFolderPath']}/timeRecords.pkl","wb")
            pickle.dump(self.timeRecords,f)
            f.close()


#===========================================================================
#                            TEST CODE
# Try to see the difference between
# (1) python3 MaintletTimer.py
# (2) python3 MaintletTimer.py -log debug
#===========================================================================
import argparse
if __name__ == "__main__":
    import os
    logger.warning(f"{os.path.basename(__file__)}")
    parser = argparse.ArgumentParser()
    parser.add_argument( '-log',
                        '--loglevel',
                        default='warning',
                        help='Provide logging level. Example --loglevel debug, default=warning' )

    args = parser.parse_args()

    logger.setLevel(args.loglevel.upper())

    timer = MaintletTimer("./testTimer", record=True, logging=True)
    with timer.getTime('processData') as mt:
        time.sleep(1)
    with timer.getTime('IO') as mt:
        time.sleep(1.5)
    with timer.getTime('processData') as mt:
        time.sleep(2)
    with timer.getTime('IO') as mt:
        time.sleep(2)
    print(timer.timeRecords)
    timer.saveTimeToFile()
    with open(f"./testTimer/timeRecords.pkl", "rb") as input_file:
        e = pickle.load(input_file)
    print(e)
#============================= END OF TEST CODE ==============================

