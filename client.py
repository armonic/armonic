#!/usr/bin/python
"""This is a client implementation module.

Actions needed to control agent:
- load a module
- get information about this module
"""

import argparse
import pprint

# Print list of available methods
#print lfm.system.listMethods()

def reqList(args):
    """take a list of "args:value" strings and return a dict"""
    acc={}
    for a in args:
        s=a.split(":")
        acc.update({s[0]:s[1]})
    return acc


def parseArgs(args):
    """take a list of "args:value" strings and return a dict"""
    acc={}
    if not args: return acc
    for r in args:
        a=reqList(r[1:])
        if r[0] in acc:
            acc[r[0]].append(a)
        else: acc.update({r[0]:[a]})
    return acc

def cmd_list(args):
    pprint.pprint(client.call('list'))

def cmd_get_states(args):
    pprint.pprint(client.call('get_states', args.module))

def cmd_provide(args):
    if args.provide:
        if args.requires_list:
            pprint.pprint(client.call('get_provide_requires', args.module, args.provide))
        elif args.path:
            pprint.pprint(client.call('get_provide_path', args.module, args.provide))
        elif args.arguments:
            pprint.pprint(client.call('get_provide_args', args.module, args.provide))
        elif args.call:
            if not args.require:
                args.require = ""
            if not args.arg:
                args.arg = ""
            pprint.pprint(client.call('call_provide', args.module, args.provide, parseArgs(args.require), reqList(args.arg)))
    else:
        pprint.pprint(client.call('get_provides', args.module))

def cmd_goto(args):
    if args.list_requires:
        pprint.pprint(client.call('get_state_requires', args.module, args.state))
    elif args.dryrun:
        pprint.pprint(client.call('get_state_path', args.module, args.state))
    else:
        pprint.pprint(client.call('goto_state', args.module, args.state, parseArgs(args.require)))

def cmd_dot(args):
    print client.call('to_dot', args.module)

def cmd_current(args):
    print client.call('get_current_state', args.module)

parser = argparse.ArgumentParser(prog='mss')
parser.add_argument('--port','-P', type=int, default=8000,help='Mss agent port (default: %(default)s))')
parser.add_argument('--host','-H', type=str, default="localhost",help='Mss agent host (default: %(default)s))')
parser.add_argument('--protocol', type=str,choices=['socket','xmlrpc'], default="xmlrpc",help='Protocol (default: %(default)s))')
parser.add_argument('--version',"-V", action='version', version='%(prog)s ' + "0.1")
parser.add_argument('--verbose',"-v", type=int,default=10,help="Between 10 (DEBUG) and 50 (ERROR)")
subparsers = parser.add_subparsers(help='sub-command help')

parser_list = subparsers.add_parser('list', help='list available modules')
parser_list.set_defaults(func=cmd_list)

parser_dot = subparsers.add_parser('dot', help='dot modules statemachine')
parser_dot.add_argument('module', type=str, help='a module')
parser_dot.set_defaults(func=cmd_dot)

parser_getState = subparsers.add_parser('states', help='list available states of module')
parser_getState.add_argument('module', type=str, help='a module')
parser_getState.set_defaults(func=cmd_get_states)

parser_provide = subparsers.add_parser('provide', help='Call a provide, list needed requires and arguments to call it. Without provide arguement, list all provide of the module.')
parser_provide.add_argument('module' , type=str, help='a module')
parser_provide.add_argument('provide' , type=str, nargs="?", help='provide name')
parser_provide.add_argument('-R',dest="require" , type=str,  nargs="*", help="specify requires. Format is 'require_name value1:value value2:value'")
parser_provide.add_argument('-A',dest="arg" , type=str, nargs="*", help='specify provide arguments')
parser_provide.add_argument('--requires-list','-r',action='store_true',help="list requires to call this provide")
parser_provide.add_argument('--arguments','-a',action='store_true',help="print path to call this provide")
parser_provide.add_argument('--path','-p',action='store_true',help="print path to call this provide")
parser_provide.add_argument('--call','-c',action='store_true',help="call this provide")
parser_provide.set_defaults(func=cmd_provide)

parser_goto = subparsers.add_parser('goto', help='Go to a module state')
parser_goto.add_argument('module' , type=str, help='a module')
parser_goto.add_argument('state' , type=str, help='a module')
parser_goto.add_argument('-R',dest="require" , type=str,  nargs="*", action='append' , help="specify requires. Format is 'require_name value1:value value2:value'")
parser_goto.add_argument('--dryrun','-n',action='store_true',help="Dryrun mode")
parser_goto.add_argument('--list-requires','-l',action='store_true',help="List Requires to go to this path")
parser_goto.set_defaults(func=cmd_goto)

parser_current = subparsers.add_parser('current', help='Current module state')
parser_current.add_argument('module' , type=str, help='a module')
parser_current.set_defaults(func=cmd_current)

args = parser.parse_args()

if args.protocol == "xmlrpc":
    from mss.client_xmlrpc import ClientXMLRPC, XMLRPCError
    client = ClientXMLRPC(args.host, args.port)
    try:
        args.func(args)
    except XMLRPCError as err:
        print "%s: %s" % (err.errno, err.error)
        exit(1)

elif args.protocol == "socket":
    from mss.client_socket import ClientSocket
    import logging
    format = '%(asctime)s|%(levelname)6s - %(message)s'
    sh = logging.StreamHandler()
    sh.setLevel(args.verbose)
    sh.setFormatter(logging.Formatter(format))
    client = ClientSocket(args.host, args.port)
    client.set_logging_handler(sh)
    args.func(args)
