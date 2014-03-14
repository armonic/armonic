import shutil
import os.path
import os
import logging
import time

from armonic.lifecycle import State, Transition, Lifecycle
from armonic.require import Require, RequireExternal
from armonic.variable import VString, Host
from armonic.states import InstallPackagesUrpm
from armonic.utils import ethernet_ifs
from armonic.process import ProcessThread


logger = logging.getLogger(__name__)


class NotInstalled(State):
    pass


class Installed(InstallPackagesUrpm):
    packages = ["nfs-utils-clients"]


class Active(State):
    services = ["nfs-utils-clients"]

    @RequireExternal(
        'nfs',
        "//Nfs_server/Active/get_dir",
        provide_args=[Host("client", default=ethernet_ifs()[0][1])],
        provide_ret=[VString("remotetarget")])
    @Require('mountpoint', [VString("path")])
#    @RequireExternal('nfs-start',
#                     '//Nfs_server/Active/start')
    def mount(self, requires):
        """Mount remotetarget on mountpoint. If it is already mounted,
        it does nothing."""
        mountpoint = requires.get("mountpoint").variables().path.value
        remotetarget = requires.get("nfs").variables().remotetarget.value

        for line in file("/proc/mounts"):
            device = line.split(" ")[0]
            dir = line.split(" ")[1]
            if dir == mountpoint:
                if device == remotetarget:
                    logger.info("Device %s is already mounted in %s" % (
                        remotetarget, mountpoint))
                    return
                else:
                    raise Exception("Directory %s is used by %s."
                                    "Can not mount nfs share %s" % (
                                        mountpoint,
                                        device,
                                        remotetarget))

        already_exist = False
        if not os.path.exists(mountpoint):
            logging.debug("Directory %s has been created" % mountpoint)
            os.makedirs(mountpoint)
        else:
            # To remove the potential last '/'
            path = os.path.abspath(mountpoint)
            path_bak = "%s.armonic-nfs-bak-%s" % (path, int(time.time()))
            logging.debug("Directory is moved to %s." % path_bak)
            shutil.move(path, path_bak)
            os.makedirs(mountpoint)
            already_exist = True

        logging.info("mount.nfs %s %s" % (remotetarget, mountpoint))
        thread = ProcessThread("mount.nfs", None, "test",
                               ["/sbin/mount.nfs",
                                remotetarget, mountpoint])
        if not thread.launch():
            logger.warning("Error during mount.nfs")
            raise Exception("Error during mount.nfs")

        if already_exist:
            logging.info("Files from %s/ are copied to %s/." %
                         (path_bak, path))
            shutil.copytree("%s/" % path_bak, "%s/" % path)


class Nfs_client(Lifecycle):
    initial_state = NotInstalled()
    transitions = [
        Transition(NotInstalled(), Installed()),
        Transition(Installed(), Active()),
    ]
