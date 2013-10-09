from mss.lifecycle import State, Transition, Lifecycle
from mss.require import Require, RequireLocal, RequireExternal, Requires
from mss.variable import VString, Password
import mss.state
import configuration
import mss.common
import logging

logger=logging.getLogger(__name__)

class NotInstalled(mss.state.InitialState):pass

class Template(mss.state.CopyTemplate):
    supported_os_type = [mss.utils.OsTypeMBS1()]
    src="/var/www/wordpress/wp-config-sample.php"
    dst="/var/www/wordpress/wp-config.php"

class Configured(State):
    supported_os_type = [mss.utils.OsTypeMBS1()]

    @Require.specify(Require([VString("root",default="/")],name='augeas'))
    @Require.specify(RequireExternal("Mysql","addDatabase",
                                      provide_args=[VString("user",default="wordpress_user"),
                                                    Password("password",default="wordpress_pwd"),
                                                    VString("database",default="wordpress_db")]))
    def entry(self):
        """set value in wp-config.php"""
        logger.info("%s.%-10s: edit php wordpress configuration file with %s"%(self.lf_name,self.name,self.requires))
        self.conf=configuration.Wordpress(autoload=True,augeas_root=self.requires_entry.get('augeas').variables.root.value)
        print self.requires_entry.get('Mysql.addDatabase').variables
        tmp=self.requires_entry.get('Mysql.addDatabase').variables[0]
        self.conf.configure(tmp.database.value, tmp.user.value, tmp.password.value, tmp.host.value)
        logger.event({"lifecycle":self.lf_name,"event":"binding","target":tmp.host.value})
    def leave(self):
        """ set wordpress.php """
        logger.info("undo php wordpress configuration file modifications...")


class Active(State):
    supported_os_type = [mss.utils.OsTypeMBS1()]

    @Require.specify(RequireLocal("Httpd","get_documentRoot",
                                   provide_args=[VString("httpdDocumentRoot",
                                                         default="/var/www/wordpress")]))
    @Require.specify(RequireLocal("Httpd","start"))
    def entry(self):
        logger.info("%s.%-10s: activation with %s"%(self.lf_name,self.name,self.requires))
        self.httpdDocumentRoot=self.requires_entry.get('Httpd.get_documentRoot').variables[0].httpdDocumentRoot.value
        logger.info("%s.%-10s: TODO : write to MSS database : wordpress use a vhost=%s"%(self.lf_name,self.name,self.httpdDocumentRoot))
    def leave(self):
        logger.info("you should call 'apache.leaveActiveState(%s)'"%self.httpdDocumentRoot)

    @Require.specify()
    def get_site(self,requires):
        return 

        #@provide()
    def get_network_port(self):
        """Return the httpd listening port for this wordpress installation"""
        return "Call Httpd.getPortByDocumentRoot('%s')"%self.httpdDocumentRoot


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
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
