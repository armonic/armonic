import logging
import time
import MySQLdb

from mss.lifecycle import State, Transition, Lifecycle, provide
from mss.require import Require, RequireExternal
from mss.variable import Hostname, VString, Port
from mss.configuration_augeas import XpathNotInFile
import mss.process
import mss.state
from mss.utils import OsTypeDebian, OsTypeMBS1

import configuration


logger = logging.getLogger(__name__)


class NotInstalled(mss.state.InitialState):
    """Initial state"""
    pass

class Configured(State):
    """Configure mysql.
    - set port
    - disable skipnetworking"""
    requires=[Require([Port("port",default=3306)],name="port"),
              Require([VString("root",default="/")],name="augeas")]
    def entry(self):
        """ set mysql port """
        logger.info("%s.%-10s: edit my.cnf with requires %s"%(self.lf_name,self.name,self.requires))
        self.config=configuration.Mysql(autoload=True,augeas_root=self.requires.get('augeas').variables.root.value)
        self.config.port.set(str(self.requires.get('port').variables.port.value))
        try:
            self.config.skipNetworking.rm()
        except XpathNotInFile : pass
        self.config.save()

    @provide({'restart':True})
    def set_port(self,port):
        logger.info("%s.%-10s: provide call: set port with value %s"%(self.lf_name,self.name,port))
        self.config.port.set(port)
        self.config.save()
        return True

    @provide()
    def get_port(self):
        return self.config.port.get()

class SetRootPassword(mss.lifecycle.State):
    """Set initial Mysql root password"""
    requires=[Require([VString("pwd",default="root")],name="root_pwd")]
    def entry(self):
        logger.debug("%s.%s set mysql root password ...",self.lf_name,self.name)
        thread_mysqld = mss.process.ProcessThread("mysqldadmin", None, "test",["/usr/bin/mysqladmin","password","%s" % self.requires.get("root_pwd").variables.pwd.value],None,None,None,None)
        thread_mysqld.start()
        thread_mysqld.join()
        if thread_mysqld.code == 0:
            logger.event("%s.%s mysql root password is '%s'",self.lf_name,self.name,self.requires.get("root_pwd").variables.pwd.value)
        else:
            logger.event("%s.%s mysql root password setting failed",self.lf_name,self.name)


class ResetRootPassword(mss.lifecycle.State):
    """To change mysql root password. It launches a
    mysqld without grant table and networking, sets a new root
    password and stop mysqld."""
    requires=[Require([VString("pwd",default="root")],name="root_pwd")]
    def entry(self):
        logger.debug("%s.%s changing mysql root password ...",self.lf_name,self.name)
        thread_mysqld = mss.process.ProcessThread("mysqld --skip-grant-tables --skip-networking", None, "test",["/usr/sbin/mysqld","--skip-grant-tables","--skip-networking"],None,None,None,None)
        thread_mysqld.start()
        pwd_change=False
        for i in range(1,6):
            logger.info("%s.%s changing password ... [attempt %s/5]",self.lf_name,self.name,i)
            thread_mysql = mss.process.ProcessThread("mysql -u root CHANGE_PWD to %s"%self.requires.get("root_pwd").variables.pwd.value, None, "test",["/usr/bin/mysql",
                                                                     "-u","root",
                                                                     "-e","use mysql;update user set password=PASSWORD('%s') where User='root';flush privileges;"%self.requires.get("root_pwd").variables.pwd.value
                                                                     ],None,None,None,None)
            thread_mysql.start()
            thread_mysql.join()
            if thread_mysql.code == 0:
                pwd_change=True
                break
            logger.info("%s.%s changing password ... attempt %s FAIL",self.lf_name,self.name,i)
            time.sleep(1)
        thread_mysqld.stop()
        if pwd_change:
            logger.event("%s.%s mysql root password is not '%s'",self.lf_name,self.name,self.requires.get("root_pwd").variables.pwd.value)
        else:
            logger.event("%s.%s mysql root password changing fail",self.lf_name,self.name)


class ActiveOnDebian(mss.state.ActiveWithSystemV):
    services=["mysql"]
    supported_os_type=[OsTypeDebian()]

class ActiveOnMBS(mss.state.ActiveWithSystemd):
    """Permit to activate the service"""
    services=["mysqld"]
    supported_os_type=[OsTypeMBS1()]

class Active(mss.lifecycle.MetaState):
    """Launch mysql server and provide some actions on databases."""
    implementations = [ActiveOnDebian, ActiveOnMBS]
    @provide()
    def getDatabases(self,user='root',password='root'):
        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("show databases;")
        rows = cur.fetchall()
        return [d[0] for d in rows]

    @provide()
    def addDatabase(self,user,password,database):
        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS %s;"%database)
        rows = cur.fetchall()
        return [d[0] for d in rows]

    @provide()
    def rmDatabase(self,user,password,database):
        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("DROP DATABASE %s;"%database)
        return True

    @provide()
    def addUser(self,user,password,newUser,userPassword):
        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("GRANT ALL PRIVILEGES ON *.* TO '%s'@'%%' IDENTIFIED BY '%s' WITH GRANT OPTION;"%(newUser,userPassword))
        return True



class ConfiguredSlave(State):
    """Can be used to configure Mysql as a slave"""
    requires=[RequireExternal("Mysql","get_auth",[VString("dbName"),VString("dbUser"),Hostname("slave_host")]),
              RequireExternal("Mysql","get_dump",[VString("dbName")])
              ]

class Dump(State):
    @provide()
    def get_dump(self,dbName):
        return "iop"


class ActiveAsSlave(mss.lifecycle.MetaState):
    implementations = [ActiveOnDebian, ActiveOnMBS]
    @provide({'restart':False})
    def get_db(self,dbName,user):
        return "iop"
    def cross(self,restart=False):pass

class ActiveAsMaster(State):
    @provide()
    def get_auth(self,dbName,user,slave_host):
        return "iop"
    def cross(self,restart=False):pass

class InstalledOnMBS(mss.state.InstallPackagesUrpm):
    packages = ["mysql-MariaDB"]

class InstalledOnDebian(mss.state.InstallPackagesApt):
    packages = ["mysql-server"]

class Installed(mss.lifecycle.MetaState):
    """Install mysql package (metastate)"""
    implementations = [InstalledOnMBS, InstalledOnDebian]



class Mysql(Lifecycle):
    """Mysql lifecycle permit to install and manage a mysql
    server. Several running mode are available:
    - use mysql as a single database server
    - use mysql as a slave database server
    - use mysql as a master database server
    """
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,SetRootPassword()),
        Transition(SetRootPassword()    ,Configured()),
        Transition(Configured()      ,ResetRootPassword()),
        Transition(Configured()      ,Active()),
#        Transition(Configured()      ,ActiveOnDebian()),
        Transition(Configured()      ,ConfiguredSlave()),
        Transition(Configured()      ,ActiveAsMaster()),
        Transition(ConfiguredSlave() ,ActiveAsSlave()),
        Transition(ConfiguredSlave() ,Dump()),
        Transition(Configured() ,Dump())
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
