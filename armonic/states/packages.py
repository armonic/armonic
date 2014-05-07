import logging

from armonic.lifecycle import State, MetaState
from armonic import process
import armonic.utils
from armonic.process import run

logger = logging.getLogger(__name__)


class PackageInstallationError(Exception):
    pass


class UrpmiError(PackageInstallationError):
    pass


class AptGetInstallError(PackageInstallationError):
    pass


class InstallPackagesUrpm(State):
    """Install packages on the system using ``urpmi``."""
    packages = []
    """List of packages to install"""
    supported_os_type = [armonic.utils.OsTypeMBS()]

    def _xml_add_properties_tuple(self):
        return ([("repository", "mbs")] +
                [('package', p) for p in self.packages] +
                armonic.lifecycle.State._xml_add_properties_tuple(self))

    def enter(self):
        pkgs = " ".join(self.packages)
        logger.info("Installing packages '%s' ..." % (pkgs))
        for p in self.packages:
            thread = process.ProcessThread("/bin/rpm", None, "test",
                                           ["/bin/rpm",
                                            "-q",
                                            "%s" % p],
                                           None, None, None, None)
            if thread.launch():
                logger.info("Package '%s' is already installed" % p)
            else:
                logger.info("Package '%s' is installing..." % p)
                thread = process.ProcessThread("/usr/sbin/urpmi", None, "test",
                                               ["/usr/sbin/urpmi",
                                                "--auto",
                                                "--no-suggests",
                                                "%s" % p],
                                               None, None, None, None)
                if thread.launch():
                    logger.info("Installing of package '%s': done." % p)
                else:
                    logger.info("Installing of package '%s': failed!" % p)
                    raise UrpmiError()
        logger.info("Installing packages '%s': done." % (pkgs))

    def leave(self):
        logger.info("%s.%-10s: urpme %s" %
                    (self.lf_name, self.name, " ".join(self.packages)))


class InstallPackagesApt(State):
    """Install packages on the system using ``apt``."""
    packages = []
    """List of packages to install"""
    supported_os_type = [armonic.utils.OsTypeDebian(),
                         armonic.utils.OsTypeUbuntu()]

    def _is_installed(self, package):
        return run("/usr/bin/dpkg", ["--status", "%s" % package])

    def enter(self):
        pkgs = " ".join(self.packages)
        logger.info("%s.%s apt-get install %s ...",
                    self.lf_name,
                    self.name,
                    pkgs)
        for p in self.packages:
            if self._is_installed(p):
                logger.info("package %s is already installed" % p)
            else:
                logger.info("package %s is installing..." % p)

                if run("/usr/bin/apt-get", ["install",
                                            "--assume-yes",
                                            "%s" % p],
                       env={"DEBIAN_FRONTEND": "noninteractive"}):
                    logger.info("%s.%s apt-get install %s done." %
                                (self.lf_name, self.name, p))
                else:
                    logger.info("%s.%s apt-get install %s failed." %
                                (self.lf_name, self.name, p))
                    raise AptGetInstallError()

    def leave(self):
        """Remove specified packages. Be careful, 'purge' option is applied."""
        if self.packages != []:
            logger.info("Uninstalling packages (via `apt-get remove`):")
            for p in self.packages:
                logger.info("\t%s" % p)

        for p in self.packages:
            if self._is_installed(p):
                logger.debug("Uninstalling package %s..." % p)
                if not run("/usr/bin/apt-get", ["remove",
                                                "--assume-yes",
                                                "--purge",
                                                "%s" % p],
                           env={"DEBIAN_FRONTEND": "noninteractive"}):
                    logger.debug("Some errors during "
                                 "uninstallation of package %s!" % p)
                    raise AptGetInstallError()
            else:
                logger.debug("Package %s is not installed!" % p)


class InstallPackages(MetaState):
    """Install packages using the available package management tool
    on the system.
    """
    implementations = [InstallPackagesUrpm, InstallPackagesApt]
