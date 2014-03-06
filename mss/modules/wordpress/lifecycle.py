import logging

from mss.lifecycle import State, Transition, Lifecycle
from mss.require import Require, RequireLocal, RequireExternal
from mss.provide import Provide
from mss.variable import VString, Password
from mss.states import InitialState, CopyTemplates, InstallPackagesUrpm, InstallPackagesApt
import configuration
import mss.utils


logger = logging.getLogger(__name__)


class NotInstalled(InitialState):
    pass


class Template(CopyTemplates):
    """Copy wp-config-sample.php to wp-config.php"""
    supported_os_type = [mss.utils.OsTypeMBS()]
    src_files = ["/var/www/wordpress/wp-config-sample.php"]
    dst_files = ["/var/www/wordpress/wp-config.php"]


class Configured(State):
    """Set database informations"""
    supported_os_type = [mss.utils.OsTypeMBS()]

    @Require('augeas', [VString("root", default="/")])
    @RequireExternal("db", "//Mysql//addDatabase",
                     provide_args=[VString("user",
                                           default="wordpress_user"),
                                   Password("password",
                                            default="wordpress_pwd"),
                                   VString("database",
                                           default="wordpress_db")])
    def enter(self):
        """set value in wp-config.php"""
        self.conf = configuration.Wordpress(autoload=True, augeas_root=self.requires_enter.get('augeas').variables().root.value)
        print self.requires_enter.get('db').variables()
        tmp = self.requires_enter.get('db').variables()
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
    supported_os_type = [mss.utils.OsTypeMBS()]

    @RequireLocal("http_document", "//Httpd//get_documentRoot",
                  provide_args=[VString("httpdDocumentRoot",
                                default="/var/www/wordpress")])
    @RequireLocal("http_start", "//Httpd//start")
    def enter(self):
        self.httpdDocumentRoot = self.requires_enter.get('http_document').variables().httpdDocumentRoot.value
        logger.debug("%s.%-10s: TODO : write to MSS database : wordpress use a vhost=%s" % (self.lf_name, self.name, self.httpdDocumentRoot))

    def leave(self):
        logger.debug("you should call 'apache.leaveActiveState(%s)'" % self.httpdDocumentRoot)

    @Provide()
    def get_website(self, requires):
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
    def enter(self):
        pass

    @Provide()
    def get_website(self, requires):
        pass


class Installed(InstallPackagesUrpm):
    packages = ["wordpress"]


class InstalledOnDebian(InstallPackagesApt):
    packages = ["wordpress"]
    supported_os_type = [mss.utils.OsTypeDebianWheezy()]


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
