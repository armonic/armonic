from mss.lifecycle import State, Transition, Lifecycle
from mss.require import Require, RequireExternal
from mss.variables import VPort, VHosts, VDict
import mss.state

import mss.common
import logging
logger=logging.getLogger(__name__)

class NotInstalled(State):pass
class Configured(mss.state.RunScript):
    requires=[
        RequireExternal([VDict("hosts")], "Wordpress", "get_site"),
        Require([VPort("port")])
        ]
    script_name="setup.sh"

    def require_to_script_args(self):
        return [",".join(self.requires.get('Wordpress.get_site').variables.hosts), str(self.requires.this.variables.port.value)]


class Active(mss.state.ActiveWithSystemd):
    services=["varnish"]

class Installed(mss.state.InstallPackages):
    packages=["varnish"]

class Varnish(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,Active()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
