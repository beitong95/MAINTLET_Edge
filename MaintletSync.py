from threading import Lock
from MaintletLog import logger
import traceback
class MaintletSyncManager:
    """
    Sync database and files between the client and the server 
    1. make sure the file is sent and the database entry is sent
    2. after 1, clean up redundant data
    """    
    def __init__(self, networkManager, dataCollector):
        """
        Init

        Args:
            networkManager (MaintletNetworkManager): network manager obj
            dataCollector (MaintletDataCollection): data collection obj
        """        
        self.networkManager = networkManager
        self.audioInterface = dataCollector

        self.pendingTransactions = {} # a dictionary stores all pending transactions
        self.finishAckMessages = set()
        self.DVMessages = set() # data visualization messages
        self.filenameToMid = {}
        # Lock for shared dict pendingTransaction
        self.pendingTransactionsLock = Lock()
        # Flag for killing the thread
        self.stopThread = False

        # if we specify the record count, we will shorten the check period to exit faster
        if self.audioInterface.recordCount == 0:
            self.checkPendingMessagePeriod = 10
        else:
            self.checkPendingMessagePeriod = 1
    
    def start(self):
        # set up network services
        self.deviceMac = self.audioInterface.deviceMac
        self.serverIP = self.audioInterface.serverIP
        self.serverUsername = self.audioInterface.serverUsername
        self.serverFileFolder = self.audioInterface.serverFileFolder
        self.MQTTQos = self.audioInterface.MQTTQos
        self.tableName = self.audioInterface.tableName
        self.keyName = 'key'

        # topic format
        # maintlet<Send/Reply>/MACOfDevice/[subTopic]
        self.sendTopic = f"maintletSend/{self.deviceMac}/{self.tableName}"
        self.replyTopic = f"maintletReply/{self.deviceMac}/#"

        # MQTT
        try:
            self.networkManager.connectMQTT(self.deviceMac, self.serverIP, self.MQTTQos, self.sendTopic, self.replyTopic, self.on_publish, self.on_message)
        except Exception as e:
            logger.error(traceback.format_exc())

        # SCP
        try:
            self.networkManager.connectSCPServer(self.serverIP, self.serverUsername, self.serverFileFolder, self.SCPProgressCallback)
        except Exception as e:
            logging.error(traceback.format_exc())
            MaintletFail(f"Connection to SCP server {self.serverIP} Failed")

        # start the pendingTransaction checker thread
        thread = threading.Thread(target=self.checkPendingMessage)
        thread.name = 'checkPendingMessage'
        thread.start()

    def leave(self):
        if self.pendingTransactionsLock.locked():
            self.pendingTransactionsLock.release()
        self.stopThread = True

# REVIEW Text Parser
    def getMACFromTopic(self, text):
        return text.split('/')[1]
    
    def getSubTopicFromTopic(self, text):
        return text.split('/')[2]

    def getFilenameFromMessage(self, text):
        return text.split(',')[1][2:-1]

