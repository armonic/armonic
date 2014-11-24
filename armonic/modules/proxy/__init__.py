from armonic import Lifecycle, State, Transition, Provide
from armonic.states import InitialState
from armonic.require import RequireExternal
from armonic.variable import Url


import logging
logger = logging.getLogger(__name__)


class NotInstalled(InitialState):
    pass


class Configured(State):

    @RequireExternal("websites", "//WebSite//start",
                     provide_ret=[Url("url")],
                     nargs="*")
    def enter(self, requires):
        logger.info(requires.websites.variables())


class Active(State):

    def enter(self):
        logger.info("Activation of proxy service...")

    @Provide(label="Fake proxy creation",
             tags=['demo'])
    def start(self):
        logger.info('up')


class Proxy(Lifecycle):
    """This is a simulation of a proxy service. This must be just use
    to try Armonic."""
    initial_state = NotInstalled()
    transitions = [
        Transition(NotInstalled(), Configured()),
        Transition(Configured(), Active())
    ]
