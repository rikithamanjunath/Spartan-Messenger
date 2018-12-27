import threading
import yaml
#sudo python3 -m pip install pycryptodome
import grpc
import time
import sys


import chat_pb2 as chat
import chat_pb2_grpc as rpc

from Crypto import Random
from Crypto.Cipher import AES



class AESCipher():

    def __init__(self, encryptKey):
        self.key = b'[EX\xc8\xd5\xbfI{\xa2$\x05(\xd5\x18\xbf\xc0\x85)\x10nc\x94\x02)j\xdf\xcb\xc4\x94\x9d(\x9e'

    # Padding in order to be a multiple of key size
    def pad(self,s:str):
        # s=s.decode('utf-8')
        padMessage = s + "\0" * (AES.block_size - len(s) % AES.block_size)
        return padMessage.encode("utf-8")

    def encrypt(self,inputMessage):
        message=self.pad(inputMessage)
        iv = (Random.new().read(AES.block_size))
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return iv + cipher.encrypt(message)


    def decrypt(self,ciphertext):
        iv = ciphertext[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        plaintext = cipher.decrypt(ciphertext[AES.block_size:])
        return plaintext.rstrip(b"\0")


class Client:

    def __init__(self, username: str,groupName:str,encryptKey,maxCachelimit:str,RateLimitperUser:str):
        # the frame to put ui components on
        self.AES = AESCipher(encryptKey)
        self.username = username
        self.destination = groupName
        self.RateLimitperUser= RateLimitperUser
        self.maxCachelimit=maxCachelimit
        self.chat_list = []

        # create a gRPC channel + stub
        channel = grpc.insecure_channel(address + ':' + str(port))
        self.conn = rpc.ChatServerStub(channel)
        self.firstTime = 0

        print("[Spartan] Connected to Sparatan server at {} \n".format(port))
        print("Users in this group are {}".format(validGroups[self.destination]))

        # create new listening thread for when new message streams come in from the server
        threading.Thread(target=self.__listen_for_messages, daemon=True).start()
        # create a new thread to read the message from client side
        threading.Thread(target=self._read_message(), daemon=True).start()


    # Waiting for the new messages from the server
    def __listen_for_messages(self):

        me = chat.Note()
        me.source = self.username
        me.destination = self.destination
        me.message = self.AES.encrypt("register")
        for incomingNote in self.conn.ChatStream(me):
            if self.firstTime < maxCachelimit:
                self.firstTime = self.firstTime+1
                decrMessage = self.AES.decrypt(incomingNote.message)
                print("[{}] {}\n".format(incomingNote.source, decrMessage.decode('utf-8')))
                self.chat_list.append(decrMessage)
            elif self.username !=incomingNote.source:
                decrMessage = self.AES.decrypt(incomingNote.message)
                print("[{}] {}\n".format(incomingNote.source, decrMessage.decode('utf-8')))
                self.chat_list.append(decrMessage)


    # Read from command line input from the client
    def _read_message(self):
        inputText = None
        while inputText is None:
            inputText = input("[{}] > ".format(self.username))
            # reset so that read does not happen
            self.firstTime = maxCachelimit
            n = chat.Note()
            n.source = self.username
            n.destination = self.destination
            # Encrypt the message
            n.message = self.AES.encrypt(inputText)
            limitMessage = self.conn.SendNote(n)
            # Check on the rate limit  . If the signal(good) from server not good then notify user
            if limitMessage.message != "good":
                print("[{}] {}\n".format(limitMessage.source,limitMessage.message))
            inputText = None

# Add the group users to the list
def addGroup (grplist,groupName):
    validGroups[groupName] = list()
    for usr in grplist:
        validGroups[groupName].append(usr)


if __name__ == '__main__':

    # Read config file
    with open("config.yaml", 'r') as ymlfile:
        cfg = yaml.load(ymlfile)
        port = cfg['port']
        maxCachelimit = cfg['max_num_messages_per_user']
        RateLimitperUser = cfg['max_call_per_30_seconds_per_user']
        encryptKey = cfg['key']

        encryptKey1= b'[EX\xc8\xd5\xbfI{\xa2$\x05(\xd5\x18\xbf\xc0\x85)\x10nc\x94\x02)j\xdf\xcb\xc4\x94\x9d(\x9e'

    address = 'localhost'
    validGroups={}
    grp1 = cfg['groups']['group1']
    grp2 = cfg['groups']['group2']
    addGroup(grp1, "group1")
    addGroup(grp2, "group2")

    # check for valid number of argument, in python first argument is fileName not used
    if len(sys.argv) != 2:
        print("Error, please correct the number of arguments")
        exit(-1)

    username = sys.argv[1].strip()

    # check if the user is in any of the groups
    if not ( username in validGroups["group1"] or username in validGroups["group2"]) :
        # sys.argv[1] not in validGroups['group1'] or sys.argv[1] not in (validGroups['group2']):
        print("Error, please enter correct group")
        exit(-1)


    if username in validGroups["group1"]:
        key = "group1"
    else:
        key = "group2"

    c = Client(username,key,encryptKey,maxCachelimit,RateLimitperUser)

    while True:
        time.sleep(64 * 64 * 100)
