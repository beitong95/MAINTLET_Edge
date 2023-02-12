#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  NA
#  @createdOn      :  02/01/2023
#  @description    :  Errors used in Maintlet project 
#===========================================================================

from MaintletLog import logger

#==========================================================================
#                              Error Class
#   This is the base error class for MAINTLET exceptions
#   Catch all errors specific for MAINTLET
#
#   import MaintletError
#   try:
#       except MaintletError.Error 
#==========================================================================
class Error(Exception):
    def __init__(self, msg=''):
        self.message = msg
        Exception.__init__(self, msg)

    def __repr__(self):
        return self.message

    __str__ = __repr__

class NoFilenameFoundInDictionary(Error):
    pass

class ConfigFileNotFoundInDirectoryError(Error):
    def __init__(self, filepath):
        Error.__init__(self, f"We cannot find config file with path: {filepath}")
        self.filepath = filepath

class ADCTimeError(Error):
    def __init__(self):
        Error.__init__(self, f"The ADC time is not correct. Retry...")

class GetDeviceIndexError(Error):
    def __init__(self, deviceName):
        Error.__init__(self, f"Cannot get the system index of device {deviceName}")

#===========================================================================
#                            TEST CODE
#===========================================================================

if __name__ == '__main__':
    try:
        raise ADCTimeError
    except Exception as e:
        print(e)

    try:
        raise ConfigFileNotFoundInDirectoryError("test-filepath") 
    except Exception as e:
        print(e)
#============================= END OF TEST CODE ==============================


