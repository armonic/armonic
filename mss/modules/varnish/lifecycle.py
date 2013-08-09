from mss.lifecycle import State, Transition, Lifecycle
from mss.require import Require, RequireExternal, VPort
import mss.state

import mss.common
import logging
logger=logging.getLogger(__name__)

class NotInstalled(State):pass
class Configured(mss.state.RunScript):
    requires=[
        RequireExternal("Wordpress","get_site",[]),
        Require([VPort("port")])
        ]
    script_name="setup.sh"

    def require_to_script_args(self, requires):
        print requires
        hosts=[r['host'] for r in requires['Wordpress.get_site']]
        return ["%s" % ",".join(hosts),"%s" % requires['port'][0]['port']]

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
