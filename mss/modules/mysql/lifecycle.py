import logging
import time
import MySQLdb

from mss.lifecycle import State, Transition, Lifecycle, provide
from mss.require import Requires, Require, RequireExternal, RequireUser, RequireLocal
from mss.variable import Hostname, VString, Port, Password, VInt
from mss.configuration_augeas import XpathNotInFile
from mss.process import ProcessThread
import mss.state
from mss.utils import OsTypeDebian, OsTypeMBS

import configuration


logger = logging.getLogger(__name__)


class NotInstalled(mss.state.InitialState):
    """Initial state"""
    pass

class Configured(State):
    """Configure mysql.
    - set port
    - disable skipnetworking"""
    @Require([Port("port",default=3306)], name="port")
    @Require([VString("root",default="/")], name="augeas")
    def entry(self):
        """ set mysql port """
        logger.info("%s.%-10s: edit my.cnf with requires %s"%(self.lf_name,self.name,self.requires_entry))
        self.config=configuration.Mysql(autoload=True,augeas_root=self.requires_entry.get('augeas').variables.root.value)
        self.config.port.set(str(self.requires_entry.get('port').variables.port.value))
#        self.config.server_id.set("1")
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

    @Require([VString("password",default="root")], name="root_pwd")
    def entry(self):
        pwd = self.requires_entry.get('root_pwd').variables.get('password').value #password.value
        thread_mysqld = ProcessThread("mysql", None, "test",
                                      ["/bin/systemctl", "start", "mysqld.service"])
        if not thread_mysqld.launch():
            logger.info("Error at systemctl start mysqld.service (launch for mysqladmin)")
            raise Exception("Error at mysqld launching for mysqladmin")

        logger.debug("%s.%s set mysql root password ...",self.lf_name,self.name)
        thread_mysqld = ProcessThread("mysql", None, "test",
                                      ["/usr/bin/mysql", "-u", "root",
                                       "--password=%s"%pwd, "-e", "quit"])

        if thread_mysqld.launch():
            logger.info("%s.%s mysql root password already set to 'root'",self.lf_name,self.name)
            return
        thread_mysqld = ProcessThread("mysqldadmin", None, "test",
                                      ["/usr/bin/mysqladmin","password",pwd])

        if thread_mysqld.launch():
            logger.info("%s.%s mysql root password is '%s'",
                         self.lf_name,self.name,pwd)
            self.root_password=pwd
        else:
            logger.info("%s.%s mysql root password setting failed",self.lf_name,self.name)
            raise Exception("SetRootPassword failed with pwd %s" % pwd)

        thread_mysqld = ProcessThread("mysql", None, "test",
                                      ["/bin/systemctl", "stop", "mysqld.service"])
        if not thread_mysqld.launch():
            logger.info("Error at systemctl stop mysqld.service (launch for mysqladmin)")
            raise Exception("Error at mysqld launching for mysqladmin")



class ResetRootPassword(mss.lifecycle.State):
    """To change mysql root password. It launches a
    mysqld without grant table and networking, sets a new root
    password and stop mysqld."""
    supported_os_type=[OsTypeMBS()]

    @Require([VString("password",default="root")], name="root_pwd")
    def entry(self):
        logger.debug("%s.%s changing mysql root password ...",self.lf_name,self.name)
        logger.debug("%s.%s ensuring that mysqld is stopped ...",self.lf_name,self.name)
        thread = ProcessThread("mysql", None, "test",
                                      ["/bin/systemctl", "stop", "mysqld.service"])
        if not thread.launch():
            logger.info("Error at systemctl stop mysqld.service (launch for mysqladmin)")
            raise Exception("Error at mysqld launching for mysqladmin")

        thread_mysqld = ProcessThread("mysqld --skip-grant-tables --skip-networking", None, "test",["/usr/sbin/mysqld","--skip-grant-tables","--skip-networking"],None,None,None,None)
        thread_mysqld.start()
        pwd_change=False
        for i in range(1,6):
            logger.info("%s.%s changing password ... [attempt %s/5]",self.lf_name,self.name,i)
            thread_mysql = ProcessThread("mysql -u root CHANGE_PWD to %s"%self.requires_entry.get("root_pwd").variables.password.value, None, "test",
                                         ["/usr/bin/mysql",
                                          "-u","root",
                                          "-e","use mysql;update user set password=PASSWORD('%s') where User='root';flush privileges;"%self.requires_entry.get("root_pwd").variables.password.value
                                          ])
            thread_mysql.start()
            thread_mysql.join()
            if thread_mysql.code == 0:
                pwd_change=True
                break
            logger.info("%s.%s changing password ... attempt %s FAIL",self.lf_name,self.name,i)
            time.sleep(1)
        thread_mysqld.stop()
        if pwd_change:
            logger.info("%s.%s mysql root password is now '%s'",self.lf_name,self.name,self.requires_entry.get("root_pwd").variables.password.value)
        else:
            logger.info("%s.%s mysql root password changing fail",self.lf_name,self.name)


