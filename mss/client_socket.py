import socket
import pickle
import struct
import logging


class AgentException(Exception):
    pass

class ConnectionError(Exception):
    pass

class ClientSocket(object):
    def __init__(self, host="127.0.0.1", port=8000, cls_handler=logging.StreamHandler):
        self._host = host
        self._port = port
        self.handler = cls_handler()

    def _connect(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.connect((self._host, self._port))
        except socket.error as e:
            raise ConnectionError(e)

    def set_logging_handler(self, handler):
        """Set a handler. You can use handler defined by the standard logging module."""
        self.handler = handler

    def close(self):
        self._socket.close()

    def call(self, method, *args, **kwargs):
        request = {'method': method, 'args': args, 'kwargs': kwargs}
        return self._send_and_receive(request)

    def _receive_string(self):
        packer = struct.Struct("!I?")
        p = self._socket.recv(packer.size)
        size = packer.unpack(p)[0]
        last = packer.unpack(p)[1]
        ret = self._socket.recv(size)
        recv_size=len(ret)
        while recv_size != size:
            ret += self._socket.recv(size-recv_size)
            recv_size=len(ret)
        ret = pickle.loads(ret)
        return (last, ret)

    def _send_and_receive(self, request):
        self._connect()
        self._socket.sendall(pickle.dumps(request))
        ret = self._receive()
        pRet =  ret #pickle.loads(ret)
        self._socket.close()
        if "exception" in pRet:
            raise pRet['exception']
        elif "return" in pRet:
            return pRet['return']
        else:
            raise AgentException("Error: agent send no response!")

    def _receive(self):
        while True:
            (l, r) = self._receive_string()
            if l:
                break
            if r.levelno >= self.handler.level:
                self.handler.handle(r)
        return r
