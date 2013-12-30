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

import sys
import traceback
import os
import logging
import logging.handlers
import pickle
import SocketServer
import struct
import argparse

import mss.lifecycle
import mss.common

PACKET_INFO_SIZE = 5

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

format = '%(asctime)s|%(levelname)7s - %(message)s'
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter(format))

format = '%(asctime)s|%(name)20s|%(levelname)6s: %(message)s'
fh = logging.handlers.RotatingFileHandler("/tmp/mss.log", maxBytes=10485760, backupCount=5)
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter(format))

logger.addHandler(ch)
logger.addHandler(fh)


def my_send(socket, string):
    send_size = len(string)
    sent_size = socket.send(string)
    if sent_size < send_size:
        logger.warning("Packet has not been sent entirely: %d bytes instead of %d bytes." % (sent_size, send_size))

def sendString(socket,string,last=False):
    packer=struct.Struct("!I?")
    packet=pickle.dumps(string)
    p=packer.pack(len(packet),last)
    my_send(socket, p)
    my_send(socket, packet)

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
#        format = '%(asctime)s|%(levelname)7s %(ip)15s: %(message)s'
#        self._logHandler = logging.StreamHandler(socketIO)
        self._logHandler = MyStreamHandler(socketIO)
        self._logHandler.setLevel(logging.DEBUG)
#        self._logHandler.setFormatter(logging.Formatter(format))
        self._logHandler.addFilter(mss.common.NetworkFilter())
        self._logHandler.addFilter(mss.common.XpathFilter())
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
            # self._logger.exception doesn't go through the socket so we get
            # the traceback and include it in an error log
#            t, v, tb = sys.exc_info()
#            self._logger.error("Error while processing %s:\n%s" % (request['method'],
#                                                                   "".join(traceback.format_tb(tb))))
            self._logger.exception(e)
            sendString(self.request, {'exception': e}, True)
        else:
            sendString(self.request, {'return': ret}, True)

class MyTCPServer(SocketServer.TCPServer):
    allow_reuse_address=True

if __name__ == "__main__":
    modules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mss', 'modules')

    parser = argparse.ArgumentParser(prog=__file__)
    parser.add_argument('--port','-P', type=int, default=8000, help='MSS agent port (default: %(default)s))')
    parser.add_argument('--host','-H', type=str, default="0.0.0.0", help='MSS agent IP (default: %(default)s))')
    parser.add_argument('--modules-dir', type=str, default=modules_dir, help='MSS modules location (default: %(default)s)')
    parser.add_argument('--include-module', dest="module", type=str, nargs="*", default=None, help='Specify which module directory name to import (by default all modules are imported)')

    args = parser.parse_args()
    mss.common.load_lifecycles(os.path.abspath(args.modules_dir),include_modules=args.module)
    lfm = mss.lifecycle.LifecycleManager()

    print "Server listening on %s:%d" % (args.host, args.port)
    print "Using modules from %s " % args.modules_dir
    server = MyTCPServer((args.host, args.port), MyTCPHandler)
    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print "Exiting."
