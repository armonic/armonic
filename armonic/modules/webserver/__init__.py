from armonic import Lifecycle, State, Transition, Provide, Require
from armonic.states import InitialState
from armonic.variable import VString, Port


import logging
logger = logging.getLogger(__name__)


class NotInstalled(InitialState):
    pass


class Installed(State):

    def enter(self):
        logger.info("Installation of webserver packages...")


class Configured(State):

    @Require("conf", variables=[Port("port", default=80)])
    def enter(self, requires):
        port = requires.conf.variables().port.value
        logger.info("Configuration of webserver service...")
        logger.info("Webserver listening on port %d" % port)

    @Provide(tags=['internal'])
    @Require("document_root", variables=[VString("path", default="/var/www/")])
    def create_document_root(self, requires):
        document_root = requires.document_root.variables().path.value
        logger.info("Creating document_root '%s'..." % document_root)


class Active(State):

    def enter(self):
        logger.info("Activation of webserver service...")

    @Provide(label='Fake webserver activation',
             tags=['demo'])
    def start(self):
        pass


class WebServer(Lifecycle):
    """This is a simulation of a webserver services. This must be just use
    to try Armonic."""
    initial_state = NotInstalled()
    transitions = [
        Transition(NotInstalled(), Installed()),
        Transition(Installed(), Configured()),
        Transition(Configured(), Active())
    ]
