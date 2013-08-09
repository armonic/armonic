from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

import mss.lifecycle

import mss.modules.mysql
import mss.modules.wordpress
import mss.modules.apache
import mss.modules.varnish

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)


class XMLRPCServer(SimpleXMLRPCServer):

    def _dispatch(self, method, params):
        func = None
        try:
            func = self.funcs[method]
        except KeyError:
            if self.instance is not None:
                args = params[0][0]
                kwargs = params[0][1]
                return self.instance._dispatch(method, *args, **kwargs)

        if func is not None:
            return func(*params)
        else:
            raise Exception('method "%s" is not supported' % method)



port=8000
server = XMLRPCServer(("0.0.0.0", port),
                      requestHandler=RequestHandler,
                      allow_none=True,
                      logRequests=False)
server.register_introspection_functions()
server.register_instance(mss.lifecycle.LifecycleManager())

# Run the server's main loop
print "Server listening on port %d" % port
try:
    server.serve_forever()
except KeyboardInterrupt:
    print 'Exiting'
