#===========================================================================
#  ?                                ABOUT
#  @author         : Beitong Tian
#  @email          : beitong2@illinois.edu
#  @repo           :  
#  @createdOn      : 01/31/2023 
#  @description    : An Sqlite3 wrapper for MAINTLET project
#===========================================================================

import sqlite3
import threading
from threading import Lock
import os
import queue
from MaintletConfig import pathNameConfig, experimentFolderPath, messageQMaxSize
from MaintletTable import TableEntryForRecordedFile
from MaintletLog import logger
class MaintletDatabase:

    def __init__(self):
        """
        Init an SQlite database for MAINTLET
        """
        # set database folder and path
        self.databaseName = pathNameConfig['databaseName']
        self.experimentFolderPath = experimentFolderPath
        self.databasePath = pathNameConfig['databasePath']
        logger.error(self.databasePath)
        self.con = sqlite3.connect(self.databasePath, check_same_thread=False)
        self.cur = self.con.cursor()
        self.curLock = Lock()
        self.messageQ = queue.Queue(maxsize=messageQMaxSize)
        # a small tableMetaData for table metadata
        self.tableMetaData = {}

    def messageQPut(self, message):
        """
        A wrapper of putting message to message Q

        Args:
            item (MessageQ Object): item should have a command and a payload
        """
        try:
            self.messageQ.put_nowait(message)
        except queue.Full:
            logger.critical("MaintletDatabase Queue is Full")
        self.handleMessageQ()

    def handleMessageQ(self):
        """
        Handle message in message Queues
            Command 1: insert_<tableName>
            Paylaod: Any object which implements methods in TableEntryForRecordedFile
            todo: try else insert the data back into the queue
        """
        while not self.messageQ.empty():
            try:
                message = self.messageQ.get_nowait()
                payload = message.payload
                command = message.command

                if 'insert' in command:
                    tableName = command.split('_')[1]
                    if tableName not in self.tableMetaData.keys():
                        logger.critical(f"Try to insert entry for unknow table: {tableName}")
                        continue
                    self.insertValue(tableName, withColumn=payload.getAttributeCount(), withValue=payload.getTableEntryValuesForDatabase())
                
                elif 'update' in command:
                    # parse command and payload
                    tokens = command.split('_')
                    tableName = tokens[1]
                    column = tokens[2]
                    keyName = tokens[3]
                    keyValue = tokens[4]
                    payload = message.payload
                    newValue = payload

                    if tableName not in self.tableMetaData.keys():
                        logger.critical(f"Try to update entry for unknow table: {tableName}")
                        continue
                    self.updateValue(toTable = tableName, atColumn = column, withKeyName = keyName, withKeyValue = keyValue, withValue = newValue)

            except queue.Empty:
                logger.critical("MaintletDatabase Queue should not be Empty")

    def addTable(self, tableName, tableObject):
        """
        add a table with table object, please create a class following the TableEntryForRecordedFile

        Args:
            tableObject (MaintletTable): A table object
        """
        table = tableObject
        tableAttributes = table.getTableAttributes()
        self.tableMetaData[tableName] = {}
        self.createTable(withName=tableName, withParameter=tableAttributes)

    def createTable(self, withName, withParameter):
        """
        Create a table given the table name and attributes' names

        Args:
            withName (string): The table name. 
            withParameter (tuple): A tuple of names of attributes.
        """
        tableName = withName
        parameterName = withParameter
        command = f"CREATE TABLE if not exists {tableName}{withParameter}"
        with self.curLock:
            self.cur.execute(command)

    def insertValue(self, toTable, withColumn, withValue):
        """
        Insert value (entry) to a table.

        Args:
            toTable (str): The table name.
            withColumn (int): The number of attributes of the table.
            withValue (list): [entry1, entry2, ...]. For each entry: entry1 = (value1, value2, ....).
        """
        tableName = toTable
        valuePlaceholder = f"({['?,' * withColumn][0][:-1]})"
        data = withValue
        command = f"INSERT INTO {tableName} VALUES{valuePlaceholder}"
        thread = threading.Thread(target=self.__insertValue, args=(command,data,))
        thread.name = 'insertValue'
        thread.start()
    
    def __insertValue(self,command,data):
        """
        The thread routine of insertValue

        Args:
            command (str): The command to be sent to the database.
            data (list): Same to withValue in insertValue.
        """
        with self.curLock:
            self.cur.executemany(command, data)
            self.con.commit()
    
    def updateValue(self, toTable, atColumn, withKeyName, withKeyValue, withValue):
        """
        Update value (entry) of a table.

        Args:
            toTable (str): The table name.
            atColumn (str): The attribute name.
            withKeyName (str): The primary key attribute name of a table. 
            withKeyValue (str): The primary key value of the target row.
            withValue (str/int): The new value.

        Returns:
            str: The command for updating the value. 
        """
        tableName = toTable
        attributeName = atColumn
        keyName = withKeyName
        keyValue = withKeyValue
        value = withValue
        if type(value) is str:
            command = f"UPDATE {tableName} SET {attributeName} = '{str(value)}' WHERE {keyName} = '{str(keyValue)}'"
        elif type(value) is int:
            command = f"UPDATE {tableName} SET {attributeName} = {str(value)} WHERE {keyName} = '{str(keyValue)}'"

        thread = threading.Thread(target=self.__updateValue, args=(command, ))
        thread.name = 'updateValue'
        thread.start()
        return command

    def __updateValue(self, command):
        """
        The thread routing of updateValue

        Args:
            command (str): The command to be sent to the database.
        """
        with self.curLock:
            self.cur.execute(command)
            self.con.commit()
    
    def queryResToList(self, res):
        """
        Convert the database query result to a list

        Args:
            res (): The raw query result.

        Returns:
            list: The query result in list format. 
        """
        l = []
        l = list(map(lambda x: x[0], res))
        return l
    
    def executeQueryCommand(self, command):
        """
        Query the database.

        Args:
            command (str): The query command.

        Returns:
            list: The query result in list format.
        """
        with self.curLock:
            res = self.cur.execute(command).fetchall()
        return self.queryResToList(res)
        

    def printAllTableNames(self):
        """
        Print all table names in this database.
        """
        for row in self.cur.execute("SELECT name FROM sqlite_master"):
            print(row)
    
    def printTable(self, withTableName, orderedBy = ''):
        """
        Print a complete table in this database.

        Args:
            withTableName (str): The target table name. 
            orderedBy (str, optional): An attribute name with which we want to sort the result. Defaults to ''.
        """
        tableName = withTableName
        if orderedBy == '':
            command = f"SELECT * FROM {tableName}"
        else:
            command = f"SELECT * FROM {tableName} ORDERED BY {orderedBy}"
        with self.curLock:
            for row in self.cur.execute(command):
                print(row)
    
    def printATableRowCount(self, withTableName):
        """
        Print the number of rows in a table.

        Args:
            withTableName (str): The name of the target table.
        """
        tableName = withTableName
        command = f"SELECT COUNT(*) FROM {tableName}"
        with self.curLock:
            print(self.cur.execute(command).fetchone())

    def closeDatabase(self):
        """
        Disconnet the connection to the database. 
        """
        # todo commit?
        self.con.close()

