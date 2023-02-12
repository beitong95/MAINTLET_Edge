#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  02/02/2023
#  @description    :  This is a python file that stores all shared objects among modules
#===========================================================================

from MaintletTimer import MaintletTimer
from MaintletConfig import experimentFolderPath
from multiprocessing import Queue
import time
#===========================================================================
#                            SHARED OBJECT #?
#===========================================================================
timer = MaintletTimer(record=True, logging=True, experimentFolderPath = experimentFolderPath)
fileSystemToDataAnalysisQ = Queue()
networkingOutQ = Queue()
#============================= END OF SHARED OBJECT ==============================

#===========================================================================
#                            TEST CODE
#===========================================================================
if __name__ == '__main__':
    def sleep10S():
        time.sleep(10)
    with timer.getTime("1111"):
        sleep10S()