class ActiveOnDebian(mss.state.ActiveWithSystemV):
    services=["mysql"]
    supported_os_type=[OsTypeDebian()]

class ActiveOnMBS(mss.state.ActiveWithSystemd):
    """Permit to activate the service"""
    services=["mysqld"]
    supported_os_type=[OsTypeMBS()]

class EnsureMysqlIsStopped(mss.state.ActiveWithSystemd):
    services=["mysqld"]
    supported_os_type=[OsTypeMBS()]

    def entry(self):
        mss.state.ActiveWithSystemd.leave(self)

    def leave(self):
        pass
    def cross(self):
        pass

class ActiveOnMBS(mss.state.ActiveWithSystemd):
    """Permit to activate the service"""
    services=["mysqld"]
    supported_os_type=[OsTypeMBS()]


class Active(mss.lifecycle.MetaState):
    """Launch mysql server and provide some actions on databases."""
    implementations = [ActiveOnDebian, ActiveOnMBS]

    @Require([VString('user'), VString('password')])
    def getDatabases(self,requires):
        user = requires.get('this').variables.get('user').value
        password = requires.get('this').variables.get('password').value

        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("show databases;")
        rows = cur.fetchall()
        return [d[0] for d in rows]

    @RequireUser(name='mysqlRoot',
                     provided_by='Mysql.SetRootPassword.entry.root_pwd.password',
                     variables=[Password('root_password')])
    @Require([VString('user'), VString('password'), VString('database')])
    def addDatabase(self,requires):
        """Add a user and a database. User have permissions on all databases."""
        database = requires.get('this').variables.get('database').value
        user = requires.get('this').variables.get('user').value
        password = requires.get('this').variables.get('password').value
        mysql_root_pwd = requires.get('mysqlRoot').variables.get('root_password').value

        if database in ['database']:
            raise mss.common.ProvideError('Mysql', self.name, 'addDatabase', "database name can not be '%s'"%database)
        self.addUser('root', mysql_root_pwd, user, password)
        con = MySQLdb.connect('localhost', user, password);
        cur = con.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS %s;"%database)
        rows = cur.fetchall()
        return [d[0] for d in rows]


    @RequireUser(name='mysql_root',
                     provided_by='SetRootPassword.entry',
                     variables=[Password('user'),Password('password')])
    @Require([VString('database')])
    def rmDatabase(self,user,password,database):
        con = MySQLdb.connect('localhost', user,
                              password);
        cur = con.cursor()
        cur.execute("DROP DATABASE %s;"%database)
        return True


    #@Require([VString('user'), VString('password'), VString('database')])
    def addUser(self,user,password,newUser,userPassword):
        con = MySQLdb.connect('localhost', user,
                              password);

        cur = con.cursor()
        cmd = "GRANT ALL PRIVILEGES ON *.* TO '%s'@'%%' IDENTIFIED BY '%s' WITH GRANT OPTION;"%(newUser,userPassword)
        logger.debug("$mysql> %s" % cmd)
        cur.execute(cmd)
        cmd = "GRANT ALL PRIVILEGES ON *.* TO '%s'@'localhost' IDENTIFIED BY '%s' WITH GRANT OPTION;"%(newUser,userPassword)
        logger.debug("$mysql> %s" % cmd)
        cur.execute(cmd)
        logger.info("mysql user '%s' with password '%s' has been created." % (newUser,userPassword))
        return True