#===========================================================================
#                            TEST CODE
#===========================================================================
    
if __name__ == '__main__':
    experimentFolderPath = "./testExperimentFolder"
    databaseName = 'myDatabase'
    os.system(f"rm {experimentFolderPath}/database/{databaseName}")
    myDatabase = MaintletDatabase(experimentFolderPath, databaseName)
    parameters = ('filename', 'duration', 'samplingRate', 'sampleWidth', 'recordChunk', 'playbackSamplingRate', 'playbackSampleWidth', 'playbackChunk', 'playbackFileNames', 'sensor1Type', 'sensor1Location', 'sensor2Type', 'sensor2Location', 'sensor3Type', 'sensor3Location', 'sensor4Type', 'sensor4Location', 'sensor5Type', 'sensor5Location', 'sensor6Type', 'sensor6Location', 'experimentName', 'experimentDescription')
    myDatabase.createTable(withName='beitong2', withParameter=parameters)
    myDatabase.printAllTableNames()
    value = [('09_23_2022_15_17_25_462742.wav', 2, 48000, 3, 4800, 44100, 2, 4800, 'testAudio/testRecordAndPlay.wav;testAudio/testRecordAndPlay.wav', 'NC', '', 'NC', '', 'vibration', 'on cs3113 desk', 'NC', '', 'NC', '', 'NC', '', 'test', 'no description')]
    myDatabase.insertValue(toTable='beitong2', withColumn=len(parameters), withValue=value)
    myDatabase.insertValue(toTable='beitong2', withColumn=len(parameters), withValue=value)
    myDatabase.printTable(withTableName='beitong2')
    myDatabase.printATableRowCount(withTableName='beitong2')
    print("Update duration value to 100")
    myDatabase.updateValue(toTable='beitong2', atColumn='duration', withKeyName='filename', withKeyValue="09_23_2022_15_17_25_462742.wav", withValue=100)
    myDatabase.printTable(withTableName='beitong2')
    myDatabase.printATableRowCount(withTableName='beitong2')

#============================= END OF TEST CODE==============================

