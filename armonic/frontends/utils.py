import re
import json
import logging
import getpass
import argparse

from sleekxmpp.jid import JID, InvalidJID

import armonic.common
from armonic.utils import OsTypeMBS, OsTypeDebianWheezy, OsTypeAll


def jidType(string):
    try:
        jid = JID(string)
    except InvalidJID:
        raise argparse.ArgumentTypeError('Incorrect JID')
    return str(jid)


def read_variable(string):
    return json.loads(string)


def show_variable(variable):
    var = json.dumps(variable)
    if var == "null":
        return ""
    return var


def read_string(string):
    """Try to transform string argument value to armonic primitive type"""
    if string.startswith('[') and string.endswith(']'):
        return [l.lstrip() for l in string[1:-1].split(",")]
    try:
        return int(string)
    except ValueError:
        return string


# Taken from http://stackoverflow.com/questions/384076/how-can-i-make-the-python-logging-output-to-be-colored/384125#384125
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(30, 38)
# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[;%dm"
BOLD_SEQ = "\033[1;%dm"
COLORS = {
    'INFO': WHITE,
    'DEBUG': BLUE,
    'EVENT': GREEN,
    'WARNING': YELLOW,
    'CRITICAL': MAGENTA,
    'ERROR': RED,
    'PROCESS': CYAN
}


class ColoredFormatter(logging.Formatter):

    def __init__(self, *args, **kwargs):
        logging.Formatter.__init__(self, *args, **kwargs)

    def format(self, record):
        levelname = record.levelname
        if record.levelname in COLORS:
            record._levelname = record.levelname
            levelname_color = BOLD_SEQ % (COLORS[levelname]) + levelname + RESET_SEQ
            record.levelname = levelname_color
        record.module = COLOR_SEQ % WHITE + "[" + record.module + "]" + RESET_SEQ
        if getattr(record, 'ip', None):
            record._ip = record.ip
            record.ip = COLOR_SEQ % WHITE + "[" + record.ip + "]" + RESET_SEQ
        return logging.Formatter.format(self, record)


class Filter(object):
    """Permit to filter log based on a list of pattern applied on
    record.module."""
    def __init__(self, patterns):
        self.patterns = patterns

    def filter(self, record):
        return record.module in self.patterns


class CliArg(object):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def add_to_parser(self, parser):
        parser.add_argument(*self.args, **self.kwargs)


class Cli(object):

    def __init__(self, parser, disable_options=[]):
        self.disabled_options = disable_options
        self.parser = parser
        self.__add_arguments()

    def __add_arguments(self):
        for cli_arg in self.ARGUMENTS:
            if cli_arg.args[0] not in self.disabled_options:
                cli_arg.add_to_parser(self.parser)

    def has_arg(self, name):
        return name not in self.disabled_options

    def parse_args(self):
        return self.parser.parse_args()


class CliBase(Cli):
    """Contains arguments that are common for all frontends.

    To use it, you have to instanciate it with a arparse.parser, and
    call parse_args.

    """

    VERBOSE_LEVELS = [(logging.INFO, "INFO"),
                      (logging.DEBUG, "DEBUG"),
                      (armonic.common.TRACE_LEVEL, armonic.common.TRACE_LEVEL_NAME)]
    VERBOSE_DEFAULT_LEVEL = logging.ERROR

    ARGUMENTS = [
        CliArg('--verbose', "-v",
               action="count",
               help='Can be specified many times (%s)' % [v[1] for v in VERBOSE_LEVELS]),
        CliArg('--version', "-V",
               action='version', version='%(prog)s ' + "0.1"),
        CliArg('--config', "-c",
               is_config_file=True, help='Path to config file'),
        CliArg('--log-filter',
               default=None,
               action='append',
               help='To filter logs on the module name. Filters are applied on stdout handler. This option can be specified several times.')
    ]

    def __init__(self, *args, **kwargs):
        Cli.__init__(self, *args, **kwargs)
        self.logging_level = CliBase.VERBOSE_DEFAULT_LEVEL

    def parse_args(self):
        args = Cli.parse_args(self)

        if self.has_arg('--verbose') and args.verbose is not None:
            self.logging_level = CliBase.VERBOSE_LEVELS[args.verbose - 1][0]
            print "Verbosity is set to %s" % CliBase.VERBOSE_LEVELS[args.verbose - 1][1]
        else:
            self.logging_level = CliBase.VERBOSE_DEFAULT_LEVEL

        logger = logging.getLogger()
        logger.setLevel(self.logging_level)

        format = '%(levelname)-19s %(module)s %(message)s'
        ch = logging.StreamHandler()
        ch.setLevel(self.logging_level)
        ch.setFormatter(ColoredFormatter(format))

        if self.has_arg('--log-filter') and args.log_filter:
            ch.addFilter(Filter(args.log_filter))

        logger.addHandler(ch)

        return args


