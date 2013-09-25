import os
import sys
import logging
import logging.handlers
import json
import traceback

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

format = '%(asctime)s|%(levelname)7s - %(message)s'
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter(format))

format = '%(asctime)s|%(name)20s|%(levelname)6s: %(message)s'
fh = logging.handlers.RotatingFileHandler("/tmp/mss.log", maxBytes=10485760, backupCount=5)
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter(format))

logger.addHandler(ch)
logger.addHandler(fh)


def log_disable_stdout():
    logger.removeHandler(ch)


EVENT_LEVELV_NUM = 25
logging.addLevelName(EVENT_LEVELV_NUM, "EVENT")
def event(self, dct, *args, **kws):
    # Yes, logger takes its '*args' as 'args'.
    jdct = json.dumps(dct)
    self._log(EVENT_LEVELV_NUM, jdct, args, **kws)
logging.Logger.event = event


PROCESS_LEVELV_NUM = 24
logging.addLevelName(PROCESS_LEVELV_NUM, "PROCESS")
def process(self, dct, *args, **kws):
    if not hasattr(self,"_processline"):
        self._processline = ""
    t = dct.split("\n")
    if len(t) == 1:
        self._processline+=t[0]
    elif len(t) > 1:
        self._log(PROCESS_LEVELV_NUM, self._processline + t[0], args, **kws)
        for i in t[1:-1]:
            self._log(PROCESS_LEVELV_NUM, i, args, **kws)
        if t[-1] != '':
            self._processline = t[-1]
        else :
            self._processline = ""
logging.Logger.process = process


def expose(f):
    "Decorator to set exposed flag on a function."
    f.exposed = True
    return f


def is_exposed(f):
    "Test whether another function should be publicly exposed."
    return getattr(f, 'exposed', False)


def load_lifecycles(dir):
    """Import Lifecycle modules from dir"""
    if os.path.exists(os.path.join(dir, '__init__.py')):
        sys.path.insert(0, dir)
        for module in os.listdir(dir):
            if os.path.exists(os.path.join(dir, module, '__init__.py')):
                try:
                    __import__(module)
                    logger.info("Imported module %s" % module)
                except ImportError as e:
                    logger.info("Module %s can not be imported" % module)
                    logger.debug("Exception on import module %s:" % module)
                    tb=traceback.format_exc().split("\n")
                    for l in tb:
                        logger.debug("  %s"%l)


class DoesNotExist(Exception):
    pass


class ValidationError(Exception):
    pass


class IterContainer(object):
    """
    Simple object container

    Is an iterator to loop over objects:
        objects = IterContainer(objects)
        for object in objects:
            print object.name, object.value

    And provide easy object retrieve:
        objects = IterContainer(objects)
        object = objects.object_name
        print object.name, object.value

    Objects MUST have a name attribute
    """
    _objects = []

    def __new__(cls, objects):
        instance = super(IterContainer, cls).__new__(cls, objects)
        for object in objects:
            instance.__setattr__(object.name, object)
        return instance

    def __init__(self, objects):
        self._objects = objects

    def append(self, object):
        self._objects.append(object)

    def get(self, attr, *args, **kwargs):
        if hasattr(self, attr):
            return getattr(self, attr)
        raise DoesNotExist("%s does not exist" % attr)

    def __iter__(self):
        return iter(self._objects)

    def __repr__(self):
        return "IterContainer(%s)" % self._objects
