import logging

from armonic.lifecycle import State
from armonic.provide import Provide
from armonic.process import ProcessThread
import armonic.utils


logger = logging.getLogger(__name__)


class ErrorSystemd(Exception):
    pass


class ActiveWithSystemd(State):
    """Start services using ``systemd``.
    """
    services = []
    """List of services to be started when entering the state"""
    service_name = ""
    """Human name of the service to start"""
    supported_os_type = [armonic.utils.OsTypeMBS()]
    """Supported OS list for this state"""

    def __systemctl(self, action):
        for service in self.services:
            logger.info("systemctl %s %s.service ..." % (action, service))
            thread = ProcessThread("systemctl %s %s.service" % (action, service),
                                   None,
                                   "test",
                                   ["/bin/systemctl", action, "%s.service" % service])
            thread.start()
            thread.join()
            if thread.code == 0:
                logger.info("systemctl %s %s.service: done." %
                            (action, service))
            else:
                logger.info("systemctl %s %s.service: failed!" %
                            (action, service))
                thread = ProcessThread("systemctl status %s.service" % service,
                                       None,
                                       "test",
                                       ["/bin/systemctl", "status", "%s.service" % service])
                thread.start()
                thread.join()
                raise ErrorSystemd("See PROCESS log for information about systemd status %s" % service)

    def enter(self):
        logger.info("Starting services '%s' ..." % self.services)
        self.__systemctl("start")
        logger.event({"lifecycle": self.lf_name, "is_active": "true"})
        logger.info("Starting services '%s': done." % self.services)

    def leave(self):
        self.__systemctl("stop")

    def cross(self, restart=False):
        if restart:
            logger.info("Restarting services '%s' ..." % self.services)
            self.__systemctl("reload")
            logger.info("Restarting services '%s': done." % self.services)

    @Provide(label="Start {service_name} service")
    def start(self):
        logger.info("Start (via provide) services '%s': done." % self.services)


class ActiveWithSystemV(State):
    """Start services using the classic SystemV init system.
    """
    services = []
    """List of services to be started when entering the state"""
    service_name = ""
    """Human name of the service to start"""
    supported_os_type = [armonic.utils.OsTypeDebian()]
    """Supported OS list for this state"""

    def enter(self):
        for service in self.services:
            thread = ProcessThread("/etc/init.d/%s" % service,
                                   None,
                                   "test",
                                   ["/etc/init.d/%s" % service, "status"])
            thread.start()
            thread.join()
            if thread.code != 0:
                logger.info("%s.%s /etc/init.d/%s start..." %
                            (self.lf_name, self.name, service))
                thread = ProcessThread("/etc/init.d/%s" % service,
                                       None,
                                       "test",
                                       ["/etc/init.d/%s" % service, "start"])
                thread.start()
                thread.join()
            else:
                logger.info("%s.%s service %s is already started ..." %
                            (self.lf_name, self.name, service))
            logger.event("%s.%s /etc/init.d/%s start done" %
                         (self.lf_name, self.name, service))

    def leave(self):
        for service in self.services:
            logger.info("%s.%-10s: /etc/init.d/%s stop" %
                        (self.lf_name, self.name, service))

    def cross(self, restart=False):
        if restart:
            for service in self.services:
                logger.info("%s.%-10s: /etc/init.d/%s reload" %
                            (self.lf_name, self.name, service))

    @Provide(label="Start {service_name} service")
    def start(self):
        logger.info("%s.%-10s: call %s.start provide (going to state Active if not already reached)" %
                    (self.lf_name, self.name))
