# -*- coding: UTF-8 -*-
#
# (c) 2010-2013 Mandriva, http://www.mandriva.com/
#
# This file is part of Mandriva Server Setup
#
# MSS is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# MSS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MSS; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import xmlrpclib
import logging
from socket import error as socket_error

logger = logging.getLogger(__name__)


class XMLRPCError(Exception):

    def __init__(self, errno, error):
        self.errno = errno
        self.error = error

    def __unicode__(self):
        return self.error

    def __repr__(self):
        return "<XMLRPCError(%s, %s)>" % (self.errno, self.error)


class ClientXMLRPC:
    """ Class to handle the xmlrpc calls """

    def __init__(self, host="127.0.0.1", port=8000):
        self._host = host
        self._port = port
        self._url = 'http://%s:%d' % (self._host, self._port)

    def call(self, method_name, *args, **kwargs):
        conn = xmlrpclib.ServerProxy(self._url)
        method = getattr(conn, method_name)
        try:
            return method((args, kwargs))
        except socket_error as err:
            raise XMLRPCError(err.errno, err[1])
        except xmlrpclib.Fault as err:
            raise XMLRPCError(err.faultCode, err.faultString)
        except xmlrpclib.ProtocolError as err:
            raise XMLRPCError(err.errcode, err.errmsg)
        except XMLRPCError:
            raise
        except:
            logger.exception("Exception while calling %s" % method_name)
            raise XMLRPCError(999, "Unknown error")
