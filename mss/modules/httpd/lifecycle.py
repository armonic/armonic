from mss.lifecycle import State, Transition, Lifecycle, provide
from mss.require import Require
from mss.variable import VString, Port
import mss.state
import configuration

import mss.common
import logging
logger=logging.getLogger(__name__)

class NotInstalled(State):pass
class Configured(State):
    """Configure listen and vhost port"""
    requires=[Require([Port("port",default=8080)],name='port'),
              Require([VString("root",default="/")],name="augeas")]
    def entry(self):
        """Set listen and vhost port"""
        logger.info("%s.%-10s: set listen and vhost port in  httpd.conf with requires %s"%(self.lf_name,self.name,self.requires))
        self.conf=configuration.Apache(autoload=True,augeas_root=self.requires.get('augeas').variables.root.value)
        self.conf.setPort(str(self.requires.get('port').variables.port.value))
    def leave(self):
        """ set wordpress.php """
        logger.info("do nothing...")

    @mss.lifecycle.provide()
    def get_documentRoot(self):
        """Get document root path of default vhost."""
        return self.conf.documentRoot.value

    @mss.lifecycle.provide(flags={'restart':True})
    def set_port(self,port):
        """Set listen and vhost port"""
        self.conf.setPort(port)

class Active(mss.state.ActiveWithSystemd):
    services=["httpd"]

    @provide()
    def start(self):
        logger.info("Apache activation...")

class Installed(mss.state.InstallPackagesUrpm):
    packages=["apache"]

class Httpd(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,Active()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
