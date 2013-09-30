#!/usr/bin/python
"""This is a client implementation module.

Actions needed to control agent:
- load a module
- get information about this module
"""

import argparse
import pprint
from prettytable import PrettyTable
import argcomplete

from mss.client_socket import ClientSocket

# client=ClientSocket("localhost", 8000)
# print client.call('list')

# exit(1)

# Print list of available methods
#print lfm.system.listMethods()


def read_string(string):
    try:
        return int(string)
    except ValueError:
        return string

def reqList(args):
    """take a list of "args:value" strings and return a dict"""
    acc={}
    for a in args:
        s=a.split(":")
        acc.update({s[0]:read_string(s[1])})
    return acc

def parseArgs(args):
    """take a list of "args:value" strings and return a dict"""
    acc={}
    if not args: return acc
    for r in args:
        a=reqList(r[1:])
        if r[0] in acc:
            acc[r[0]]=[acc[r[0]]]
            acc[r[0]].append(a)
        else: acc.update({r[0]:a})
    print acc
    return acc

# def parseArgs(args):
#     """take a list of "args:value" strings and return a dict"""
#     requires = {}
#     current_require = None
#     for require in args:
#         for variable in require:
#             if not ':' in variable:
#                 if not variable in requires:
#                     current_require = variable
#                     requires[current_require] = {}
#             else:
#                 variable, value = variable.split(':')
#                 if not variable in requires[current_require]:
#                     requires[current_require][variable] = [value]
#                 else:
#                     requires[current_require][variable].append(value)
#     print requires
#     return requires


def cmd_status(args):
    pass
def cmd_module(args):
    print client.call('lf_list')

def cmd_module_show(args):
    print client.call('lf_info',args.module)

def cmd_state(args):
    if args.long_description:
        x = PrettyTable(["State name", "Os-type", "Documentation"])
        x.align["State name"] = "l"
        x.align["Documentation"] = "l"
        x.padding_width = 1 # One space between column edges and contents (default)
        ret=client.call('state_list', args.module,doc=True,reachable=args.reachable)
        for r in ret:
            x.add_row([r['name'],r['os-type'],r['doc']])
        print x
    else:
        for s in client.call('state_list',args.module,reachable=args.reachable):
            print s
    

def cmd_state_current(args):
    print client.call('state_current', args.module)
def cmd_state_show(args):
    pass
def cmd_state_goto(args):
    if args.list_requires:
        ret=client.call('state_goto_requires', args.module, args.state)
        pprint.pprint(ret)
        x = PrettyTable(["Name","Type","ArgName", "ArgType","ArgDefault"])
        x.align["Name"] = "l"
        x.align["Type"] = "l"
        x.align["Default"] = "l"
        x.padding_width = 1 # One space between column edges and contents (default)
        for r in ret:
            x.add_row([r.name , r.type,"","",""])
            if r.type == 'simple':
                variables=r.variables
            else:
                variables=r.provide_args
            for a in variables:
                x.add_row(["","",a.name,a.type,a.default])
            x.add_row(["" , "","","",""])
        print x
            
    elif args.dryrun:
        pprint.pprint(client.call('state_goto_path', args.module, args.state))
    else:
        pprint.pprint(client.call('state_goto', args.module, args.state, parseArgs(args.require)))

def cmd_dot(args):
    print client.call('to_dot', args.module)

def cmd_provide(args):
    if args.state:
        ret=client.call('provide_list', args.module,state_name=args.state)
    else:
        ret=client.call('provide_list', args.module)

    x = PrettyTable(["Provide Name", "State Name","Args"])
    x.align["Provide Name"] = "l"
    x.align["State Name"] = "l"
    x.align["Args"] = "l"
    x.padding_width = 1 # One space between column edges and contents (default)
    for k in ret.iterkeys():
        for i in ret[k]:
            x.add_row([i['name'],k,i['args']])
    print x

