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

from mss.client_socket import ClientSocket

import os

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
            acc[r[0]].append(a)
        else: acc.update({r[0]:[a]})
    return acc

def provide_to_table(provide):
    x = PrettyTable(["Provide Name","Require name", "Type", "ArgName", "ArgType", "ArgDefault", "Extra"])
    x.align["Require Name"] = "l"
    x.padding_width = 1 # One space between column edges and contents (default)
    x.add_row([provide.name, "", "","","","",""])
    for r in provide:
        x.add_row(["", r.name , r.type,"","","",""])
        for a in r.variables():
            if r.type == 'user':
                x.add_row(["", "","",a.name,a.type,a.default,r.provided_by])
            else:
                x.add_row(["", "","",a.name,a.type,a.default,""])
        x.add_row(["", "" , "","","","",""])
    print x



def require_to_table(requires):
    x = PrettyTable(["Require Name","Type","ArgName", "ArgType","ArgDefault","Extra"])
    x.align["Require Name"] = "l"
    x.padding_width = 1 # One space between column edges and contents (default)
    for r in requires:
        if r.type in ['external', 'local']:
            x.add_row([r.name, r.type, "", "", "", r.xpath])
        else:
            x.add_row([r.name, r.type, "", "", "", ""])
        if r.type in ['simple', 'user']:
            variables=r.variables()
        else:
            variables=r.provide_args + r.provide_ret
        for a in variables:
            if r.type == 'user':
                x.add_row(["","",a.name,a.type,a.default,r.provided_by])
            else:
                x.add_row(["","",a.name,a.type,a.default,""])
        x.add_row(["" , "","","","",""])
    print x

def state_to_table(state):
    x = PrettyTable(["Property","Value"])
    x.align = "l"
    x.add_row(["Name",state['name']])
    x.add_row(["Xpath",state['xpath']])
    x.add_row(["Supported OS","\n".join(map(str,state['supported_os_type']))])
    x.add_row(["Provides","\n".join([p['name'] for p in state['provides']])])
    x.add_row(["Entry Requires","\n".join([p['name'] for p in state['requires_entry']['require_list']])])
    print x

def dict_to_table(dct):
    x = PrettyTable(["Property","Value"])
    x.align = "l"
    for k, v in dct.items():
        x.add_row([k,v])
    print x

def cmd_status(args):
    pass

def cmd_lifecycle(args):
    if args.long_description:
        for m in client.call('lifecycle', xpath = args.xpath, doc = True):
            dict_to_table(m)
    else:
        for m in client.call('lifecycle', xpath = args.xpath, doc = False):
            print m

def cmd_xpath(args):
    if args.uri:
        pprint.pprint(client.call('uri', args.xpath))
    else:
        for r in client.call('xpath', args.xpath):
            print r

def cmd_state(args):
    if args.long_description:
        for r in client.call('state', xpath=args.xpath, doc=True):
            state_to_table(r)

    elif args.requires_list:
        ret=client.call('state_goto_requires', args.xpath)
        for r in ret:
            print r['xpath']
            require_to_table(r['requires'])
    elif args.path:
        pprint.pprint(client.call('state_goto_path', args.xpath))

    else:
        for s in client.call('state', xpath=args.xpath, doc=False):
            print s

def cmd_state_current(args):
    for r in client.call('state_current', args.xpath):
        dict_to_table(r)

def cmd_state_goto(args):
    pprint.pprint(client.call('state_goto', args.xpath, parseArgs(args.require)))

def cmd_dot(args):
    print client.call('to_dot', args.module)

def cmd_provide(args):
    if args.path:
        ret = client.call('provide_call_path', args.xpath)
        for r in ret:
            print r['xpath']
            for a in r['actions']:
                print "\t", a
        return
        
    ret=client.call('provide', args.xpath)
    for provide in ret:
        print provide.get_xpath()
        if args.long_description:
            provide_to_table(provide)
            req=client.call('provide_call_requires', xpath=args.xpath)
            require_to_table(req)
            print ""

def cmd_provide_call(args):
    pprint.pprint(client.call('provide_call', args.xpath, parseArgs(args.require), parseArgs(args.args)))

def cmd_plot(args):
    if args.T == 'dot':
        print client.call('to_dot', args.module, reachable = args.reachable)
    elif args.T == 'json':
            print json.dumps(client.call('to_primitive', args.module, reachable = args.reachable))
    elif args.T == 'json-human':
            pprint.pprint(client.call('to_primitive', args.module, reachable = args.reachable))
    elif args.T == 'automaton':
        raise NotImplementedError
    elif args.T == 'xml':
        print(client.call('to_xml', args.module))


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


parser = argparse.ArgumentParser(
    prog='mss-client',
    description=("A simple client to contact a MSS3 agent. "
                 "It is mainly used to get informations "
                 "but can also do some simple actions."))
