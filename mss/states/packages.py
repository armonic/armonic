import logging

from mss.lifecycle import State
from mss import process
import mss.utils


logger = logging.getLogger(__name__)


class PackageInstallationError(Exception):
    pass


class UrpmiError(PackageInstallationError):
    pass


class AptGetInstallError(PackageInstallationError):
    pass


class InstallPackagesUrpm(State):
    packages = []
    supported_os_type = [mss.utils.OsTypeMBS()]

    def _xml_add_properties_tuple(self):
        return ([("repository", "mbs")] +
                [('package', p) for p in self.packages] +
                mss.lifecycle.State._xml_add_properties_tuple(self))

    def enter(self):
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


class InstallPackagesApt(State):
    packages = []
    supported_os_type = [mss.utils.OsTypeDebian(), mss.utils.OsTypeUbuntu()]

    def enter(self, requires={}):
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
