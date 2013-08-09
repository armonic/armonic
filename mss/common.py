import logging
import logging.handlers
import json

logger=logging.getLogger()
logger.setLevel(logging.DEBUG)

format = '%(asctime)s|%(levelname)6s - %(message)s'
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