def cmd_provide_show(args):
    ret=client.call('provide_list', args.module)
    if args.path:
        pprint.pprint(client.call('provide_call_path', args.module, args.provide))
    else:
        for i in ret.iterkeys():
            for j in ret[i]:
                if j['name'] == args.provide:
                    print j['args']

def cmd_provide_call(args):
    pprint.pprint(client.call('provide_call', args.module, args.provide, parseArgs(args.require), reqList(args.arg)))

def ModuleCompleter(prefix, parsed_args, **kwargs):
    try:
        client = ClientSocket(parsed_args.host, parsed_args.port)
    except Exception as e:
        argcomplete.warn("Connection error to mss agent %e" % e)
    ret = client.call('lf_list')
    return (m for m in ret if m.startswith(prefix))

def StateCompleter(prefix, parsed_args, **kwargs):
    try:
        client = ClientSocket(parsed_args.host, parsed_args.port)
    except Exception as e:
        argcomplete.warn("Connection error to mss agent %e" % e)
    ret = client.call('state_list',parsed_args.module)
    return (m for m in ret if m.startswith(prefix))


def ProvideCompleter(prefix, parsed_args, **kwargs):
    try:
        client = ClientSocket(parsed_args.host, parsed_args.port)
    except Exception as e:
        argcomplete.warn("Connection error to mss agent %e" % e)
    try : 
        state = parsed_args.state
    except AttributeError:
        state = None

    if state:
        ret=client.call('provide_list', parsed_args.module,state_name=state)
    else:
        ret=client.call('provide_list', parsed_args.module)
    tmp=[]
    for k in ret.iterkeys():
        for i in ret[k]:
          tmp += [i['name']]
    return (m for m in tmp if m.startswith(prefix))


parser = argparse.ArgumentParser(prog='mss3-client')
parser.add_argument('--port','-P', type=int, default=8000,help='Mss agent port (default: %(default)s))')
parser.add_argument('--host','-H', type=str, default="localhost",help='Mss agent host (default: %(default)s))')
parser.add_argument('--protocol', type=str,choices=['socket','xmlrpc'], default="socket",help='Protocol (default: %(default)s))')
parser.add_argument('--version',"-V", action='version', version='%(prog)s ' + "0.1")
parser.add_argument('--verbose',"-v", type=int,default=10,help="Between 10 (DEBUG) and 50 (ERROR)")
subparsers = parser.add_subparsers(help='<subcommand>')

parser_status = subparsers.add_parser('status', help='Show status of agent.')
parser_status.set_defaults(func=cmd_status)


parser_module = subparsers.add_parser('module', help='List available modules.')
parser_module.set_defaults(func=cmd_module)

parser_module_show = subparsers.add_parser('module-show', help='Show a module.')
parser_module_show.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_module_show.set_defaults(func=cmd_module_show)


parser_state = subparsers.add_parser('state', help='List available states of a module')
parser_state.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_state.add_argument('--long-description','-l',action='store_true',help="Show long description")
parser_state.add_argument('--reachable','-r',action='store_true',help="Only reachable states from current state")
parser_state.set_defaults(func=cmd_state)

parser_state_current = subparsers.add_parser('state-current', help='Show current state of a module')
parser_state_current.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_state_current.set_defaults(func=cmd_state_current)

parser_state_show = subparsers.add_parser('state-show', help='Show a state of a module')
parser_state_show.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_state_show.add_argument('state' , type=str, help='a state').completer = StateCompleter
parser_state_show.set_defaults(func=cmd_state_show)

parser_state_goto = subparsers.add_parser('state-goto', help='Go to a state of a module')
parser_state_goto.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_state_goto.add_argument('state' , type=str, help='a state').completer = StateCompleter
parser_state_goto.add_argument('-R',dest="require" , type=str,  nargs="*", action='append' , help="specify requires. Format is 'require_name value1:value value2:value'")
parser_state_goto.add_argument('--dryrun','-n',action='store_true',help="Dryrun mode")
parser_state_goto.add_argument('--list-requires','-l',action='store_true',help="List Requires to go to this path")
parser_state_goto.set_defaults(func=cmd_state_goto)


