from mss.lifecycle import State, Transition, Lifecycle, provide
from mss.require import Require, VString, VPort
import mss.state
import configuration

import mss.common
import logging
logger=logging.getLogger(__name__)

class NotInstalled(State):pass
class Configured(State):
    """Configure listen and vhost port"""
    requires=[Require([VPort("port",default="8080")]),
              Require([VString("augeas_root",default="/")],name="augeas")]
    def entry(self,requires):
        """Set listen and vhost port"""
        logger.info("%s.%-10s: set listen and vhost port in  httpd.conf with requires %s"%(self.module(),self.name,requires))
        self.conf=configuration.Apache(autoload=True,augeas_root=requires['augeas'][0]['augeas_root'])
        self.conf.setPort(requires['port'][0]['port'])
    def leave(self):
        """ set wordpress.php """
        logger.info("do nothing...")

    @mss.lifecycle.provide()
    def get_documentRoot(self):
        """Get document root path of default vhost."""
        return self.conf.documentRoot.value

    @mss.lifecycle.provide({'restart':True})
    def set_port(self,port):
        """Set listen and vhost port"""
        self.conf.setPort(port)

class Active(mss.state.ActiveWithSystemd):
    services=["httpd"]

    @provide()
    def start(self):
        logger.info("Apache activation...")

class Installed(mss.state.InstallPackages):
    packages=["apache"]

class Httpd(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,Active()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