# REVIEW MQTT
    def on_message(self, client, userdata, msg):
        """
        How do we handle the reply message from the remote server
        """        

        # not necessary
        topic = msg.topic
        if self.getMACFromTopic(topic) != self.networkManager.deviceMac:
            print("wrong topic")
            return       

        # message handler
        # TODO: match the handler in a for loop, later we might have more complex protocols
        self.handleMQTTMessage(msg)
    
    def handleMQTTMessage(self, msg):
        """
        handle the reply

        Args:
            msg (byte obj): msg from the server
        """        
        topic = msg.topic

        subTopic = self.getSubTopicFromTopic(topic)
        filename = (msg.payload).decode('ascii')

        # FIXME find a more elegant way to exit
        if filename not in self.filenameToMid:
            return

        mid = self.filenameToMid[filename]

        # when we receive the database is commited
        if subTopic == 'database':
            # MaintletCheck(f"unlock Data sync for filename {filename}")
            with self.pendingTransactionsLock:
                message = str(self.pendingTransactions[mid].payload)
                self.pendingTransactions[mid].isDatabaseSyncSuccessed = True
                self.pendingTransactions[mid].timerSyncDatabase = time.time() - self.pendingTransactions[mid].timerSyncDatabase
                MaintletInfo(f"File: {self.pendingTransactions[mid].filename} - Sync Database with Mid {str(mid)} Success takes {round(self.pendingTransactions[mid].timerSyncDatabase*1000, 2)} ms")
                if self.pendingTransactions[mid].isRemovable():
                    self.pendingTransactions[mid].timerTransactionTime = time.time() - self.pendingTransactions[mid].timerTransactionTime
                    MaintletCheck(f"File: {self.pendingTransactions[mid].filename} - Transaction takes {round(self.pendingTransactions[mid].timerTransactionTime*1000, 2)} ms [database sync]")

                    threading.Thread(target=self.publishFinishACK, args=(message,)).start()

    
    def on_publish(self, client, userdata, mid):
        """
        This callback is important because even if the publish() call returns success, it does not always mean that the message has been sent.
        """        
        # This is for qos 0
        while not (mid in self.pendingTransactions or mid in self.finishAckMessages or mid in self.DVMessages):
            time.sleep(1/1e4)

        if mid in self.finishAckMessages:
            self.finishAckMessages.remove(mid)
            return

        if mid in self.DVMessages:
            self.DVMessages.remove(mid)
            return

        with self.pendingTransactionsLock:
            message = str(self.pendingTransactions[mid].payload)
            self.pendingTransactions[mid].isPublishSuccessed = True 
            self.pendingTransactions[mid].timerPublishMessage = time.time() - self.pendingTransactions[mid].timerPublishMessage
            # publish message time
            MaintletInfo(f"File: {self.pendingTransactions[mid].filename} - Transmit Message with Mid {str(mid)} with QoS {str(self.pendingTransactions[mid].qos)} Publish Success takes {round(self.pendingTransactions[mid].timerPublishMessage*1000, 2)} ms")
            if self.pendingTransactions[mid].isRemovable():
                self.pendingTransactions[mid].timerTransactionTime = time.time() - self.pendingTransactions[mid].timerTransactionTime
                MaintletCheck(f"File: {self.pendingTransactions[mid].filename} - Transaction takes {round(self.pendingTransactions[mid].timerTransactionTime*1000, 2)} ms [publish message]")
                # send file transmission ack to server
                threading.Thread(target=self.publishFinishACK, args=(message,)).start()


    def publishMessage(self, message, filepath, exitAfterFinish, key, transactionStartTime):
        """
        publish a message via mqtt client in networkmanager

        Args:
            message (string): message we want to publish
            filepath (string): the filepath (actually we can extract it from the message, here we pass it in for simplicity)
            exitAfterFinish (bool): if true, we exit after the transaction is finished (published, file transmitted, data synced)
            key (string): the key of the table, we will update the table later
            startSavingWavFileTime (float/double): the very beginning time when the transaction is generated, we will use it to track the total time of the transaction
        """        
        ret = self.networkManager.publishMessage(message)
        mid = ret[1]
        # cache pending transactions
        filename = filepath.split('/')[-1]
        with self.pendingTransactionsLock:
            # we need to save many info in each pending transaction entry for (1) delete file (2) update database (3) exit the program after the transaction is finished
            self.pendingTransactions[mid] = PendingTransaction(self.sendTopic, message, self.MQTTQos, mid, time.time(), filename, filepath, exitAfterFinish, keyValue=key, transactionStartTime=transactionStartTime)
            self.filenameToMid[filename] = mid

# REVIEW SCP
    def SCPProgressCallback(self, filename, size, sent):
        # sys.stdout.write("%s's progress: %.2f%%   \r" % (filename, float(sent)/float(size)*100) )
        if sent == size:
            # We successfully transmit the file to the server
            # set the file transmission check to True 
            filename = filename.decode('utf-8')

            # here we wait for the dict is filled by publish message
            while filename not in self.filenameToMid:
                time.sleep(0.001)
            
            with self.pendingTransactionsLock:
                mid = self.filenameToMid[filename]
                # set the file tranmission flag to true
                message = str(self.pendingTransactions[mid].payload)
                print("Message", message)
                self.pendingTransactions[mid].isFileTransmissionSuccessed = True 
                if self.pendingTransactions[mid].isRemovable():
                    self.pendingTransactions[mid].timerTransactionTime = time.time() - self.pendingTransactions[mid].timerTransactionTime
                    MaintletCheck(f"File: {self.pendingTransactions[mid].filename} - Transaction takes {round(self.pendingTransactions[mid].timerTransactionTime*1000, 2)} ms [file transmission]")
                
                    # send file transmission ack to server
                    threading.Thread(target=self.publishFinishACK, args=(message,)).start()

    def publishFinishACK(self, message):
        ret = self.networkManager.publishMessage(message,f"maintletSend/{self.deviceMac}/finishACK")
        mid = ret[1]
        self.finishAckMessages.add(mid)

    def publishDVMessage(self, message, topic):
        ret = self.networkManager.publishMessage(message, topic)
        mid = ret[1]
        self.DVMessages.add(mid)

    def sendFile(self, filepath, block=False):
        self.networkManager.transmitFile(filepath, block)

