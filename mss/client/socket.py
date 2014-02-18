from __future__ import absolute_import
import socket
import pickle
import struct
import logging

PACKET_INFO_SIZE = 5


class AgentException(Exception):
    pass


class ConnectionError(Exception):
    pass


class ClientSocket(object):
    """A simple socket client for mss agent.

    Logs emit by agent are forwarded to this client. To use them, add
    a logging handler with :py:meth:`add_logging_handler`
    or they can be specified as arguments at init time.

    :param handlers: To set handlers to forward agent logs
    :type handlers: [logging.Handler]

    """
    def __init__(self, host="127.0.0.1", port=8000, handlers=[]):
        self._host = host
        self._port = port
        self.handlers = handlers

    def _connect(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.connect((self._host, self._port))
        except socket.error as e:
            raise ConnectionError(e)

    def add_logging_handler(self, handler):
        """Set a handler. You can use handler defined by the standard
        logging module, for instance logging.StreamHandler"""
        self.handlers.append(handler)

    def close(self):
        self._socket.close()

    def call(self, method, *args, **kwargs):
        """Make a call to the agent. See
        :py:class:`mss.lifecycle.LifecycleManager` to know which methods can
        be called."""
        request = {'method': method, 'args': args, 'kwargs': kwargs}
        return self._send_and_receive(request)

    def provide_call_requires(self, xpath):
        return self.call("provide_call_requires", xpath=xpath)

    def provide_call_args(self, xpath):
        return self.call("provide_call_args", xpath=xpath)

    def provide_call(self, xpath, requires, provide_args):
        return self.call("provide_call", 
                         xpath=xpath, 
                         requires=requires, 
                         provide_args=provide_args)
        
    def uri(self, xpath):
        return self.call("uri", 
                         xpath=xpath)

    def _receive_string(self):
        packer = struct.Struct("!I?")
        recv_size = 0
        p = ""
        while recv_size < packer.size:
            p += self._socket.recv(packer.size - recv_size)
            recv_size = len(p)
        try:
            size = packer.unpack(p)[0]
        except struct.error:
            print "Struct error with packet:"
            print p
            raise
        last = packer.unpack(p)[1]
        ret = self._socket.recv(size)
        recv_size = len(ret)
        while recv_size < size:
            ret += self._socket.recv(size - recv_size)
            recv_size = len(ret)
        ret = pickle.loads(ret)
        return (last, ret)

    def _send_and_receive(self, request):
        self._connect()
        self._socket.sendall(pickle.dumps(request))
        ret = self._receive()
        pRet = ret  # pickle.loads(ret)
        self._socket.close()
        if "exception" in pRet:
            raise pRet['exception']
        elif "return" in pRet:
            return pRet['return']
        else:
            raise AgentException("Error: agent send no response!")

    def _receive(self):
        while True:
            (last_msg, r) = self._receive_string()
            if last_msg:
                break
            for h in self.handlers:
                if r.levelno >= h.level:
                    h.handle(r)
        return r
