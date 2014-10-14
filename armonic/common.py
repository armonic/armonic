import os
import sys
import logging
import logging.handlers
import traceback
import copy

from armonic.utils import get_first_ip

VERSION = "0.1"

SIMULATION = False
"""If set to True, provide call is not realized, just simulated. This
is used to design Provide/Require interactions.

"""

DONT_VALIDATE_ON_CALL = False
"""If set to True, provide validation is not realized before provide
calls. This is mainly use with SIMULATION flag, in order to simulate calls
that have provide ret which are not available (since provides return None).
"""

MUC_SUBDOMAIN = "logs"
"""Default subdomain for the MUC service
"""

CLI_CONF = [os.path.expanduser("~/.config/armonic/cli.conf"), "/etc/armonic/cli.conf"]
"""Default locations for Armonic clients (armocli, smartonic) configuration files
"""
AGENT_CONF = [os.path.expanduser("~/.config/armonic/agent.conf"), "/etc/armonic/agent.conf"]
"""Default locations for Armonic agent configuration files
"""
MASTER_CONF = [os.path.expanduser("~/.config/armonic/master.conf"), "/etc/armonic/master.conf"]
"""Default locations for Armonic master configuration files
"""

PUBLIC_IP = "localhost"
"""Public IP that should be used to contact deployed service. It has to be set by command line."""

# We set a null handler to avoid warning message if no handler is
# specified.
logging.getLogger("armonic").addHandler(logging.NullHandler())

# Custom logging levels
EVENT_LEVEL = 15
EVENT_LEVEL_NAME = "EVENT"
logging.addLevelName(EVENT_LEVEL, EVENT_LEVEL_NAME)


def event(self, kws):
    # This level is used in armonic to log an event.
    self._log(EVENT_LEVEL, kws, [], extra={"event_data": kws})
logging.Logger.event = event


PROCESS_LEVEL = 25
PROCESS_LEVEL_NAME = "PROCESS"
logging.addLevelName(PROCESS_LEVEL, PROCESS_LEVEL_NAME)


def process(self, dct, *args, **kws):
    """This level permits to log the output of processes. In fact, the
    message is transmitted only if it contains a '\n' otherwise, it is
    buffered until the next '\n'."""
    if not hasattr(self, "_processline"):
        self._processline = ""
    t = dct.split("\n")
    if len(t) == 1:
        self._processline += t[0]
    elif len(t) > 1:
        self._log(PROCESS_LEVEL, self._processline + t[0], args, **kws)
        for i in t[1:-1]:
            self._log(PROCESS_LEVEL, i, args, **kws)
        if t[-1] != '':
            self._processline = t[-1]
        else:
            self._processline = ""
logging.Logger.process = process

logger = logging.getLogger(__name__)

class NetworkFilter(logging.Filter):
    """Use this filter to add ip address of agent in log. Could be
    useful if we simultaneous use several agents.

    It adds %(ip) formatter.

    Add this filter to a handler via addFilter method."""
    def filter(self, record):
        record.ip = get_first_ip()
        return True


class XpathFilter(logging.Filter):
    """Use this filter to add xpath of object that emit the log.

    It adds %(xpath) formatter.

    Add this filter to a handler via addFilter method."""
    def filter(self, record):
        f = logging.currentframe()
        # On some versions of IronPython, currentframe() returns None if
        # IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename != record.pathname:
                f = f.f_back
                continue
            try:
                record.xpath = f.f_locals['self'].get_xpath_relative()
            except AttributeError:
                record.xpath = ""
            break
        return True


def expose(f):
    "Decorator to set exposed flag on a function."
    f.exposed = True
    return f


def is_exposed(f):
    "Test whether another function should be publicly exposed."
    return getattr(f, 'exposed', False)


def format_input_variables(requires=[]):
    """If the requires format is ([("//xpath/to/variable_name", "value")], X),
    translate to ([("//xpath/to/variable_name", {0:value})], X)
    """
    if not requires:
        return requires
    variables_values = requires[0]
    for index, (variable_xpath, variable_values) in enumerate(variables_values):
        if not type(variable_values) == dict:
            variables_values[index] = (variable_xpath, {0: variable_values})
    if len(requires) == 2:
        return [variables_values, requires[1]]
    elif len(requires) == 1:
        return [variables_values]


def load_lifecycle(lifecycle_path, raise_import_error=False):
    """Import a lifecycle. The lifecycle is a python module."""
    module_dir = os.path.abspath(
        os.path.join(os.path.abspath(lifecycle_path), os.pardir))
    if module_dir not in sys.path:
        logger.debug("Inserting module dir %s in 'sys.path'..." % module_dir)
        sys.path.insert(0, module_dir)
    lifecycle = os.path.relpath(lifecycle_path, module_dir)
    if os.path.exists(os.path.join(module_dir,
                                   lifecycle,
                                   '__init__.py')):

        logger.debug("Importing lifecycle %s..." % lifecycle)
        try:
            __import__(lifecycle)
            logger.info("Imported lifecycle %s" % lifecycle)
        except ImportError:
            logger.exception(
                "Exception on import lifecycle %s:" % lifecycle)
            if raise_import_error:
                raise


def load_default_lifecycles(raise_import_error=False):
    """Import default lifecycles"""
    lifecycle_dir = os.path.join(os.path.dirname(__file__), 'modules')
    logger.info("Loading default lifecycles (in %s):" % lifecycle_dir)
    load_lifecycle_repository(
        lifecycle_dir, raise_import_error=raise_import_error)


def load_lifecycle_repository(lifecycle_repository,
                              raise_import_error=False):
    """Import Lifecycle modules from lifecycle_repository which is a
    directory that contains several modules.

    :param raise_import_error: Raise import error if True

    """
    lifecycle_repository = os.path.abspath(lifecycle_repository)
    logger.info("Loading lifecycles in repository '%s'..." % lifecycle_repository)

    for lifecycle in os.listdir(lifecycle_repository):
        load_lifecycle(os.path.join(lifecycle_repository, lifecycle),
                       raise_import_error=raise_import_error)


class ValidationError(Exception):
    def __init__(self, msg, require_name=None, variable_name=None):
        Exception.__init__(self, msg)
        self.variable_name = variable_name
        self.require_name = require_name
        self.msg = msg

    def __setstate__(self, dict):
        self.variable_name = dict['variable_name']
        self.require_name = dict['require_name']
        self.msg = dict['msg']

    def __repr__(self):
        return "Error for variable %s in require %s:\n\t%s" % (
            self.variable_name, self.require_name, self.msg)

    def __str__(self):
        return self.__repr__()


class ProvideError(Exception):
    def __init__(self, provide, message, exc_info=None):
        self.provide = provide
        self.message = "Error in %s" % self.provide.get_xpath()
        if message:
            self.message += " : %s" % message
        if exc_info:
            exc_type, exc_value, exc_traceback = exc_info
            self.traceback = "".join(traceback.format_exception(exc_type, exc_value,
                                                                exc_traceback))
            self.message += "\n" + self.traceback

    def __str__(self):
        return self.message


class ExtraInfoMixin(object):
    extra = {}

    def __init__(self, **kwargs):
        self.extra = copy.copy(self.__class__.extra)
        self.extra.update(dict(**kwargs))

    def to_primitive(self):
        return {'extra': self.extra}
