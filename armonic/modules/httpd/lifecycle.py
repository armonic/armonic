from armonic.lifecycle import State, Transition, Lifecycle
from armonic.require import Require
from armonic.provide import Provide
from armonic.variable import VString, Port
from armonic.states import InstallPackagesUrpm, ActiveWithSystemd
import configuration

import logging


logger = logging.getLogger(__name__)


class NotInstalled(State):
    pass


class Configured(State):
    """Configure listen and vhost port"""

    @Require('conf', [Port("port", default=8080, label="Listen port", expert=True)])
    @Require('augeas', [VString("root", default="/", label="Augeas root path", expert=True)])
    def enter(self, requires):
        """Set listen and vhost port"""
        port = requires.conf.variables().port.value
        logger.info("Set httpd listening port to %s" % port)
        augeas = requires.augeas.variables().root.value

        self.conf = configuration.Apache(autoload=True, augeas_root=augeas)
        self.conf.setPort(str(port))
        logger.event({"lifecycle": self.lf_name,
                      "event": "listening",
                      "port": port})

    def leave(self):
        """ set wordpress.php """
        logger.info("do nothing...")

    @Provide(label="Get Apache2 document root",
             tags=['internal'])
    @Require('http_document',
             [VString("root",
              default='/var/www/',
              label="Document root path")])
    def get_document_root(self, requires):
        """Get document root path of default vhost."""
        return self.conf.documentRoot.value

    @Provide(label='Set Apache2 listen port',
             tags=['expert', 'webserver', 'apache'])
    @Require('conf', [Port("port", expert=True)])
    # flags={'restart':True})
    def set_port(self, requires):
        """Set listen and vhost port"""
        self.conf.setPort(requires.conf.variables().port.value)

    @Provide(tags=['internal'])
    def get_port(self):
        """Set listen and vhost port"""
        return {"port": self.conf.port.value}


class Active(ActiveWithSystemd):
    services = ["httpd"]

    @Provide(label="Start Apache2 service")
    def start(self):
        ActiveWithSystemd.start(self)


class Installed(InstallPackagesUrpm):
    packages = ["apache"]


class Httpd(Lifecycle):
    transitions = [
        Transition(NotInstalled(), Installed()),
        Transition(Installed(), Configured()),
        Transition(Configured(), Active()),
    ]

    def __init__(self):
        self.init(NotInstalled(), {})
