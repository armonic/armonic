"""This module defines some base state classes. They can be used to
build a application lifecycle."""

import logging
import process
import inspect
import os.path

from shutil import copyfile

import mss.lifecycle
import mss.common
from mss.require import Require

# class ConfiguredAugeas(mss.lifecycle.State,mss.configuration_augeas.Configuration):

logger = logging.getLogger(__name__)


class CopyTemplate(mss.lifecycle.State):
    """Copy a file from src to dst"""
    src = ""
    dst = ""

    def entry(self):
        logger.info("Copying template file from '%s' to '%s' ...",
                    self.src,
                    self.dst)
        copyfile(self.src, self.dst)
        logger.info("Copying template file from '%s' to '%s': done.",
                    self.src,
                    self.dst)


class RunScript(mss.lifecycle.State):
    """This state permit to run a shell script. To convert require to
    shell script args, redefine :py:meth:`requireToScriptArgs`."""
    script_name = ""

    def require_to_script_args(self):
        """Return []. Redefine it if your script needs arguments.
        This must return a list of arguements.
        """
        return []

    def entry(self):
        script_path = os.path.join(os.path.dirname(inspect.getfile(
                                            self.__class__)), self.script_name)
        script_dir = os.path.dirname(script_path)
        script_args = self.require_to_script_args()
        logger.info("Running script '%s' with args '%s' ..." % (
            self.script_name,
            script_args))
        thread = process.ProcessThread("/bin/bash", None, "test",
                                       ["/bin/bash",
                                        script_path] + script_args,
                                       script_dir, None, None, None)
        thread.start()
        thread.join()
        if thread.code == 0:
            logger.info("Running script '%s': done." % script_path)
        else:
            logger.info("Running script '%s': failed!" % script_path)
            logger.debug("%s", thread.output)


class PackageInstallationError(Exception):
    pass


class UrpmiError(PackageInstallationError):
    pass


class InstallPackagesUrpm(mss.lifecycle.State):
    packages = []
    supported_os_type = [mss.utils.OsTypeMBS()]

    def _xml_add_property(self):
        return ([("repository", "mbs")] +
                [('package', p) for p in self.packages] +
                mss.lifecycle.State._xml_add_property(self))

    def entry(self):
        pkgs = " ".join(self.packages)
        logger.info("Installing packages '%s' ..." % (pkgs))
        for p in self.packages:
            thread = process.ProcessThread("/bin/rpm", None, "test",
                                           ["/bin/rpm",
                                            "-q",
                                            "%s" % p],
                                           None, None, None, None)
            thread.start()
            thread.join()
            if thread.code == 0:
                logger.info("Package '%s' is already installed" % p)
            else:
                logger.info("Package '%s' is installing..." % p)
                thread = process.ProcessThread("/usr/sbin/urpmi", None, "test",
                                               ["/usr/sbin/urpmi",
                                                "--auto",
                                                "--no-suggests",
                                                "%s" % p],
                                               None, None, None, None)
                thread.start()
                thread.join()
                if thread.code == 0:
                    logger.info("Installing of package '%s': done." % p)
                else:
                    logger.info("Installing of package '%s': failed!" % p)
                    raise UrpmiError()
        logger.info("Installing packages '%s': done." % (pkgs))

    def leave(self):
        logger.info("%s.%-10s: urpme %s" %
                    (self.lf_name, self.name, " ".join(self.packages)))


class AptGetInstallError(PackageInstallationError):
    pass


class InstallPackagesApt(mss.lifecycle.State):
    packages = []
    supported_os_type = [mss.utils.OsTypeDebian()]

    def _xml_add_property(self):
        return ([("repository", "debian")] +
                [('package', p) for p in self.packages] +
                mss.lifecycle.State._xml_add_property(self))

    def entry(self, requires={}):
        pkgs = " ".join(self.packages)
        logger.info("%s.%s apt-get install %s ...",
                    self.lf_name,
                    self.name,
                    pkgs)
        for p in self.packages:
            thread = process.ProcessThread("/usr/bin/dpkg", None, "test",
                                           ["/usr/bin/dpkg",
                                            "--status",
                                            "%s" % p],
                                           None, None, None, None)
            thread.start()
            thread.join()
            if thread.code == 0:
                logger.info("package %s is already installed" % p)
            else:
                logger.info("package %s is installing..." % p)
                thread = process.ProcessThread("/usr/bin/apt-get",
                                               None,
                                               "test",
                                               ["/usr/bin/apt-get",
                                                "install",
                                                "--assume-yes",
                                                "%s" % p],
                                               None, None, None,
                                               {"DEBIAN_FRONTEND": "noninteractive"})
                thread.start()
                thread.join()
                if thread.code == 0:
                    logger.info("%s.%s apt-get install %s done." %
                                (self.lf_name, self.name, p))
                else:
                    logger.info("%s.%s apt-get install %s failed." %
                                (self.lf_name, self.name, p))
                    raise AptGetInstallError()

    def leave(self):
        logger.info("%s.%-10s: urpme %s" %
                    (self.lf_name, self.name, " ".join(self.packages)))


class ErrorSystemd(Exception):
    pass


class ActiveWithSystemd(mss.lifecycle.State):
    """If systemctl returns a code != 0, systemctl status 'service' is
    called and exception ErrorSystemd is raised"""
    services = []
    supported_os_type = [mss.utils.OsTypeMBS()]

    def __systemctl(self, action):
        for service in self.services:
            logger.info("systemctl %s %s.service ..." % (action, service))
            thread = process.ProcessThread("systemctl %s %s.service" %
                                           (action, service),
                                           None,
                                           "test",
                                           ["/bin/systemctl",
                                            action,
                                            "%s.service" % service],
                                           None, None, None, None)
            thread.start()
            thread.join()
            if thread.code == 0:
                logger.info("systemctl %s %s.service: done." %
                            (action, service))
            else:
                logger.info("systemctl %s %s.service: failed!" %
                            (action, service))
                thread = process.ProcessThread("systemctl status %s.service" % service,
                                               None,
                                               "test",
                                               ["/bin/systemctl",
                                                "status",
                                                "%s.service" % service],
                                               None, None, None, None)
                thread.start()
                thread.join()
                raise ErrorSystemd("See PROCESS log for information about systemd status %s" % service)

    def entry(self):
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

    @mss.lifecycle.provide()
    def start(self, requires):
        logger.info("Start (via provide) services '%s': done." % self.services)


class ActiveWithSystemV(mss.lifecycle.State):
    """Lauch the service via SysV."""
    services = []
    supported_os_type = [mss.utils.OsTypeDebian()]

    def entry(self):
        for service in self.services:
            thread = process.ProcessThread("/etc/init.d/%s" % service, None,
                                           "test",
                                           ["/etc/init.d/%s" % service,
                                            "status"],
                                           None, None, None, None)
            thread.start()
            thread.join()
            if thread.code != 0:
                logger.info("%s.%s /etc/init.d/%s start ..." %
                            (self.lf_name, self.name, service))
                thread = process.ProcessThread("/etc/init.d/%s" % service,
                                               None,
                                               "test",
                                               ["/etc/init.d/%s" % service,
                                                "start"],
                                               None, None, None, None)
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

                # @mss.lifecycle.provide()
    def start(self):
        logger.info("%s.%-10s: call %s.start provide (going to state Active if not already reached)" %
                    (self.lf_name, self.name))


class InitialState(mss.lifecycle.State):
    supported_os_type = [mss.utils.OsTypeAll()]
