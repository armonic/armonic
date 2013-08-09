import logging
import time
import MySQLdb

from mss.lifecycle import State, Transition, Lifecycle, provide
from mss.require import Require, RequireExternal, VHost, VString, VPort
from mss.configuration_augeas import XpathNotInFile
import mss.process
import mss.state

import configuration


logger = logging.getLogger(__name__)


class NotInstalled(State):
    """Initial state"""
    pass
class Configured(State):
    """Permit to configure a module. Basically, it sets mysql port"""
    requires=[Require([VPort("port",default="3306")]),
              Require([VString("augeas_root",default="/")])]
    def entry(self,requires):
        """ set mysql port """
        logger.info("%s.%-10s: edit my.cnf with requires %s"%(self.module(),self.name,requires))
        self.config=configuration.Mysql(autoload=True,augeas_root=requires['augeas_root'][0]['augeas_root'])
        self.config.port.set(requires['port'][0]['port'])
        try:
            self.config.skipNetworking.rm()
        except XpathNotInFile : pass
        self.config.save()

    @provide({'restart':True})
    def set_port(self,port):
        logger.info("%s.%-10s: provide call: set port with value %s"%(self.module(),self.name,port))
        self.config.port.set(port)
        self.config.save()
        return True

    @provide()
    def get_port(self):
        return self.config.port.get()

class ResetRootPassword(mss.lifecycle.State):
    """Go to this state to change mysql root password. It launches a
    mysqld without grant table and networking, sets a new root
    password and stop mysqld."""
    requires=[Require([VString("pwd",default="root")],name="root_pwd")]
    def entry(self,requires={}):
        logger.debug("%s.%s changing mysql root password ...",self.module(),self.name)
        thread_mysqld = mss.process.ProcessThread("mysqld --skip-grant-tables --skip-networking", None, "test",["/usr/sbin/mysqld","--skip-grant-tables","--skip-networking"],None,None,None,None)
        thread_mysqld.start()
        pwd_change=False
        for i in range(1,6):
            logger.info("%s.%s changing password ... [attempt %s/5]",self.module(),self.name,i)
            thread_mysql = mss.process.ProcessThread("mysql -u root CHANGE_PWD to %s"%requires["root_pwd"][0]["pwd"], None, "test",["/usr/bin/mysql",
                                                                     "-u","root",
                                                                     "-e","use mysql;update user set password=PASSWORD('%s') where User='root';flush privileges;"%requires["root_pwd"][0]["pwd"]
                                                                     ],None,None,None,None)
            thread_mysql.start()
            thread_mysql.join()
            if thread_mysql.code == 0:
                pwd_change=True
                break
            logger.info("%s.%s changing password ... attempt %s FAIL",self.module(),self.name,i)
            time.sleep(1)
        thread_mysqld.stop()
        if pwd_change:
            logger.event("%s.%s mysql root password is not '%s'",self.module(),self.name,requires["root_pwd"][0]["pwd"])
        else:
            logger.event("%s.%s mysql root password changing fail",self.module(),self.name)

class Active(mss.state.ActiveWithSystemd):
    """Permit to activate the service"""
    services=["mysqld"]

    @provide()
    def getDatabases(self,user,password):
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
    requires=[RequireExternal("Mysql","get_auth",[VString("dbName"),VString("dbUser"),VHost("slave_host")]),
              RequireExternal("Mysql","get_dump",[VString("dbName")])
              ]

class Dump(State):
    @provide()
    def get_dump(self,dbName):
        return "iop"


class ActiveAsSlave(State):
    @provide({'restart':False})
    def get_db(self,dbName,user):
        return "iop"
    def cross(self,restart=False):pass

class ActiveAsMaster(State):
    @provide()
    def get_auth(self,dbName,user,slave_host):
        return "iop"
    def cross(self,restart=False):pass

class Installed(mss.state.InstallPackages):
    packages=["mysql-MariaDB"]

class Mysql(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,ResetRootPassword()),
        Transition(Configured()      ,Active()),
        Transition(Configured()      ,ConfiguredSlave()),
        Transition(Configured()      ,ActiveAsMaster()),
        Transition(ConfiguredSlave() ,ActiveAsSlave()),
        Transition(ConfiguredSlave() ,Dump()),
        Transition(Configured() ,Dump())
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
