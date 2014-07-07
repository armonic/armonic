import json
import logging


def read_variable(string):
    return json.loads(string)


def show_variable(variable):
    return json.dumps(variable)


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


class Cli(object):
    """This class encapslutates common stuff for CLI Armonic clients."""
    VERBOSE_LEVELS = [(logging.INFO, "INFO"), (logging.DEBUG, "DEBUG")]
    VERBOSE_DEFAULT_LEVEL = logging.CRITICAL

    def __init__(self):
        self.logging_level = Cli.VERBOSE_DEFAULT_LEVEL

    def add_argument_verbose(self, parser):
        """A helper to add a verbose argument"""
        parser.add_argument('--verbose', "-v",
                            action="count",
                            help='Can be specified many times (%s)' % [v[1] for v in Cli.VERBOSE_LEVELS])

    def parse_args(self, parser):
        """A helper to parse arguments. This add several common options such
        as verbosity. It returns the same object than parseargs.parse_args."""

        self.add_argument_verbose(parser)
        args = parser.parse_args()

        if args.verbose is not None:
            self.logging_level = Cli.VERBOSE_LEVELS[args.verbose -1][0]
            print "Verbosity is set to %s" % Cli.VERBOSE_LEVELS[args.verbose -1][1]

        logging.basicConfig(level=self.logging_level,
                            format = '%(levelname)7s - %(message)s')

        return args
