from mss.lifecycle import State, Transition, Lifecycle, provide
from mss.require import Require, RequireExternal
from mss.variable import Port
import mss.state

import mss.common
import logging
logger=logging.getLogger(__name__)

class NotInstalled(State):pass
class Installed(mss.state.InstallPackagesUrpm):
    packages=["nfs-server"]
class Configured(State):
    pass

class Active(mss.state.ActiveWithSystemd):
    services=["nfs-server"]
    
    @provide()
    def get_dir(self, requires):
        return {"remotetarget" : "undefined/remote/target"}

class Nfs_server(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,Active()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
