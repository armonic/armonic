import pprint
from prettytable import PrettyTable
import json

import armonic.frontends.utils


def req_list(args):
    """take a list of "args:value" strings and return a dict"""
    acc = {}
    for a in args:
        s = a.split(":")
        acc.update({s[0]: armonic.frontends.utils.read_string(s[1])})
    return acc


def parse_args(args):
    """take a list of "args:value" strings and return a dict"""
    if args is None:
        return []

    # print args
    acc = {}
    # Take
    # [[req1, v1:x , v2:x], [req2, ...]]
    # Transform to
    # {req1:[[v1:x, v2:x], [v2:x], ...], req2:[...]}
    for a in args:
        if a[0] in acc:
            acc[a[0]].append(a[1:])
        else: acc.update({a[0]: [a[1:]]})
    ret = acc
    # print ret

    # Take
    # {req1:[[v1:x, v2:x], [v2:x], ...], req2:[...]}
    # Transform to
    # {req1/v1 : {0:x}, req1/v2 : {1:x}, ...}
    acc = {}
    for req, variables in ret.items():
        for i in range(0,len(variables)):
            for k,v in req_list(variables[i]).items():
                key = req+"/"+k
                if key in ret:
                    acc[key].update({i:v})
                else:
                    acc[key] = {i:v}
    ret = acc
    # print ret

    # Take
    # {req1/v1 : {0:x}, req1/v2 : {1:x}, ...}
    # Transform to
    # [(req1/v1 : {0:x}), (req1/v2 : {1:x}), ...]
    # Moreover, it adds // if needed
    acc = []
    for k, v in ret.items():
        if k.startswith("/"):
            xpath = k
        else :
            xpath = "//"+k
        acc.append((xpath, v))
    ret = acc
    # print ret

    ret = (ret, {'source': None, 'uuid': None})
    return ret


def provide_to_table(provide):
    try:
        print "  Label  : %s" % provide['extra']['label']
    except KeyError:
        pass
    try:
        print "  Tags   : %s" % provide['extra']['tags']
    except KeyError:
        pass
    try:
        print "  Help   : %s" % provide['extra']['help']
    except KeyError:
        pass

    for r in provide['requires']:
        print "  Require:    ", "%s type:%s" % (r['name'].ljust(15), r['type'].ljust(15))
        if r['type'] == 'simple':
            for a in r['variables_skel']:
                print "    Variable (args)  : ", "%s type:%s default:'%s'" % (a['name'].ljust(15),a['type'].ljust(8),a['default'])
        else:
            print "    Provide xpath    :  %s" % r['provide_xpath']
            for a in r['provide_args']:
                print "    Variable (args)  : ", "%s type:%s default:'%s'" % (a['name'].ljust(15),a['type'].ljust(8),a['default'])
            for a in r['provide_ret']:
                print "    Variable (return): ", "%s type:%s default:'%s'" % (a['name'].ljust(15),a['type'].ljust(8),a['default'])


def print_path(ret):
    """Get the return of provide|state_path method"""
    for r in ret:
        print
        print r['xpath']
        if r['paths'] == []:
            print "  can not be reached."
        for i, p in enumerate(r['paths']):
            print "path %i" % i
            for a in p:
                print "  ", "%5s " % a[1], a[0]


def state_to_table(state):
    x = PrettyTable(["Property","Value"])
    x.align = "l"
    x.add_row(["Name",state['name']])
    x.add_row(["Xpath",state['xpath']])
    x.add_row(["Supported OS","\n".join(map(str,state['supported_os_type']))])
    x.add_row(["Provides","\n".join([p['name'] for p in state['provides']])])
    x.add_row(["Enter Requires","\n".join([p['name'] for p in state['provide_enter']['requires']])])
    print x

def dict_to_table(dct):
    x = PrettyTable(["Property","Value"])
    x.align = "l"
    for k, v in dct.items():
        x.add_row([k,v])
    print x


