from armonic import Lifecycle, State, Transition, Provide
from armonic.states import InitialState
from armonic.require import RequireLocal
from armonic.variable import VString, Url


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

    @Provide(label="Fake website creation",
             tags=['demo'])
    @RequireLocal("webserver", "//WebServer//start",
                  provide_ret=[Url("url")])
    def start(self, requires):
        logger.info("Start website")
        url = requires.webserver.variables().url.value
        return {"url": url}


class WebSite(Lifecycle):
    """This is a simulation of a webserver services. This must be just use
    to try Armonic."""
    initial_state = NotInstalled()
    transitions = [
        Transition(NotInstalled(), Templated()),
        Transition(Templated(), Active())
    ]
