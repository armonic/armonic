from mss.lifecycle import State, Transition, Lifecycle, provide
from mss.require import Require, RequireLocal, RequireExternal, VString, VPassword
import mss.state
import configuration
import mss.common
import logging

logger=logging.getLogger(__name__)

class NotInstalled(State):pass
class Configured(State):
    requires=[
        Require([VString("augeas_root",default="/")]),
        RequireExternal("Mysql","get_db",[VString("dbName",default="wordpress_db"),
                                          VString("dbUser",default="wordpress_user"),
                                          VPassword("dbPassword",default="wordpress_pwd")])]
    def entry(self,requires):
        """set value in wp-config.php"""
        logger.info("%s.%-10s: edit php wordpress configuration file with %s"%(self.lf_name,self.name,requires))
        self.conf=configuration.Wordpress(autoload=True,augeas_root=requires['augeas_root'][0]['augeas_root'])
        self.conf.configure(requires['Mysql.get_db'][0]['dbName'],requires['Mysql.get_db'][0]['dbUser'],requires['Mysql.get_db'][0]['dbPassword'],requires['Mysql.get_db'][0]['host'])
    def leave(self):
        """ set wordpress.php """
        logger.info("undo php wordpress configuration file modifications...")


class Active(State):
    requires=[RequireLocal("Httpd","get_documentRoot",[VString("httpdDocumentRoot",default="/var/www/wordpress")]),
              RequireLocal("Httpd","start",[])]
    def entry(self,requires):
        logger.info("%s.%-10s: activation with %s"%(self.lf_name,self.name,requires))
        self.httpdDocumentRoot=requires['Httpd.get_documentRoot'][0]['httpdDocumentRoot']
        logger.info("%s.%-10s: TODO : write to MSS database : wordpress use a vhost=%s"%(self.lf_name,self.name,requires['Httpd.get_documentRoot'][0]['httpdDocumentRoot']))
    def leave(self):
        logger.info("you should call 'apache.leaveActiveState(%s)'"%self.httpdDocumentRoot)

    @provide()
    def get_network_port(self):
        """Return the httpd listening port for this wordpress installation"""
        return "Call Httpd.getPortByDocumentRoot('%s')"%self.httpdDocumentRoot


class Installed(mss.state.InstallPackages):
    packages=["wordpress"]

class Wordpress(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,Active()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
