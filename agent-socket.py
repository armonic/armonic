#!/usr/bin/python
"""
Socket agent.

All logger event are send through the socket.
The return of function call is :
{"return":value} | {"exception":value}.
'value' is "picklized".

Protocol:
1) send a struct ((int) msg_size_in_bytes , (bool) last_msg?)
2) send message

"""

import logging
import logging.handlers
import pickle
import SocketServer
import struct

import mss.lifecycle
import mss.common

import mss.modules.mysql
import mss.modules.wordpress
import mss.modules.apache
import mss.modules.varnish

lfm = mss.lifecycle.LifecycleManager()


def sendString(socket,string,last=False):
    packer=struct.Struct("!I?")
    packet=pickle.dumps(string)
    p=packer.pack(len(packet),last)
    socket.send(p)
    socket.send(packet)

class SocketIO(object):
    def __init__(self,socket):
        self._socket=socket

    def write(self,string):
        try:
            sendString(self._socket,string)
        except:pass

class MyStreamHandler(logging.StreamHandler):
    """To send PROCESS log byte per byte."""
    def emit(self,record):
        self.stream.write(record)

class MyTCPHandler(SocketServer.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def redirect_log(self):
        # self.request is the TCP socket connected to the client
        socketIO=SocketIO(self.request)

        self._logger=logging.getLogger()
        self._logger.setLevel(logging.DEBUG)
#        format = '%(asctime)s|%(name)s|%(levelname)s: %(message)s'
        format = '%(asctime)s|%(levelname)7s: %(message)s'
#        self._logHandler = logging.StreamHandler(socketIO)
        self._logHandler = MyStreamHandler(socketIO)
        self._logHandler.setLevel(logging.DEBUG)
        self._logHandler.setFormatter(logging.Formatter(format))
        self._logger.addHandler(self._logHandler)

    def finish(self):
        try:
            self._logger.removeHandler(self._logHandler)
        except AttributeError:pass

    def parseRequest(self,data):
        """transform unicode to str. FIXME...  Some problems appear
        with augeas when unicode string are used to set it."""
        ret = pickle.loads(data)
        return ret

    def handle(self):
        data = self.request.recv(1024)
        request=self.parseRequest(data)
        self.redirect_log()

        try:
            ret = lfm._dispatch(request['method'], *request['args'], **request['kwargs'])
        except Exception as e:
            sendString(self.request,{'exception':e},True)
            raise
        else:
            sendString(self.request,{'return':ret},True)

class MyTCPServer(SocketServer.TCPServer):
    allow_reuse_address=True

if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 8000

    # Create the server, binding to localhost on port 9999

    print "Server listening on port %d"%PORT
    server = MyTCPServer((HOST, PORT), MyTCPHandler)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    server.serve_forever()
