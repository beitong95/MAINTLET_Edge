#===========================================================================
#  ?                                ABOUT
#  @author         :  Beitong Tian
#  @email          :  beitong2@illinois.edu
#  @repo           :  
#  @createdOn      :  01/31/2023
#  @description    :  A class for database table entry
#===========================================================================

# Todo: use namedtuple instead
# Todo: type safe
# Todo: inheritance, create a base class ... 

import json

class TableEntryForRecordedFile:
    def __init__(self, message=''):
        """
        Init a table entry.

        Args:
            message (str, optional): A formatted message which can be used to initialize a table entry. Defaults to ''.
        """        
        self.key = '' # record time _ macaddress
        self.filename = ''
        self.duration = 0
        self.samplingRate = 0
        self.sampleWidth = 0
        self.recordChunk = 0
        self.playbackSamplingRate = 0
        self.playbackSampleWidth = 0
        self.playbackChunk = 0
        self.playbackFileNames = '' # need flatten
        self.sensor1Type = ''
        self.sensor1Location = ''
        self.sensor2Type = ''
        self.sensor2Location = ''
        self.sensor3Type = ''
        self.sensor3Location = ''
        self.sensor4Type = ''
        self.sensor4Location = ''
        self.sensor5Type = ''
        self.sensor5Location = ''
        self.sensor6Type = ''
        self.sensor6Location = ''
        self.volumes = ''
        self.experimentName = ''
        self.experimentDescription = ''
        self.deviceMac = ''
        self.deviceDescription = ''
        self.recordTime = ''
        self.tableName = ''
        self.transactionStatus = '' # finished unfinished
        if message != '':
            self.initWithMessage(message)
    
    def updateKey(self):
        """
        The primary key value of the table

        Returns:
            self.key (string): The primary key value of the table
        """        
        self.key = f"{self.recordTime}_{self.deviceMac}"
        return self.key
    

    def initWithMessage(self, message):
        """
        Init a table entry with a message with predefined format.
        The format should satisfy the tokenization below. 

        Args:
            message (string): A tuple string
        """        
        if type(message) is tuple:
            pass
        elif type(message) is str:
            # convert string to tuple
            message = eval(message)
        self.key = message[0] # record time _ macaddress
        self.filename = message[1]
        self.duration = message[2]
        self.samplingRate = message[3]
        self.sampleWidth = message[4]
        self.recordChunk = message[5]
        self.playbackSamplingRate = message[6]
        self.playbackSampleWidth = message[7]
        self.playbackChunk = message[8]
        self.playbackFileNames = message[9]
        self.sensor1Type = message[10]
        self.sensor1Location = message[11]
        self.sensor2Type = message[12]
        self.sensor2Location = message[13]
        self.sensor3Type = message[14]
        self.sensor3Location = message[15]
        self.sensor4Type = message[16]
        self.sensor4Location = message[17]
        self.sensor5Type = message[18]
        self.sensor5Location = message[19]
        self.sensor6Type = message[20]
        self.sensor6Location = message[21]
        self.experimentName = message[22]
        self.experimentDescription = message[23]
        self.deviceMac = message[24]
        self.deviceDescription = message[25]
        self.recordTime = message[26]
        self.tableName = message[27]
        self.transactionStatus = message[28]

    def getTableAttributes(self):
        """
        Get table attributes in a string format which is required for creating a database table

        Returns:
            attributes (string): All attributes of the table. 

        Example Output: 
        (key, filename, duration, samplingRate, sampleWidth, recordChunk, playbackSamplingRate, playbackSampleWidth, 
        playbackChunk, playbackFileNames, sensor1Type, sensor1Location, sensor2Type, sensor2Location, sensor3Type, 
        sensor3Location, sensor4Type, sensor4Location, sensor5Type, sensor5Location, sensor6Type, sensor6Location, 
        experimentName, experimentDescription, deviceMac, deviceDescription, recordTime, tableName, transactionStatus, 
        PRIMARY KEY (key))
        """        
        primaryKeysEntry = f"PRIMARY KEY (key)"
        attributes = list(self.__dict__.keys())
        attributes.append(primaryKeysEntry) 
        attributes = tuple(attributes)
        attributes = str(attributes).replace('"', '').replace("'", '')
        return attributes

    def getTableEntryValuesForDatabase(self):
        """
        Get table values used for creating a table entry.

        Returns:
            list: A list of values of a table entry.
        """        
        return [tuple(self.__dict__.values())]

    def getTableEntryValuesForPublishMessage(self):
        """
        Get table values used for sending message.

        Returns:
            string: A string can be used to compose a message.
        """        

        return str(tuple(self.__dict__.values()))
 
    def getAttributeCount(self):
        """
        Get the number of attributes in an entry

        Returns:
            int: The number of attributes in an entry
        """
        return len(tuple(self.__dict__.keys()))

    def getTableEntryInDictFormat(self):
        """
        Get the table entry in the dict format with key = attribute name, value = attribute value

        Returns:
            dict: A table entry in the dict format.
        """
        return self.__dict__

    def getDebugInfo(self):
        """
        For debug purpose, print all outputs of methods in this class. 
        """
        return f"""getTableAttributes: {self.getTableAttributes()}
getAttriubteCount: {self.getAttriubteCount()}
getTableValuesForDatabase: {self.getTableEntryValuesForDatabase()}
getTableEntryValuesForPublishMessage: {self.getTableEntryValuesForPublishMessage()}
getTableEntryInDictFormat: {self.getTableEntryInDictFormat()}"""

    def __str__(self):
        """
        Get a string of dict with beautiful format

        Returns:
            string: A formatted string of dict.
        """
        return json.dumps(self.__dict__, indent=2) 

#===========================================================================
#                            TEST CODE
#===========================================================================
if __name__ == '__main__':

    print("Default setting")
    print("#######################################################")
    tableEntry = TableEntryForRecordedFile()
    print(tableEntry)
    print(tableEntry.getDebugInfo())

    print()

    print("Synthesized data")
    print("#######################################################")
    tempTuple = tuple(f"{i+1}" for i in range(tableEntry.getAttriubteCount()))
    tableEntry2 = TableEntryForRecordedFile(f"{tempTuple}")
    print(tableEntry2)
    print(tableEntry2.getDebugInfo())
#============================= END OF TEST CODE ==============================

    
