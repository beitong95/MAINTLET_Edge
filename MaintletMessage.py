#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  02/02/2023
#  @description    :  Handle all messages
#===========================================================================

import queue
from MaintletLog import logger

class MaintletMessage:
    def __init__(self, command, payload):
        self.command = command
        self.payload = payload