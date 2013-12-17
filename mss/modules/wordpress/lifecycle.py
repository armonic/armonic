from mss.lifecycle import State, Transition, Lifecycle, provide
from mss.require import Require, RequireLocal, RequireExternal
from mss.variable import VString, Password
import mss.state
import configuration
import mss.common
import logging

logger=logging.getLogger(__name__)

class NotInstalled(mss.state.InitialState):pass

class Template(mss.state.CopyTemplate):
    """Copy wp-config-sample.php to wp-config.php"""
    supported_os_type = [mss.utils.OsTypeMBS()]
    src="/var/www/wordpress/wp-config-sample.php"
    dst="/var/www/wordpress/wp-config.php"

class Configured(State):
    """Set database informations"""
    supported_os_type = [mss.utils.OsTypeMBS()]

    @Require('augeas', [VString("root",default="/")])
    @RequireExternal("db", "//Mysql//addDatabase",
                     provide_args=[VString("user",default="wordpress_user"),
                                   Password("password",default="wordpress_pwd"),
                                   VString("database",default="wordpress_db")])
    def entry(self):
        """set value in wp-config.php"""
        logger.info("%s.%-10s: edit php wordpress configuration file with %s"%(self.lf_name,self.name,self.requires_entry))
        self.conf=configuration.Wordpress(autoload=True,augeas_root=self.requires_entry.get('augeas').variables().root.value)
        print self.requires_entry.get('db').variables()
        tmp=self.requires_entry.get('db').variables()
        self.conf.configure(tmp.database.value, tmp.user.value, tmp.password.value, tmp.host.value)
        logger.event({"lifecycle":self.lf_name,"event":"binding","target":tmp.host.value})

    def leave(self):
        """ set wordpress.php """
        logger.info("undo php wordpress configuration file modifications...")


class Active(State):
    httpdDocumentRoot = None

    supported_os_type = [mss.utils.OsTypeMBS()]

    @RequireLocal("http_document", "//Httpd//get_documentRoot",
                      provide_args=[VString("httpdDocumentRoot",
                                    default="/var/www/wordpress")])
    @RequireLocal("http_start","//Httpd//start")
    def entry(self):
        logger.info("%s.%-10s: activation with %s"%(self.lf_name,self.name,self.requires_entry))
        self.httpdDocumentRoot=self.requires_entry.get('http_document').variables().httpdDocumentRoot.value
        logger.info("%s.%-10s: TODO : write to MSS database : wordpress use a vhost=%s"%(self.lf_name,self.name,self.httpdDocumentRoot))

    def leave(self):
        logger.info("you should call 'apache.leaveActiveState(%s)'"%self.httpdDocumentRoot)

    @provide()
    def get_website(self, requires):
        return

    @provide()
    def get_network_port(self):
        """Return the httpd listening port for this wordpress installation"""
        return "Call Httpd.getPortByDocumentRoot('%s')"%self.httpdDocumentRoot

class ActiveWithNfs(State):
    """Get wp-content from a NFS share."""
    @RequireLocal(
        "nfs", 
        "//Nfs_client//mount", 
        provide_args=[
            VString(
                "path",
                from_xpath = "Wordpress/Active/entry/http_document/httpdDocumentRoot",
                modifier = "%s/wp-content"),
            VString("name", default = "wordpress")])
    def entry(self):
        pass
    
    @provide()
    def get_website(self, requires):
        pass

class Installed(mss.state.InstallPackagesUrpm):
    packages=["wordpress"]

class InstalledOnDebian(mss.state.InstallPackagesUrpm):
    packages=["wordpress"]
    supported_os_type = [mss.utils.OsTypeDebianWheezy()]

class Wordpress(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Template()),
        Transition(NotInstalled()    ,InstalledOnDebian()),
        Transition(InstalledOnDebian()    ,Template()),
        Transition(Template()    ,Configured()),
        Transition(Configured()      ,Active()),
        Transition(Active()      ,ActiveWithNfs()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