class CliClient(Cli):
    ARGUMENTS = [
        CliArg('--dont-call', action='store_true',
               default=False,
               help="Don't execute provide calls.\
               States are not applied.",
               env_var='ARMONIC_DONT_CALL'),
        CliArg('--manage', action='store_true', default=False,
               help="Manage all provides without confirmation",
               env_var='ARMONIC_MANAGE')
    ]


class CliLocal(Cli):
    ARGUMENTS = [
        CliArg('--os-type', choices=['mbs', 'debian', 'arch', 'any'],
               default=None, help="Manually specify an OsType.",
               env_var='ARMONIC_OS_TYPE'),
        CliArg('--lifecycle-dir', type=str, action='append',
               help="Load a lifecycle directory."),
        CliArg('--lifecycle-repository', type=str, action='append',
               help="Load a lifecycle repository (composed by several lifecycles)."),
        CliArg('--no-default', action='store_true',
               default=False, help="Don't load default lifecycles."),
        CliArg('--simulation', action='store_true',
               default=False,
               help="Simulate provide calls. States are applied.",
               env_var='ARMONIC_SIMULATION'),
        CliArg('--halt-on-error', action="store_true",
               default=False,
               help='Halt if a module import occurs (default: %(default)s))'),
    ]

    def parse_args(self):
        args = Cli.parse_args(self)

        if self.has_arg('--simulation'):
            armonic.common.SIMULATION = args.simulation

        if self.has_arg('--os-type'):
            os_type = None
            if args.os_type == "mbs":
                os_type = OsTypeMBS()
            elif args.os_type == "debian":
                os_type = OsTypeDebianWheezy()
            elif args.os_type == "any":
                os_type = OsTypeAll()
            self.os_type = os_type

        if self.has_arg('--no-default') and not args.no_default:
            armonic.common.load_default_lifecycles(
                raise_import_error=args.halt_on_error)

        if self.has_arg('--lifecycle-dir') and args.lifecycle_dir is not None:
            for l in args.lifecycle_dir:
                armonic.common.load_lifecycle(
                    l,
                    raise_import_error=args.halt_on_error)

        if self.has_arg('--lifecycle-repository') and args.lifecycle_repository is not None:
            for l in args.lifecycle_repository:
                armonic.common.load_lifecycle_repository(
                    l,
                    raise_import_error=args.halt_on_error)

        return args


class CliXMPP(Cli):
    ARGUMENTS = [
        CliArg('--host', '-H', type=str,
               help="XMPP server IP (if DNS is not set correctly)",
               env_var='ARMONIC_XMPP_HOST'),
        CliArg('--port', '-P',
               type=int,
               default=5222,
               help="XMPP server port (default '%(default)s')",
               env_var='ARMONIC_XMPP_PORT'),
        CliArg('--jid', '-j',
               required=True,
               type=jidType,
               help="The client JID",
               env_var='ARMONIC_XMPP_JID'),
        CliArg('--password', '-p', type=str,
               help="The client password",
               env_var='ARMONIC_XMPP_PASSWD'),
        CliArg('--muc-domain',
               type=str,
               help="XMPP MUC domain (default is %s.<JID_DOMAIN>)" % armonic.common.MUC_SUBDOMAIN,
               env_var='ARMONIC_XMPP_MUC_DOMAIN'),
        CliArg('--verbose-xmpp', action='store_true',
               default=False,
               help="Enable sleekxmpp logging")
    ]

    def __init__(self, parser, disable_options=[], confirm_password=False):
        """
        :param confirm_password: Set to true if the password has to be set twice
        """
        Cli.__init__(self, parser, disable_options)
        self.confirm_password = confirm_password
        self.password = None

    def parse_args(self):
        """A helper to parse arguments. This add several common options such
        as verbosity. It returns the same object than parseargs.parse_args."""
        args = Cli.parse_args(self)

        # We just enable sleekxmmp logs if DEBUG mode is set
        if self.has_arg('--verbose-xmpp') and args.verbose_xmpp:
            logging.getLogger("sleekxmpp").setLevel(logging.DEBUG)
        else:
            logging.getLogger("sleekxmpp").setLevel(logging.WARNING)

        if not self.has_arg('--password'):
            raise Exception('--password is mandatory.')

        if self.has_arg('--muc-domain'):
            self.muc_domain = args.muc_domain
            if self.muc_domain is None:
                self.muc_domain = armonic.common.MUC_SUBDOMAIN + '.' + JID(args.jid).domain

        if not args.password:
            self.password = read_passwd(check=self.confirm_password)
        else:
            self.password = args.password

        return args


def read_passwd(check=False):
    """ read password from console """
    match = False
    prompt = "Password"
    pwd = ""
    while not match:
        pwd = getpass.getpass(prompt + ': ')
        if check:
            pwd2 = getpass.getpass(prompt + ' (confirm): ')
            match = (pwd == pwd2)
            if not match:
                print "Passwords don't match. Retry..."
        else:
            match = True
    return pwd