class ConfiguredAsSlave(State):
    """Configure Mysql as a slave"""
    @Require([VInt('server_id',default=2)])
    @Require([VString("root",default="/")], name="augeas")
    def entry(self):
        self.config=configuration.Mysql(autoload=True,augeas_root=self.requires_entry.get('augeas').variables.root.value)
        self.config.server_id.set(str(self.requires_entry.get('this').variables.server_id.value))
        self.config.log_bin.set("mysql-bin")
        self.config.save()

class ActiveAsSlave(mss.lifecycle.MetaState):
    """Take a filepath of a dump and apply this dump.
    To obtain the dump, you can call the provide Mysql.get_dump.
    The dump file is removed after its application.
    """
    # This implementation is not clean. We should be able to automate
    # the transfert of the dump file...
    #
    # An idea is that Mysql.get_dump returns a special Variable such
    # as VFileMSS3. This would be an url such as
    # http://ip_master/dump.file or anything else.  Then, in VFileMSS3
    # would have a get_file_in_local method to proceed to downloading. 
    implementations = [ActiveOnDebian, ActiveOnMBS]

    @RequireUser(name='mysqlRoot',
                     provided_by='Mysql.SetRootPassword.entry.root_pwd.password',
                     variables=[Password('root_password')])
    @RequireExternal(lf_name='Mysql',provide_name='get_dump',
                     provide_ret=[VString('filePath'),VString('logFile'), VInt('logPosition')])
    @RequireExternal(lf_name='Mysql',provide_name='add_slave_auth',
                     provide_args=[VString('user',default='replication'),
                                   VString('password',default='repl_pwd')])
    def entry(self):
        root_user = "root"
        root_password = self.requires_entry.get('mysqlRoot').variables.get('root_password').value
        filePath = self.requires_entry.get('Mysql.get_dump').variables[0].filePath.value
        logFile = self.requires_entry.get('Mysql.get_dump').variables[0].logFile.value
        logPosition = self.requires_entry.get('Mysql.get_dump').variables[0].logPosition.value
        slave_user = self.requires_entry.get('Mysql.add_slave_auth').variables[0].get('user').value
        slave_password = self.requires_entry.get('Mysql.add_slave_auth').variables[0].get('password').value
        master_host = self.requires_entry.get('Mysql.add_slave_auth').variables[0].get('host').value
        
        logger.debug("%s %s %s" , filePath, logFile, logPosition)
        thread = ProcessThread("mysql", None, "test",
                               ["/usr/bin/mysql", 
                                "-u", "root", 
                                "--password=%s"%root_password,
                                "-e","stop slave ; source %s ; start slave;" % filePath])
        if not thread.launch():
            logger.info("Error during mysql source dumpfile")
            raise Exception("Error during mysql source dumpfile")
        

        con = MySQLdb.connect('localhost', root_user, root_password);
        cur = con.cursor()
        cur.execute("slave stop;")
        cur.execute("CHANGE MASTER TO MASTER_HOST='%s', MASTER_USER='%s', MASTER_PASSWORD='%s', MASTER_LOG_FILE='%s', MASTER_LOG_POS=%s;" % (
                master_host,
                slave_user,
                slave_password,
                logFile,
                logPosition))
        cur.execute("slave start;")

    @RequireUser(name='mysqlRoot',
                     provided_by='Mysql.SetRootPassword.entry.root_pwd.password',
                     variables=[Password('root_password')])
    def slave_status(self,requires):
        root_user = "root"
        root_password = requires.get('mysqlRoot').variables.get('root_password').value

        con = MySQLdb.connect('localhost', root_user, root_password);
        cur = con.cursor()
        cur.execute("SHOW SLAVE STATUS;")
        rows = cur.fetchall()
        return rows