parser.add_argument('--port','-P', type=int, default=8000,help='Mss agent port (default: %(default)s)')
parser.add_argument('--host','-H', type=str, 
                    default=os.environ.get('MSS_AGENT_HOST', "localhost")
                    ,help="Mss agent host (default: '%(default)s'). Agent host can also be specified with env variable 'MSS_AGENT_HOST'")
parser.add_argument('--protocol', type=str,choices=['socket','xmlrpc'], default="socket",help='Protocol (default: %(default)s))')
parser.add_argument('--version',"-V", action='version', version='%(prog)s ' + "0.1")
parser.add_argument('--verbose',"-v", type=int,default=10,help="Between 10 (DEBUG) and 50 (ERROR)")
subparsers = parser.add_subparsers(help='<subcommand>')

parser_status = subparsers.add_parser('status', help='Show status of agent.')
parser_status.set_defaults(func=cmd_status)

parser_lifecycle = subparsers.add_parser('lifecycle', help='List lifecycles.')
parser_lifecycle.add_argument("xpath" , type=str, 
                          default="//*[@ressource='lifecycle']", nargs="?", 
                          help="A xpath. Default is '%(default)s' which matches all lifecycles.")
parser_lifecycle.add_argument('--long-description','-l',action='store_true',help="Show long description.")
parser_lifecycle.set_defaults(func=cmd_lifecycle)

parser_xpath = subparsers.add_parser('xpath', help='Get xpath')
parser_xpath.add_argument('xpath' , type=str, help='an xpath')
parser_xpath.add_argument('--uri','-u',action='store_true',help="Get uri associated to ressources that match the xpath.")
parser_xpath.set_defaults(func=cmd_xpath)

parser_state = subparsers.add_parser('state', help='List states.')
parser_state.add_argument("xpath" , type=str, 
                          default="//*[@ressource='state']", nargs="?", 
                          help="A xpath. Default is '%(default)s' which matches all states.")
parser_state.add_argument('--long-description','-l',action='store_true',help="Show long description.")
parser_state.add_argument('--path','-p',action='store_true',help="Show state path to go to these states.")
parser_state.add_argument('--requires-list','-r',action='store_true',help="List Requires to go to these states.")

parser_state.set_defaults(func=cmd_state)

parser_state_current = subparsers.add_parser('state-current', help='Show current state of a module.')
parser_state_current.add_argument('xpath' , type=str, help='a xpath that correspond to lifecycles.')
parser_state_current.set_defaults(func=cmd_state_current)

parser_state_goto = subparsers.add_parser('state-goto', help='Go to a state of a module.')
parser_state_goto.add_argument('xpath' , type=str, help='a xpath that correspond to a unique state.')
parser_state_goto.add_argument('-R',dest="require" , type=str,  nargs="*", action='append' , help="specify requires. Format is 'require_name value1:value value2:value'.")
parser_state_goto.set_defaults(func=cmd_state_goto)


parser_provide = subparsers.add_parser('provide', help='List provides.')
parser_provide.add_argument('xpath' , type=str, help='a xpath')
parser_provide.add_argument('--long-description','-l',action='store_true',help="Show long description")
parser_provide.add_argument('--path','-p',action='store_true',help="Show the path of state to call the provides")
parser_provide.set_defaults(func=cmd_provide)

parser_provide_call = subparsers.add_parser('provide-call', help='Call a provide.')
parser_provide_call.add_argument('xpath' , type=str, help='a xpath')
parser_provide_call.add_argument('-R',dest="require" , type=str,  nargs="*", action='append', help="specify requires. Format is 'require_name value1:value value2:value'")
parser_provide_call.add_argument('-A',dest="args" , type=str, nargs="*", action='append', help="Specify provide argument. Format is 'arg1:value1 arg2:value2 ...'")
parser_provide_call.set_defaults(func=cmd_provide_call)

parser_plot = subparsers.add_parser('plot', help='Plot a lifecycle')
parser_plot.add_argument('module' , type=str, nargs='?', help='a module').completer = ModuleCompleter
parser_plot.add_argument('--reachable','-r',action='store_true',help="Only reachable states from current state")
parser_plot.add_argument('-T', choices=['dot','json','json-human','automaton','xml'],help="print path to call this provide. For xml format, you can pipe mss stdout to xmllint --format - to have a indented output ('client.py plot -T xml | xmllint --format -').")
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
    format = '%(asctime)s|%(levelname)6s - %(ip)s/%(xpath)s - %(message)s'
    sh = logging.StreamHandler()
    sh.setLevel(args.verbose)
    sh.setFormatter(logging.Formatter(format))
    client = ClientSocket(args.host, args.port)
    client.add_logging_handler(sh)
    args.func(args)