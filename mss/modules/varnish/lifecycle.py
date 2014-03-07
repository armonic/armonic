import logging

from mss.lifecycle import State, Transition, Lifecycle
from mss.require import Require, RequireExternal
from mss.variable import Port
from mss.states import ActiveWithSystemd, InstallPackagesUrpm, RunScript


logger = logging.getLogger(__name__)


class NotInstalled(State):
    pass


class Configured(RunScript):
    script_name = "setup.sh"

    def require_to_script_args(self):
        hosts = [v.host.value for v in
                 self.provide_enter.backend.variables(all=True)]
        return [",".join(hosts),
                str(self.provide_enter.conf.variables().port.value)]

    @Require('conf', [Port("port", default=80)])
    @RequireExternal('backend', "//get_website", nargs='*')
    def enter(self, requires):
        RunScript.enter(self)
        for v in requires.backend.variables(all=True):
            logger.event({"lifecycle": self.lf_name,
                          "event": "binding",
                          "target": v.host.value})
        logger.event({"lifecycle": self.lf_name,
                      "event": "listening",
                      "port": requires.conf.variables().port.value})


class Active(ActiveWithSystemd):
    services = ["varnish"]


class Installed(InstallPackagesUrpm):
    packages = ["varnish"]


class Varnish(Lifecycle):
    initial_state = NotInstalled()
    transitions = [
        Transition(NotInstalled(), Installed()),
        Transition(Installed(), Configured()),
        Transition(Configured(), Active()),
    ]