# REVIEW CHECK LOOP
    def checkPendingMessage(self):
        # we can check pending message periodically
        # or we can check at everyplaces where we update the success flags
        # step 1, put toBeDeleted Keys in a list
        # step 2, in the second round, delete them
        # the delete wait time D_T: 1 x period D_T < 2 x period 
        deleteListForPendingMessages = []
        deleteListForFilenameToMid = []

        while True and self.stopThread == False:
            counter = 0

            # why we split a long sleep to multiple short sleeps?
            # we want to exit this thread eariler
            # we can also set the thread as a daemon thread
            while counter < self.checkPendingMessagePeriod and self.stopThread == False:
                time.sleep(0.5)
                counter += 0.5
            
            # User asks to exit the program, so we exit in the fastest way
            if self.stopThread == True:
                break

            with MaintletTimer("Check pending messages") as mt:
                with self.pendingTransactionsLock:
                    # step2
                    for mid in deleteListForPendingMessages:
                        # extract stored entries from the pendingTransaction entry
                        filepath = self.pendingTransactions[mid].filepath
                        exitAfterFinish = self.pendingTransactions[mid].exitAfterFinish
                        keyValue = self.pendingTransactions[mid].keyValue

                        # remove the local file
                        process = subprocess.Popen(["rm", filepath])
                        # sts = os.waitpid(process.pid, 0)

                        # remove the key
                        del self.pendingTransactions[mid]

                        # update the local database success = true
                        # we change this update method to async to minimize the process time
                        command = self.audioInterface.database.updateValue(toTable=self.tableName, atColumn='transactionStatus', withKeyName=self.keyName, withKeyValue=keyValue, withValue='finished')
                        
                        MaintletCheck(command)
                        MaintletCheck(f"{filepath} with Message ID {str(mid)} is deleted")

                        if exitAfterFinish:
                            print("We have record enough files, Exit...")
                            self.audioInterface.closeAndExit()
                    for filename in deleteListForFilenameToMid:
                        del self.filenameToMid[filename]

                    # clean buffers
                    deleteListForPendingMessages = []
                    deleteListForFilenameToMid = []
                    
                    # step1
                    for mid, pendingTransaction in self.pendingTransactions.items():
                        if pendingTransaction.isRemovable():
                            # print(f"Message with Id {str(mid)} can be deleted")
                            deleteListForPendingMessages.append(mid)
                            deleteListForFilenameToMid.append(pendingTransaction.filename)

class PendingTransaction:
    def __init__(self, topic, payload, qos, mid, currentTime, filename, filepath, exitAfterFinish, keyValue, transactionStartTime):
        # topic of the message
        self.topic = topic
        # payload of the message
        self.payload = payload
        # qos of the transaction 
        self.qos = qos 
        # message id of this transaction
        self.mid = mid
        # record the time of message publish
        # update in on_publish
        self.timerPublishMessage = currentTime
        # update in on_message
        self.timerSyncDatabase = currentTime
        # update in all checkers
        self.timerTransactionTime = transactionStartTime
        # filename 
        self.filename = filename
        # filepath
        self.filepath = filepath
        # key of the entry in the database
        self.keyValue = keyValue
        # flag for exit the program when this transaction is finished 
        self.exitAfterFinish = exitAfterFinish

        # checks
        self.isPublishSuccessed = False
        self.isDatabaseSyncSuccessed = False
        self.isFileTransmissionSuccessed = False
    
    def isRemovable(self):
        return self.isPublishSuccessed and self.isDatabaseSyncSuccessed and self.isFileTransmissionSuccessed

def testPublish():
    testValue = "('09_25_2022_18_48_38_030066.wav', 2, 48000, 3, 4800, 44100, 2, 4800, 'testAudio/testRecordAndPlay.wav;testAudio/testRecordAndPlay.wav', 'NC', '', 'NC', '', 'vibration', 'on cs3113 desk', 'NC', '', 'NC', '', 'NC', '', 'test', 'no description', 'dc:a6:32:36:fb:62', 'rpi4 for test', '123', 'false')"
    testValue2 = "('09_25_2022_18_48_38_123456.wav', 2, 48000, 3, 4800, 44100, 2, 4800, 'testAudio/testRecordAndPlay.wav;testAudio/testRecordAndPlay.wav', 'NC', '', 'NC', '', 'vibration', 'on cs3113 desk', 'NC', '', 'NC', '', 'NC', '', 'test', 'no description', 'dc:a6:32:36:fb:62', 'rpi4 for test', '123', 'false')"
    networkManager = MaintletNetworkManager()
    syncManager = MaintletClientServerSyncManager(networkManager)
    # new test
    syncManager.start()
    syncManager.publishMessage(message=testValue)
    syncManager.sendFile(filepath='./test/testFiles/09_25_2022_18_48_38_030066.wav')
    time.sleep(2)
    syncManager.publishMessage(message=testValue2)
    syncManager.sendFile(filepath='./test/testFiles/09_25_2022_18_48_38_123456.wav')

    # old test
    # networkManager.connectMQTT(deviceMac='12:12:12:12:12:12', serverIP='130.126.138.110')
    # networkManager.connectSCPServer(serverIP='130.126.138.110', serverUserName='klara-storage-01', serverFileFolder='/home/klara-storage-01/maintlet/dump')
    # networkManager.transmitFile(filepath='./test/testFiles/09_25_2022_18_48_38_030066.wav')
    # networkManager.transmitFile(filepath='./test/testFiles/09_25_2022_18_48_38_123456.wav')
    # networkManager.publishMessage(message=testValue ,qos=2)
    # networkManager.publishMessage(message=testValue2,qos=2)

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break
    
    syncManager.leave()

if __name__ == "__main__":
    testPublish()
