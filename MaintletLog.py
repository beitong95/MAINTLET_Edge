#===========================================================================
#  ?                                MAINTLET Logging 
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  01/24/2023
#  @description    :  This is the MAINTLET logging module developed based on 
#                     the original Python3 logging module.
#===========================================================================

#===========================================================================
#  todo                             TODO
#    1. move log configurations in to config.ini
#    2. change file handler to WatchedFileHandler (for logrotate)
#       Logrotate: https://linux.die.net/man/8/logrotate  
# 
#===========================================================================

#==========================================================================
#                              Logging Rule
#   Three handlers for logging:
#   1. print out on terminal
#   2. save in file
#   3. send alert email 
#   
#   Below we explain logging rules in MAINTLET 
# 
#   Format: 
#   Logging level (handlers used):
#       1. what information is in this logging level
# 
#   DEBUG (1):
#       1. Metadata and Statistics of each chunk of data
#   
#   INFO (1):
#       1. State updates for each audio file
#
#   WARNING (1,2):
#       1. Unusual Time Consumption of some critical functions
#
#   ERROR (1,2):
#       1. Any error captured in our program
#   
#   Critical (1,2,3):
#       1. Low Memory, Low CPU, Low Storage, NO network connection, ... 
#   
#==========================================================================

#==========================================================================
#                              Usage
#   from MaintletLog import logger 
#   logger.error(f"The message you wanna log.")
#   Please refer to the test code below
#   
#==========================================================================

import logging
from logging.handlers import SMTPHandler
import os
from MaintletConfig import description
from MaintletConfig import pathNameConfig
from MaintletConfig import mailhost, fromaddr, toaddrs, logFileName
# default logging level, all messages below these level will be suppressed
logLevel_default = logging.INFO

# create the logger with name MAINTLET
logger = logging.getLogger()
logger.setLevel(logLevel_default)

# create stream handler
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)

# create file handler

logfilename = f"{pathNameConfig['logFolderPath']}/{logFileName}"
file_handler = logging.FileHandler(filename=logfilename, mode='a')
file_handler.setLevel(logging.ERROR)

# create smtp handler

smtp_handler = SMTPHandler(mailhost = mailhost, 
                            fromaddr = fromaddr, 
                            toaddrs = toaddrs, 
                            subject = f"""MAINTLET Critical Logging""")
smtp_handler.setLevel(logging.CRITICAL)

# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
email_formatter = logging.Formatter("""Time: %(asctime)s
Logger Name: %(name)s
Level: %(levelname)s
Message: %(message)s
\n\n{}""".format(description))
# connect everything logger - handler(filter) - formatter
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
smtp_handler.setFormatter(email_formatter)
logger.addHandler(stream_handler)
logger.addHandler(file_handler)
logger.addHandler(smtp_handler)

#===========================================================================
#                            TEST CODE
#===========================================================================
if __name__ == '__main__':
    logger.debug('debug message')
    logger.info('info message')
    logger.warning('warn message')
    logger.error('error message')
    logger.critical(f"critical message")
#============================= END OF TEST CODE ==============================

