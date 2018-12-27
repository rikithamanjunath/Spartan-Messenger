from concurrent import futures

import grpc
import time
import chat_pb2 as chat
import chat_pb2_grpc as rpc
import yaml

# 30 seconds for rate limit
TIME_LIMIT = 30

class ChatServer(rpc.ChatServerServicer):

    def __init__(self,chatSet,validGroups,ratelimiter,maxCachelimit,RateLimitperUser):
        # List with all the chat history
        self.chats = chatSet
        self.validGroups = validGroups
        self.ratelimiter = ratelimiter
        self.RateLimitperUser= RateLimitperUser
        self.maxCachelimit= maxCachelimit

    # This chat stream will be used to send new messages to clients
    # Every client opens the connection and waits (listens) for the server to send the messages
    def ChatStream(self, me:chat.Note, context,):

        key = me.source+":"+me.destination
        lastindex = 0

        while True:
            # Check if there are any new messages
            while len(self.chats[key]) > lastindex:
                #  LRU cache implemetation
                # if more message in list than the cachecapacity  remove one by one, but also reduce the index
                while len(self.chats[key]) > maxCachelimit:
                    self.chats[key].pop(0)
                    lastindex -= 1
                # index should not be less than zero, edge case
                if lastindex < 0:
                    lastindex = 0
                n = self.chats[key][lastindex]
                lastindex += 1
                yield n

    def validateRateLimit(self,request):
        currentTime = time.time()
        # for the fist user
        # Ratelimiter(hashmap): key= user;  value = time
        if len(self.ratelimiter[request.source]) < RateLimitperUser:
            self.ratelimiter[request.source].append(currentTime)
            return chat.RateLimit(source="server",destination=request.source,message ="good")
        else:
            # after time limit 30 seconds, remove the entries of rate limiter
            while len(self.ratelimiter[request.source]) >= RateLimitperUser and ((currentTime - self.ratelimiter[request.source][0]) > TIME_LIMIT):
                self.ratelimiter[request.source].pop(0)
            if len(self.ratelimiter[request.source])>=RateLimitperUser:
                outputstr = "Reached limit of {}, Last Message not sent. Wait for  {} seconds".format(request.source,(TIME_LIMIT- (currentTime - self.ratelimiter[request.source][0])))
                print(outputstr)
                return chat.RateLimit(source="server",destination=request.source,
                                      message =outputstr)
            else:
                self.ratelimiter[request.source].append(currentTime)
                return chat.RateLimit(source="server",destination=request.source,message ="good")

    # @RateLimitperUser
    def SendNote(self, request: chat.Note, context):

        # This method is called when a client sends a message to the server.

        print("[{}-->{}] {}".format(request.source,request.destination, request.message))
        # Add it to the chat history
        rateLimitCheck = self.validateRateLimit(request)
        # only if its good then we store in cache(good --> <30 3 messages)
        if rateLimitCheck.message == "good":
            for dest in validGroups[request.destination]:
                key = dest + ":" + request.destination
                self.add(key, chat.Note(source=request.source,destination=request.destination,message=request.message))
        return rateLimitCheck


    # GEt the list for key and add value to list
    def add(self, key:str,value:chat.Note):
        self.chats[key].append(value)


# add users to the groups (valid groups )
def addGroup (grplist,groupName):
    validGroups[groupName] = list()
    for usr in grplist:
        validGroups[groupName].append(usr)
        chatSet[usr + ":" + groupName] = list()
        ratelimiter[usr] = list()

if __name__ == '__main__':

     # Read config file
    with open("config.yaml", 'r') as ymlfile:
        cfg = yaml.load(ymlfile)
        port = cfg['port']
        maxCachelimit = cfg['max_num_messages_per_user']
        RateLimitperUser = cfg['max_call_per_30_seconds_per_user']

    chatSet = {}
    validGroups = {}
    ratelimiter = {}

    grp1 = cfg['groups']['group1']
    grp2 = cfg['groups']['group2']
    addGroup(grp1,"group1")
    addGroup(grp2,"group2")

    # create a gRPC server

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=int(10)))
    rpc.add_ChatServerServicer_to_server(ChatServer(chatSet,validGroups,ratelimiter,maxCachelimit,RateLimitperUser), server)

    print('Starting server. Listening at {}'.format(port))
    server.add_insecure_port('[::]:' + str(port))
    server.start()
    # Server starts in background (another thread) so keep waiting
    while True:
        time.sleep(64 * 64 * 100)