class ConfiguredAsMaster(State):
    """Expose all databases to slave except mysql and informationshema."""
    @Require([VInt('server_id',default=1)])
    @Require([VString("root",default="/")], name="augeas")
    def entry(self):
        self.config=configuration.Mysql(autoload=True,augeas_root=self.requires_entry.get('augeas').variables.root.value)
        self.config.server_id.set(str(self.requires_entry.get('this').variables.server_id.value))
        self.config.log_bin.set("mysql-bin")

        # Management of bin_log_ignore directive.
        # First we remove all of them
        for i in range(len(self.config.binlog_ignore_dbs)-1,-1,-1):
            self.config.binlog_ignore_dbs[i].rm()
        # Second, we add mysql and informationschema
        tmp = configuration.BinLogIgnoreDb()
        tmp.value = "mysql"
        self.config.binlog_ignore_dbs.append(tmp)
        tmp = configuration.BinLogIgnoreDb()
        tmp.value = "informationschema"
        self.config.binlog_ignore_dbs.append(tmp)

        self.config.save()

class ActiveAsMaster(mss.lifecycle.MetaState):
    implementations = [ActiveOnDebian, ActiveOnMBS]

    @Require([VString('user',default='replication'),
              VString('password',default='password')],
             name='slave_id')
    @RequireUser(name='mysqlRoot',
                     provided_by='Mysql.SetRootPassword.entry.root_pwd.password',
                     variables=[Password('root_password')])
    def add_slave_auth(self,requires):
        root_user = "root"
        root_password = requires.get('mysqlRoot').variables.get('root_password').value
        slave_user = requires.get('slave_id').variables.get('user').value
        slave_password = requires.get('slave_id').variables.get('password').value

        con = MySQLdb.connect('localhost', root_user, root_password);
        cur = con.cursor()
        cur.execute("GRANT REPLICATION SLAVE ON *.* TO '%s'@'%%' IDENTIFIED BY '%s';"% (slave_user, slave_password))
        cur.execute("FLUSH PRIVILEGES;")
        
    @RequireUser(name='mysqlRoot',
                     provided_by='Mysql.SetRootPassword.entry.root_pwd.password',
                     variables=[Password('root_password')])
    def get_dump(self,requires):
        """Dump datas to file and return in a dict its filePath, the
        logPosition and the logFile"""
        root_user = "root"
        root_password = requires.get('mysqlRoot').variables.get('root_password').value
        con = MySQLdb.connect('localhost', root_user, root_password);
        cur = con.cursor()
        # First, we lock all tables
        cur.execute("FLUSH TABLES WITH READ LOCK;")
        # Second, we get log postion and log file
        cur.execute("SHOW MASTER STATUS;")
        rows = cur.fetchall()
        
        # Thirst, we dump datas
        filePath = "/tmp/dbdump.db"
        thread = ProcessThread("mysqldump", None, "test",
                               ["/usr/bin/mysqldump", 
                                "-u", "root", 
                                "--password=%s"%root_password,
                                "--all-databases", "--master-data",
                                "--result-file", filePath])
        if not thread.launch():
            logger.info("Error during mysqldump")
            raise Exception("Error during mysqldump")
        # mysqldump -u root -p --all-databases --master-data > /root/dbdump.db
        # Finally, we unlock tables
        cur.execute("UNLOCK TABLES;")
        
        return {'filePath': filePath, 'logFile': rows[0][0], 'logPostion': rows[0][1]}
#                     provide_ret=[VString('filePath'),VString('logFile'), VInt('logPostion')])
#        return "/tmp/dump_db.sql"
    

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
        Transition(SetRootPassword(),Configured()),
        Transition(Installed(), ResetRootPassword()),
        Transition(Configured()      ,Active()),
        #Slave Branch
        Transition(Configured()      ,ConfiguredAsSlave()),
        Transition(ConfiguredAsSlave(),ActiveAsSlave()),
        #Master Branch
        Transition(Configured()      ,ConfiguredAsMaster()),
        Transition(ConfiguredAsMaster(),ActiveAsMaster()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
