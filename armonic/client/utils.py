import json
import logging
import armonic.common
from armonic.utils import OsTypeMBS, OsTypeDebianWheezy, OsTypeAll
import re


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


def require_validation_error(dct):
    """Take the return dict of provide_call_validate and return a list of
    tuple that contains (xpath, error_string)"""
    if dct['errors'] is False:
        return []
    errors = []
    provides = dct['requires']
    for p in provides:
        for r in p['requires']:
            for variables in r['variables']:
                for v in variables:
                    if v['error'] is not None:
                        errors.append((v['xpath'], v['error']))
    return errors


class Filter(object):
    """Permit to filter log based on a list of pattern applied on
    record.name."""
    def __init__(self, patterns):
        self.patterns = patterns

    def filter(self, record):
        for p in self.patterns:
            if re.match(p, record.name):
                return True
        return False


class Cli(object):
    """This class encapslutates common stuffs for Armonic frontends.

    :param remote: If the frontend can be used in remote mode, set to True.
    """
    VERBOSE_LEVELS = [(logging.INFO, "INFO"),
                      (logging.DEBUG+1, "EVENT"),
                      (logging.DEBUG, "DEBUG")]
    VERBOSE_DEFAULT_LEVEL = logging.CRITICAL

    def __init__(self, remote=False):
        self.logging_level = Cli.VERBOSE_DEFAULT_LEVEL
        self.os_type = None
        self.remote = remote
        
        # Will be set by args.no_remote
        self.no_remote = False

    def add_arguments(self, parser):
        """A helper to add a verbose argument"""
        parser.add_argument('--verbose', "-v",
                            action="count",
                            help='Can be specified many times (%s)' % [v[1] for v in Cli.VERBOSE_LEVELS])

        parser.add_argument('--version', "-V", action='version', version='%(prog)s ' + "0.1")

        if self.remote:
            parser.add_argument('--no-remote', action='store_true',
                                default=False, help="Directly use Armonic module.")
        parser.add_argument('--os-type', choices=['mbs', 'debian', 'arch', 'any'],
                            default=None, help="Manually specify an OsType. This is just used when no-remote is also set. If not set, the current OsType is used.")
        parser.add_argument('--lifecycle-dir', type=str, action='append',
                            help="A lifecycle directory. This is only useful on no-remote mode.")
        parser.add_argument('--no-default', action='store_true',
                            default=False, help="Don't load default lifecycles. This is only useful on no-remote mode.")
        parser.add_argument('--simulation', action='store_true',
                            default=False,
                            help="Simulate provide calls. States are applied. This is only useful on no-remote mode.")
        parser.add_argument('--dont-call', action='store_true',
                            default=False,
                            help="Don't execute provide calls. States are not applied. This is only useful on no-remote mode.")
        parser.add_argument('--halt-on-error', action="store_true",
                            default=False,
                            help='Halt if a module import occurs (default: %(default)s))')
        parser.add_argument('--log-filter',
                            default=None,
                            action='append',
                            help='To filter logs by specifing a regex which will be applied on the module name. Filters are applied on stdout handler. This option can be specified several times.')

    def parse_args(self, parser):
        """A helper to parse arguments. This add several common options such
        as verbosity. It returns the same object than parseargs.parse_args."""

        self.add_arguments(parser)
        args = parser.parse_args()
        if self.remote:
            self.no_remote = args.no_remote

        if args.verbose is not None:
            self.logging_level = Cli.VERBOSE_LEVELS[args.verbose - 1][0]
            print "Verbosity is set to %s" % Cli.VERBOSE_LEVELS[args.verbose - 1][1]

        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        format = '[%(levelname)s|%(name)s] %(message)s'
        ch = logging.StreamHandler()
        ch.setLevel(self.logging_level)
        ch.setFormatter(logging.Formatter(format))

        if args.log_filter:
            ch.addFilter(Filter(args.log_filter))

        logger.addHandler(ch)

        if self.remote is False or args.no_remote:
            os_type = None
            if args.os_type == "mbs":
                os_type = OsTypeMBS()
            elif args.os_type == "debian":
                os_type = OsTypeDebianWheezy()
            elif args.os_type == "any":
                os_type = OsTypeAll()
            self.os_type = os_type

            if not args.no_default:
                armonic.common.load_default_lifecycles(
                    raise_import_error=args.halt_on_error)

            if args.lifecycle_dir is not None:
                for l in args.lifecycle_dir:
                    armonic.common.load_lifecycle(
                        l,
                        raise_import_error=args.halt_on_error)

        return args