class Cli(object):
    def __init__(self, parser):
        self.parser = parser
        self._add_arguments()

    def cmd_status(self, args):
        dict_to_table(self.client.info())

    def cmd_lifecycle(self, args):
        if args.long_description:
            for m in self.client.lifecycle(args.xpath, long_description=True):
                dict_to_table(m)
        else:
            for m in self.client.lifecycle(args.xpath):
                print m

    def cmd_xpath(self, args):
        if args.uri:
            pprint.pprint(self.client.call('uri', args.xpath))
        else:
            for r in self.client.call('xpath', args.xpath):
                print r

    def cmd_state(self, args):
        if args.long_description:
            for r in self.client.state(xpath=args.state_xpath, doc=True):
                state_to_table(r)

        elif args.requires_list:
            ret = self.client.state_goto_requires(args.state_xpath)
            for r in ret['requires']:
                print r['xpath']
                provide_to_table(r)
        elif args.path:
            print_path(self.client.state_goto_path(args.state_xpath))
        else:
            for s in self.client.state(xpath=args.state_xpath, doc=False):
                print s

    def cmd_state_current(self, args):
        for r in self.client.state_current(args.state_xpath):
            dict_to_table(r)

    def cmd_state_goto(self, args):
        args_require = None
        if args.require is not None:
            args_require = parse_args(args.require)
        elif args.json_require is not None:
            print args.json_require
            args_require = json.loads(args.json_require)

        pprint.pprint(self.client.state_goto(args.state_xpath_uri, args_require))

    def cmd_provide(self, args):
        if args.path:
            ret = self.client.provide_call_path(args.provide_xpath)
            print_path(ret)
            return
        else:
            ret=self.client.provide(args.provide_xpath)
            for provide in ret:
                if args.all:
                    print
                    print provide['xpath']
                    req=self.client.provide_call_requires(provide_xpath_uri=provide['xpath'])
                    for p in req:
                        print "Need: ", p['xpath']
                        if args.long_description:
                            provide_to_table(p)
                else:
                    print provide['xpath']
                    if args.long_description:
                        provide_to_table(provide)


    def cmd_provide_call(self, args):
        args_require = None
        if args.require is not None:
            args_require = parse_args(args.require)
        elif args.json_require is not None:
            print args.json_require
            args_require = json.loads(args.json_require)
        if args.check:
            ret = self.client.provide_call_validate(args.xpath, args_require)
            if ret['errors'] is False:
                print "Requires are valid."
            else:
                pprint.pprint(armonic.frontends.utils.require_validation_error(ret))
        else:
            pprint.pprint(self.client.provide_call(args.xpath,  args_require))

    def cmd_plot(self, args):
        if args.T == 'dot':
            print self.client.call('to_dot', args.module, reachable = args.reachable)
        elif args.T == 'json':
                print json.dumps(self.client.call('to_primitive', args.module, reachable = args.reachable))
        elif args.T == 'json-human':
                pprint.pprint(self.client.call('to_primitive', args.module, reachable = args.reachable))
        elif args.T == 'automaton':
            raise NotImplementedError
        elif args.T == 'xml':
            print(self.client.to_xml(args.module))


    def _add_arguments(self):
        help_require="specify requires. Format is 'require_name value1:value value2:value'. If the variable is a list, the format is 'require_name variable_list:[value1,value2,...]' (spaces are forbidden)."

        subparsers = self.parser.add_subparsers(help='<subcommand>')

        parser_status = subparsers.add_parser('status', help='Show status of agent.')
        parser_status.set_defaults(func=lambda a : self.cmd_status(a))

        parser_lifecycle = subparsers.add_parser('lifecycle', help='List lifecycles.')
        parser_lifecycle.add_argument("xpath" , type=str,
                                  default="//*[@ressource='lifecycle']", nargs="?",
                                  help="A xpath. Default is '%(default)s' which matches all lifecycles.")
        parser_lifecycle.add_argument('--long-description','-l',action='store_true',help="Show long description.")
        parser_lifecycle.set_defaults(func=lambda a : self.cmd_lifecycle(a))

        parser_xpath = subparsers.add_parser('xpath', help='Get xpath')
        parser_xpath.add_argument('xpath' , type=str, help='an xpath')
        parser_xpath.add_argument('--uri','-u',action='store_true',help="Get uri associated to ressources that match the xpath.")
        parser_xpath.set_defaults(func=lambda a : self.cmd_xpath(a))

        parser_state = subparsers.add_parser('state', help='List states.')
        parser_state.add_argument("state_xpath", type=str,
                                  default="//*[@ressource='state']", nargs="?",
                                  help="A xpath that matches states. Default is '%(default)s' which matches all states.")
        parser_state.add_argument('--long-description','-l',action='store_true',help="Show long description.")
        parser_state.add_argument('--path','-p',action='store_true',help="Show state path to go to these states.")
        parser_state.add_argument('--requires-list','-r',action='store_true',help="List Requires to go to these states.")

        parser_state.set_defaults(func=lambda a : self.cmd_state(a))

        parser_state_current = subparsers.add_parser('state-current', help='Show current state of a module.')
        parser_state_current.add_argument('state_xpath' , type=str, help='a xpath that matches states')
        parser_state_current.set_defaults(func=lambda a : self.cmd_state_current(a))

        parser_state_goto = subparsers.add_parser('state-goto', help='go to a state of a module')
        parser_state_goto.add_argument('state_xpath_uri' , type=str, help='a XPath URI corresponding to a State')
        group = parser_state_goto.add_mutually_exclusive_group()
        group.add_argument('-R',dest="require" , type=str,  nargs="*", action='append', help=help_require)
        group.add_argument('-J',dest="json_require" , type=str, help="Use raw JSON require format (useful for debugging, see provide_call API for more informations)")
        parser_state_goto.set_defaults(func=lambda a : self.cmd_state_goto(a))


        parser_provide = subparsers.add_parser('provide', help='List provides.')
        parser_provide.add_argument('provide_xpath' , type=str, help='a xpath that matches Provide resources')
        parser_provide.add_argument('--long-description','-l',action='store_true',help="Show long description")
        parser_provide.add_argument('--path','-p',action='store_true',help="Show the path of state to call the provides")
        parser_provide.add_argument('--all','-a',action='store_true',help="Show all provides required to call the provide")

        parser_provide.set_defaults(func=lambda a : self.cmd_provide(a))

        parser_provide_call = subparsers.add_parser('provide-call', help='Call a provide.')
        parser_provide_call.add_argument('xpath' , type=str, help='a xpath')
        parser_provide_call.add_argument('--check','-c',action='store_true',help="check if requires are valid. This calls provide_call_validation API method.")
        group = parser_provide_call.add_mutually_exclusive_group()
        group.add_argument('-R',dest="require" , type=str,  nargs="*", action='append', help=help_require)
        group.add_argument('-J',dest="json_require" , type=str, help="Use raw JSON require format (useful for debugging, see provide_call API for more informations)")
        parser_provide_call.set_defaults(func=lambda a : self.cmd_provide_call(a))

        parser_plot = subparsers.add_parser('plot', help='Plot a lifecycle')
        parser_plot.add_argument('module' , type=str, nargs='?', help='a module')
        parser_plot.add_argument('--reachable','-r',action='store_true',help="Only reachable states from current state")
        parser_plot.add_argument('-T', choices=['dot','json','json-human','automaton','xml'],help="print path to call this provide. For xml format, you can pipe armonic stdout to xmllint --format - to have a indented output ('client.py plot -T xml | xmllint --format -').")
        parser_plot.set_defaults(func=lambda a : self.cmd_plot(a))

    def func(self, client):
        self.client = client
        args = self.parser.parse_args()
        args.func(args)
