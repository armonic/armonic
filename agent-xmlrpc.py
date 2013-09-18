import os
import argparse
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

import mss.lifecycle
import mss.common


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


if __name__ == "__main__":
    modules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mss', 'modules')

    parser = argparse.ArgumentParser(prog=__file__)
    parser.add_argument('--port','-P', type=int, default=8000, help='MSS agent port (default: %(default)s))')
    parser.add_argument('--host','-H', type=str, default="0.0.0.0", help='MSS agent IP (default: %(default)s))')
    parser.add_argument('--modules-dir', type=str, default=modules_dir, help='MSS modules location (default: %(default)s))')
    args = parser.parse_args()

    mss.common.load_lifecycles(args.modules_dir)
    lfm = mss.lifecycle.LifecycleManager()

    server = XMLRPCServer((args.host, args.port),
                          requestHandler=RequestHandler,
                          allow_none=True,
                          logRequests=False)
    server.register_introspection_functions()
    server.register_instance(lfm)

    print "Server listening on %s:%d" % (args.host, args.port)
    print "Using modules from %s " % args.modules_dir
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print 'Exiting.'