parser_provide = subparsers.add_parser('provide', help='List all provide of a module')
parser_provide.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_provide.add_argument('state' , type=str, nargs='?', default=None, help='a state').completer = StateCompleter
parser_provide.set_defaults(func=cmd_provide)

parser_provide_show = subparsers.add_parser('provide-show', help='Show arguments of a provide.')
parser_provide_show.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_provide_show.add_argument('provide' , type=str, help='a provide').completer = ProvideCompleter
parser_provide_show.add_argument('--path','-p',action='store_true',help="print path to call this provide")
parser_provide_show.set_defaults(func=cmd_provide_show)

parser_provide_call = subparsers.add_parser('provide-call', help='Call a provide.')
parser_provide_call.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_provide_call.add_argument('provide' , type=str, help='a provide').completer = ProvideCompleter
parser_provide_call.add_argument('-R',dest="require" , type=str,  nargs="*", help="specify requires. Format is 'require_name value1:value value2:value'")
parser_provide_call.add_argument('-A',dest="arg" , type=str, nargs="*", help="Specify provide argument. Format is 'arg1:value1 arg2:value2 ...'")
parser_provide_call.set_defaults(func=cmd_provide_call)

argcomplete.autocomplete(parser)
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
#    format = '%(asctime)s|%(levelname)6s - %(message)s'
    format = '%(asctime)s|%(levelname)6s %(ip)15s - %(message)s'
    sh = logging.StreamHandler()
    sh.setLevel(args.verbose)
    sh.setFormatter(logging.Formatter(format))
    client = ClientSocket(args.host, args.port)
    client.add_logging_handler(sh)
    args.func(args)


exit(1)





################################################################################
################################################################################

# DEPRECATED CLIENT

################################################################################
################################################################################

def cmd_list(args):
    pprint.pprint(client.call('list'))

def cmd_info(args):
    pprint.pprint(client.call('info'))

def cmd_provide(args):
    if args.provide:
        if args.requires_list:
            pprint.pprint(client.call('provide_call_requires', args.module, args.provide))
        elif args.path:
            pprint.pprint(client.call('provide_call_path', args.module, args.provide))
        elif args.arguments:
            pprint.pprint(client.call('provide_call_args', args.module, args.provide))
        elif args.call:
            if not args.require:
                args.require = ""
            if not args.arg:
                args.arg = ""
            pprint.pprint(client.call('provide_call', args.module, args.provide, parseArgs(args.require), reqList(args.arg)))
    else:
        pprint.pprint(client.call('provide_list', args.module))

def cmd_goto(args):
    pass
def cmd_dot(args):
    print client.call('to_dot', args.module)

def cmd_current(args):
    print client.call('state_current', args.module)



parser_list = subparsers.add_parser('list', help='list available modules')
parser_list.set_defaults(func=cmd_list)

parser_info = subparsers.add_parser('info', help='list available modules')
parser_info.set_defaults(func=cmd_info)

parser_dot = subparsers.add_parser('dot', help='dot modules statemachine')
parser_dot.add_argument('module', type=str, help='a module')
parser_dot.set_defaults(func=cmd_dot)

parser_getState = subparsers.add_parser('states', help='list available states of module')
parser_getState.add_argument('module', type=str, help='a module')
parser_getState.add_argument('--doc','-d',action='store_true',help="Print state documentation")
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
    format = '%(asctime)s|%(levelname)6s %(ip)15s - %(message)s'
    sh = logging.StreamHandler()
    sh.setLevel(args.verbose)
    sh.setFormatter(logging.Formatter(format))
    client = ClientSocket(args.host, args.port)
    client.set_logging_handler(sh)
    args.func(args)
