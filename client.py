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
import json

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
            if type(acc[r[0]]) != list:
                acc[r[0]]=[acc[r[0]]]
            acc[r[0]].append(a)
        else: acc.update({r[0]:a})
    return acc

def require_to_table(requires):
    x = PrettyTable(["Require Name","Type","ArgName", "ArgType","ArgDefault","Extra"])
    x.align["Require Name"] = "l"
    x.padding_width = 1 # One space between column edges and contents (default)
    for r in requires:
        x.add_row([r.full_name , r.type,"","","",""])
        if r.type in ['simple', 'user']:
            variables=r.variables
        else:
            variables=r.provide_args
        for a in variables:
            if r.type == 'user':
                x.add_row(["","",a.full_name,a.type,a.default,r.provided_by])
            else:
                x.add_row(["","",a.full_name,a.type,a.default,""])
        x.add_row(["" , "","","","",""])
    print x


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
        require_to_table(ret)
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
    for k in ret.iterkeys():
        for i in ret[k]:
            x.add_row([i.name,k,i.get_all_variables()])
    print x

def cmd_provide_show(args):
    if args.path:
        pprint.pprint(client.call('provide_call_path', args.module, args.provide))
    else:
        ret=client.call('provide_call_args', args.module, args.provide)
        require_to_table(ret)

def cmd_provide_call(args):
    pprint.pprint(client.call('provide_call', args.module, args.provide, parseArgs(args.require), parseArgs(args.args)))

def cmd_plot(args):
    if args.T == 'dot':
        print client.call('to_dot', args.module)
    elif args.T == 'json':
            print json.dumps(client.call('to_primitive', args.module))
    elif args.T == 'json-human':
            pprint.pprint(client.call('to_primitive', args.module))
    elif args.T == 'automaton':
        raise NotImplementedError


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
          tmp += [i.name]
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
parser_provide_call.add_argument('-R',dest="require" , type=str,  nargs="*", action='append', help="specify requires. Format is 'require_name value1:value value2:value'")
parser_provide_call.add_argument('-A',dest="args" , type=str, nargs="*", action='append', help="Specify provide argument. Format is 'arg1:value1 arg2:value2 ...'")
parser_provide_call.set_defaults(func=cmd_provide_call)

parser_plot = subparsers.add_parser('plot', help='Plot a lifecycle')
parser_plot.add_argument('module' , type=str, help='a module').completer = ModuleCompleter
parser_plot.add_argument('-T', choices=['dot','json','json-human','automaton'],help="print path to call this provide")
parser_plot.set_defaults(func=cmd_plot)


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
