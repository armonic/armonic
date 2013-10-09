from mss.lifecycle import State, Transition, Lifecycle
from mss.require import Require, RequireExternal, Requires
from mss.variable import Port, Hostname, VList
import mss.state

import mss.common
import logging
logger=logging.getLogger(__name__)

class NotInstalled(State):pass
class Configured(mss.state.RunScript):
    requires_entry=Requires('entry',[
            RequireExternal("Wordpress", "get_site"),
            Require([Port("port",default=80, required=True)])
            ])
    script_name="setup.sh"

    def require_to_script_args(self):
        hosts=[v.host.value for v in self.requires_entry.get('Wordpress.get_site').variables]
        return [",".join(hosts), 
                str(self.requires_entry.this.variables.port.value)]

    def entry(self):
        super(mss.state.RunScript,self).entry()
        for v in self.requires_entry.get('Wordpress.get_site').variables:
            logger.event({"lifecycle":self.lf_name,"event":"binding","target":v.host.value})
        logger.event({"lifecycle":self.lf_name,"event":"listening","port":self.requires_entry.this.variables.port.value})
        

class Active(mss.state.ActiveWithSystemd):
    services=["varnish"]

class Installed(mss.state.InstallPackagesUrpm):
    packages=["varnish"]

class Varnish(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,Active()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
