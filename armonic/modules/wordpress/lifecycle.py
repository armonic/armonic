import logging

from armonic.lifecycle import State, Transition, Lifecycle
from armonic.require import Require, RequireLocal, RequireExternal
from armonic.provide import Provide
from armonic.variable import VString, Password
from armonic.states import InitialState, CopyTemplates, InstallPackagesUrpm, InstallPackagesApt
import configuration
import armonic.utils


logger = logging.getLogger(__name__)


class NotInstalled(InitialState):
    pass


class Template(CopyTemplates):
    """Copy wp-config-sample.php to wp-config.php"""
    supported_os_type = [armonic.utils.OsTypeMBS()]
    src_files = ["/var/www/wordpress/wp-config-sample.php"]
    dst_files = ["/var/www/wordpress/wp-config.php"]


class Configured(State):
    """Set database informations"""
    supported_os_type = [armonic.utils.OsTypeMBS()]

    @Require('augeas', [VString("root", default="/")])
    @RequireExternal("db", "//Mysql//addDatabase",
                     provide_args=[VString("user",
                                           default="wordpress_user"),
                                   Password("password",
                                            default="wordpress_pwd"),
                                   VString("database",
                                           default="wordpress_db")])
    def enter(self, requires):
        """set value in wp-config.php"""
        self.conf = configuration.Wordpress(autoload=True, augeas_root=requires.augeas.variables().root.value)
        print requires.db.variables()
        tmp = requires.db.variables()
        logger.info("Editing wordpress configuration file with db:%s user:%s pwd:%s host:%s" % (
            tmp.database.value, tmp.user.value, tmp.password.value, tmp.host.value))

        self.conf.configure(tmp.database.value,
                            tmp.user.value,
                            tmp.password.value,
                            tmp.host.value)
        logger.event({"lifecycle": self.lf_name,
                      "event": "binding",
                      "target": tmp.host.value})

    def leave(self):
        """ set wordpress.php """
        logger.info("undo php wordpress configuration file modifications...")


class Active(State):
    httpdDocumentRoot = None
    supported_os_type = [armonic.utils.OsTypeMBS()]

    @RequireLocal("http_document", "//Httpd//get_documentRoot",
                  provide_args=[VString("httpdDocumentRoot",
                                default="/var/www/wordpress")])
    @RequireLocal("http_start", "//Httpd//start")
    def enter(self, requires):
        self.httpdDocumentRoot = requires.http_document.variables().httpdDocumentRoot.value
        logger.debug("%s.%-10s: TODO : write to MSS database : wordpress use a vhost=%s" % (self.lf_name, self.name, self.httpdDocumentRoot))

    def leave(self):
        logger.debug("you should call 'apache.leaveActiveState(%s)'" % self.httpdDocumentRoot)

    @Provide(label="Create a Wordpress",
             tags=["web", "app"])
    def get_website(self):
        return

    @Provide()
    def get_network_port(self):
        """Return the httpd listening port for this wordpress installation"""
        return "Call Httpd.getPortByDocumentRoot('%s')" % self.httpdDocumentRoot


class ActiveWithNfs(State):
    """Get wp-content from a NFS share."""
    @RequireLocal(
        "nfs",
        "//Nfs_client//mount",
        provide_args=[
            VString(
                "path",
                from_xpath="Wordpress/Active/enter/http_document/httpdDocumentRoot",
                modifier="%s/wp-content"),
            VString("name", default="wordpress")])
    def enter(self, requires):
        pass

    @Provide(label="Create a Wordpress using an NFS share",
             help=("Wordpress data will be stored on the NFS share allowing to have multiple instances,"),
             tags=["web", "expert", "nfs"])
    def get_website(self):
        pass


class Installed(InstallPackagesUrpm):
    packages = ["wordpress"]


class InstalledOnDebian(InstallPackagesApt):
    packages = ["wordpress"]
    supported_os_type = [armonic.utils.OsTypeDebianWheezy()]


class Wordpress(Lifecycle):
    initial_state = NotInstalled()
    transitions = [
        Transition(NotInstalled(), Installed()),
        Transition(Installed(), Template()),
        Transition(NotInstalled(), InstalledOnDebian()),
        Transition(InstalledOnDebian(), Template()),
        Transition(Template(), Configured()),
        Transition(Configured(), Active()),
        Transition(Active(), ActiveWithNfs()),
    ]
