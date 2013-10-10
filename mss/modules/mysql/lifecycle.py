import logging
import time
import MySQLdb

from mss.lifecycle import State, Transition, Lifecycle
from mss.require import Requires, Require, RequireExternal, RequireUser
from mss.variable import Hostname, VString, Port, Password
from mss.configuration_augeas import XpathNotInFile
from mss.process import ProcessThread
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
    @Require.specify(Require([Port("port",default=3306)],name="port"))
    @Require.specify(Require([VString("root",default="/")],name="augeas"))
    def entry(self):
        """ set mysql port """
        logger.info("%s.%-10s: edit my.cnf with requires %s"%(self.lf_name,self.name,self.requires))
        self.config=configuration.Mysql(autoload=True,augeas_root=self.requires_entry.get('augeas').variables.root.value)
        self.config.port.set(str(self.requires_entry.get('port').variables.port.value))
        try:
            self.config.skipNetworking.rm()
        except XpathNotInFile : pass
        self.config.save()
        logger.event({"lifecycle":self.lf_name,"event":"listening","port":self.requires_entry.get('port').variables.port.value})


    # @provide(requires=Requires([Require([Port("port")])]),
    #          flags={'restart':True})
    def set_port(self,port):
        logger.info("%s.%-10s: provide call: set port with value %s"%(self.lf_name,self.name,port))
        self.config.port.set(port)
        self.config.save()
        return True


    def get_port(self):
        return self.config.port.get()

class SetRootPassword(mss.lifecycle.State):
    """Set initial Mysql root password"""
    @Require.specify(Require([VString("password",default="root")],name="root_pwd"))
    def entry(self):
        pwd = self.requires_entry.get('root_pwd').variables.get('password').value #password.value

        logger.debug("%s.%s set mysql root password ...",self.lf_name,self.name)
        thread_mysqld = ProcessThread("mysql", None, "test",
                                      ["/usr/bin/mysql", "-u", "root", "--password=%s"%pwd, "-e", "quit"],
                                      None,None,None,None)
        if thread_mysqld.launch():
            logger.info("%s.%s mysql root password already set to 'root'",self.lf_name,self.name)
            return
        thread_mysqld = ProcessThread("mysqldadmin", None, "test",
                                      ["/usr/bin/mysqladmin","password",pwd],
                                      None,None,None,None)
        if thread_mysqld.launch():
            logger.info("%s.%s mysql root password is '%s'",
                         self.lf_name,self.name,pwd)
            self.root_password=pwd
        else:
            logger.info("%s.%s mysql root password setting failed",self.lf_name,self.name)
            raise Exception("SetRootPassword failed with pwd %s" % pwd)


class ResetRootPassword(mss.lifecycle.State):
    """To change mysql root password. It launches a
    mysqld without grant table and networking, sets a new root
    password and stop mysqld."""
    @Require.specify(Require([VString("pwd",default="root")],name="root_pwd"))
    def entry(self):
        logger.debug("%s.%s changing mysql root password ...",self.lf_name,self.name)
        thread_mysqld = ProcessThread("mysqld --skip-grant-tables --skip-networking", None, "test",["/usr/sbin/mysqld","--skip-grant-tables","--skip-networking"],None,None,None,None)
        thread_mysqld.start()
        pwd_change=False
        for i in range(1,6):
            logger.info("%s.%s changing password ... [attempt %s/5]",self.lf_name,self.name,i)
            thread_mysql = ProcessThread("mysql -u root CHANGE_PWD to %s"%self.requires_entry.get("root_pwd").variables.pwd.value, None, "test",["/usr/bin/mysql",
                                                                     "-u","root",
                                                                     "-e","use mysql;update user set password=PASSWORD('%s') where User='root';flush privileges;"%self.requires_entry.get("root_pwd").variables.pwd.value
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
            logger.info("%s.%s mysql root password is not '%s'",self.lf_name,self.name,self.requires_entry.get("root_pwd").variables.pwd.value)
        else:
            logger.info("%s.%s mysql root password changing fail",self.lf_name,self.name)


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

    @Require.specify(Require([VString('user'),VString('password')]))
    def getDatabases(self,requires):
        user = requires_entry.get('this').variables.get('user').value
        password = requires_entry.get('this').variables.get('password').value

        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("show databases;")
        rows = cur.fetchall()
        return [d[0] for d in rows]

    @Require.specify(RequireUser(name='mysqlRoot',
                                 provided_by='Mysql.SetRootPassword.entry.root_pwd.password',
                                 variables=[Password('root_password')]))
    @Require.specify(Require([VString('user'), VString('password'), VString('database')]))
    def addDatabase(self,requires):
        """Add a user and a database. User have permissions on all databases."""
        database = requires_entry.get('this').variables.get('database').value
        user = requires_entry.get('this').variables.get('user').value
        password = requires_entry.get('this').variables.get('password').value
        mysql_root_pwd = requires_entry.get('mysqlRoot').variables.get('root_password').value

        if database in ['database']:
            raise mss.common.ProvideError('Mysql', self.name, 'addDatabase', "database name can not be '%s'"%database)
        self.addUser('root', mysql_root_pwd, user, password)
        con = MySQLdb.connect('localhost', user, password);
        cur = con.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS %s;"%database)
        rows = cur.fetchall()
        return [d[0] for d in rows]


    @Require.specify(RequireUser(name='mysql_root',
                                 provided_by='SetRootPassword.entry',
                                 variables=[Password('user'),Password('password')]))
    @Require.specify(Require([VString('database')]))
    def rmDatabase(self,user,password,database):
        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("DROP DATABASE %s;"%database)
        return True


    @Require.specify(Require([VString('user'), VString('password'), VString('database')]))
    def addUser(self,user,password,newUser,userPassword):
        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("GRANT ALL PRIVILEGES ON *.* TO '%s'@'%%' IDENTIFIED BY '%s' WITH GRANT OPTION;"%(newUser,userPassword))
        return True


class ConfiguredSlave(State):
    """Can be used to configure Mysql as a slave"""
#    requires=Requires([RequireExternal("Mysql","get_auth",[VString("dbName"),VString("dbUser"),Hostname("slave_host")]),
#                       RequireExternal("Mysql","get_dump",[VString("dbName")])
#                       ])

class Dump(State):
#    @provide()
    def get_dump(self,dbName):
        return "iop"


class ActiveAsSlave(mss.lifecycle.MetaState):
    implementations = [ActiveOnDebian, ActiveOnMBS]
#    @provide(flags={'restart':False})
    def get_db(self,dbName,user):
        return "iop"
    def cross(self,restart=False):pass

class ActiveAsMaster(State):
#    @provide()
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
        Transition(Configured()      ,ConfiguredSlave()),
        Transition(Configured()      ,ActiveAsMaster()),
        Transition(ConfiguredSlave() ,ActiveAsSlave()),
        Transition(ConfiguredSlave() ,Dump()),
        Transition(Configured() ,Dump())
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
