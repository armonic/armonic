from armonic import Lifecycle, State, Transition
from armonic.states import InitialState
from armonic.require import RequireLocal
from armonic.variable import VString


import logging
logger = logging.getLogger(__name__)


class NotInstalled(InitialState):
    pass


class Templated(State):

    @RequireLocal(name="document_root",
                  xpath="//WebServer/Configured/create_document_root",
                  provide_args=[VString("path", default="/var/www/website/")])
    def enter(self, requires):
        logger.info("Appling template...")


class Active(State):

    def enter(self):
        logger.info("Activation of webserver service...")

    @RequireLocal("webserver", "//WebServer//start")
    def start(self, requires):
        logger.info("Start website")
        pass


class WebSite(Lifecycle):
    """This is a simulation of a webserver services. This must be just use
    to try Armonic."""
    initial_state = NotInstalled()
    transitions = [
        Transition(NotInstalled(), Templated()),
        Transition(Templated(), Active())
    ]
