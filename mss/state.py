"""This module defines some base state classes. They can be used to
build a application lifecycle."""

import logging
import process
import inspect
import os.path

from shutil import copyfile

import mss.lifecycle
import mss.common

# class ConfiguredAugeas(mss.lifecycle.State,mss.configuration_augeas.Configuration):

logger = logging.getLogger(__name__)

class CopyTemplate(mss.lifecycle.State):
    """Copy a file from src to dst"""
    src=""
    dst=""
    def entry(self,requires={}):
        logger.event("%s.%s copy template file from '%s' to '%s' ...", self.module(), self.name, self.src, self.dst)
        copyfile(self.src,self.dst)

class RunScript(mss.lifecycle.State):
    """This state permit to run a shell script. To convert require to
    shell script args, redefine :py:meth:`requireToScriptArgs`."""
    script_name = ""

    def require_to_script_args(self, requires):
        """Return []. Redefine it if your script needs arguments.
        This must return a list of arguements.
        """
        return []

    def entry(self, requires={}):
        script_path = os.path.join(os.path.dirname(inspect.getfile(self.__class__)), self.script_name)
        script_args = self.require_to_script_args(requires)
        logger.event("%s.%s run script %s %s ...", self.module(),
                     self.name, self.script_name, script_args)
        thread = process.ProcessThread("/bin/bash", None, "test",
                                       ["/bin/bash", script_path] + script_args,
                                       None, None, None, None)
        thread.start()
        thread.join()
        if thread.code == 0:
            logger.event("%s.%s run script %s done.", self.module(), self.name, script_path)
        else:
            logger.event("%s.%s run script %s failed.", self.module(), self.name, script_path)
            logger.debug("%s",thread.output)

class UrpmiError(Exception):
    pass
class InstallPackages(mss.lifecycle.State):
    packages = []

    def entry(self, requires={}):
        pkgs = " ".join(self.packages)
        logger.event("%s.%s urpmi %s ...", self.module(), self.name, pkgs)
        for p in self.packages:
            thread = process.ProcessThread("/bin/rpm", None, "test",
                                           ["/bin/rpm", "-q", "%s" % p],
                                           None, None, None, None)
            thread.start()
            thread.join()
            if thread.code == 0:
                logger.info("package %s is already installed" % p)
            else:
                logger.info("package %s is installing..." % p)
                thread = process.ProcessThread("/usr/sbin/urpmi", None, "test",
                                               ["/usr/sbin/urpmi","--auto", "--no-suggests","%s" % p],
                                               None, None, None, None)
                thread.start()
                thread.join()
                if thread.code == 0:
                    logger.event("%s.%s urpmi %s done." % (self.module(), self.name, pkgs))
                else:
                    logger.event("%s.%s urpmi %s failed." % (self.module(), self.name, pkgs))
                    raise UrpmiError()

    def leave(self):
        logger.info("%s.%-10s: urpme %s" % (self.module(), self.name, " ".join(self.packages)))


class ErrorSystemd(Exception):
    pass


class ActiveWithSystemd(mss.lifecycle.State):
    """If systemctl returns a code != 0, systemctl status 'service' is
    called and exception ErrorSystemd is raised"""
    services = []

    def __systemctl(self, action):
        for service in self.services:
            logger.event("%s.%s systemctl %s %s.service ..." % (self.module(), self.name, action, service))
            thread = process.ProcessThread("systemctl %s %s.service" % (action, service), None, "test",
                                           ["/bin/systemctl", action, "%s.service" % service],
                                           None, None, None, None)
            thread.start()
            thread.join()
            if thread.code == 0:
                logger.event("%s.%s systemctl %s %s.service done" % (self.module(), self.name, action, service))
            else:
                logger.event("%s.%s systemctl %s %s.service failed" % (self.module(), self.name, action, service))
                thread = process.ProcessThread("systemctl status %s.service" % service, None, "test",
                                               ["/bin/systemctl", "status", "%s.service" % service],
                                               None, None, None, None)
                thread.start()
                thread.join()
                raise ErrorSystemd()

    def entry(self, requires={}):
        self.__systemctl("start")

    def leave(self):
        self.__systemctl("stop")

    def cross(self, restart=False):
        if restart:
            self.__systemctl("reload")

    @mss.lifecycle.provide()
    def start(self):
        logger.info("%s.%-10s: call %s.start provide (going to state Active if not already reached)" %
                    (self.module(), self.name))


class ActiveWithSystemV(mss.lifecycle.State):
    services = []

    def entry(self, requires={}):
        for service in self.services:
            logger.event("%s.%s /etc/init.d/%s start ..." % (self.module(), self.name, service))
            thread = process.ProcessThread("/etc/init.d/%s" % service, None, "test",
                                           ["/etc/init.d/%s" % service, "start"],
                                           None, None, None, None)
            thread.start()
            thread.join()
            logger.event("%s.%s /etc/init.d/%s start done" % (self.module(), self.name, service))

    def leave(self):
        for service in self.services:
            logger.info("%s.%-10s: /etc/init.d/%s stop" % (self.module(), self.name, service))


    def cross(self, restart=False):
        if restart:
            for service in self.services:
                logger.info("%s.%-10s: /etc/init.d/%s reload" % (self.module(), self.name, service))


    @mss.lifecycle.provide()
    def start(self):
        logger.info("%s.%-10s: call %s.start provide (going to state Active if not already reached)" %
                    (self.module(), self.name))
