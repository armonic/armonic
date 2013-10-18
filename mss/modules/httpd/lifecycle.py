from mss.lifecycle import State, Transition, Lifecycle
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

    @Require.add([Port("port", default=8080)], name='port')
    @Require.add([VString("root",default="/")], name="augeas")
    def entry(self):
        """Set listen and vhost port"""
        logger.info("%s.%-10s: set listen and vhost port in  httpd.conf with requires %s"%(self.lf_name,self.name,self.requires))
        port = self.requires_entry.get('port').variables.port.value
        augeas = self.requires_entry.get('augeas').variables.root.value

        self.conf=configuration.Apache(autoload=True,augeas_root=augeas)
        self.conf.setPort(str(port))
        logger.event({"lifecycle":self.lf_name,"event":"listening","port":port})
    def leave(self):
        """ set wordpress.php """
        logger.info("do nothing...")

    @Require.add([VString("httpdDocumentRoot", default='/var/www/wordpress')])
    def get_documentRoot(self, requires):
        """Get document root path of default vhost."""
        return self.conf.documentRoot.value

    @Require.add([Port("port")])
    #flags={'restart':True})
    def set_port(self, requires):
        """Set listen and vhost port"""
        self.conf.setPort(requires.this.port.value)

class Active(mss.state.ActiveWithSystemd):
    services=["httpd"]

    # @provide()
    # def start(self):
    #     logger.info("Apache activation...")

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
