import logging
import time
import MySQLdb

from armonic import Provide
from armonic.lifecycle import State, Transition, Lifecycle, MetaState
from armonic.require import Require, RequireExternal, RequireLocal
from armonic.variable import VString, Port, Password, VInt, VUrl
from armonic.configuration_augeas import XpathNotInFile
from armonic.process import ProcessThread
from armonic.states import ActiveWithSystemV, ActiveWithSystemd, InstallPackagesUrpm, InstallPackagesApt, InitialState
import armonic.common

import configuration


logger = logging.getLogger(__name__)


class NotInstalled(InitialState):
    """Initial state"""
    pass


class Configured(State):
    """Configure mysql.
    - set port
    - disable skipnetworking"""
    @Require('conf', [Port("port", default=3306, label="Listen port", expert=True)])
    @Require('augeas', [VString("root", default="/", label="Augeas root path", expert=True)])
    def enter(self, requires):
        """ set mysql port """
        logger.info("%s.%-10s: edit my.cnf with requires %s" %
                    (self.lf_name, self.name, requires))
        self.config = configuration.Mysql(autoload=True,
                                          augeas_root=requires.augeas.variables().root.value)
        self.config.port.set(str(requires.conf.variables().port.value))
#        self.config.server_id.set("1")
        try:
            self.config.skipNetworking.rm()
        except XpathNotInFile:
            pass
        self.config.save()
        logger.event({"lifecycle": self.lf_name,
                      "event": "listening",
                      "port": requires.conf.variables().port.value})

    # @Provide(requires=Requires([Require([Port("port")])]),
    #          flags={'restart':True})
    def set_port(self):
        logger.info("%s.%-10s: provide call: set port with value %s" %
                    (self.lf_name, self.name, port))
        self.config.port.set(port)
        self.config.save()
        return True

    def get_port(self):
        return self.config.port.get()


class SetRootPassword(State):
    """Set initial Mysql root password"""

    @Require('auth', [Password("password", label="Initial root password for MySQL")])
    def enter(self, requires):
        pwd = requires.auth.variables().password.value  # password.value
        thread_mysqld = ProcessThread("mysql",
                                      None,
                                      "test",
                                      ["/bin/systemctl",
                                       "start",
                                       "mysqld.service"])
        if not thread_mysqld.launch():
            logger.info("Error at systemctl start mysqld.service (launch for mysqladmin)")
            raise Exception("Error at mysqld launching for mysqladmin")

        logger.debug("%s.%s set mysql root password ...",
                     self.lf_name,
                     self.name)
        thread_mysqld = ProcessThread("mysql", None, "test",
                                      ["/usr/bin/mysql", "-u", "root",
                                       "--password=%s" % pwd, "-e", "quit"])

        if thread_mysqld.launch():
            logger.info("%s.%s mysql root password already set to 'root'",
                        self.lf_name, self.name)
            return
        thread_mysqld = ProcessThread("mysqldadmin", None, "test",
                                      ["/usr/bin/mysqladmin", "password", pwd])

        if thread_mysqld.launch():
            logger.info("%s.%s mysql root password is '%s'",
                        self.lf_name, self.name, pwd)
            self.root_password = pwd
        else:
            logger.info("%s.%s mysql root password setting failed",
                        self.lf_name,
                        self.name)
            raise Exception("SetRootPassword failed with pwd %s" % pwd)

        thread_mysqld = ProcessThread("mysql", None, "test",
                                      ["/bin/systemctl",
                                       "stop",
                                       "mysqld.service"])
        if not thread_mysqld.launch():
            logger.info("Error at systemctl stop mysqld.service (launch for mysqladmin)")
            raise Exception("Error at mysqld launching for mysqladmin")


class ResetRootPassword(State):
    """To change mysql root password. It launches a
    mysqld without grant table and networking, sets a new root
    password and stop mysqld."""
    supported_os_type = [armonic.utils.OsTypeMBS()]

    @Require("auth", [Password("password", label="New root password for MySQL")])
    def enter(self, requires):
        logger.debug("%s.%s changing mysql root password ...",
                     self.lf_name,
                     self.name)
        logger.debug("%s.%s ensuring that mysqld is stopped ...",
                     self.lf_name,
                     self.name)
        thread = ProcessThread("mysql", None, "test",
                                      ["/bin/systemctl",
                                       "stop",
                                       "mysqld.service"])
        if not thread.launch():
            logger.info("Error at systemctl stop mysqld.service (launch for mysqladmin)")
            raise Exception("Error at mysqld launching for mysqladmin")

        thread_mysqld = ProcessThread("mysqld --skip-grant-tables --skip-networking",
                                      None,
                                      "test",
                                      ["/usr/sbin/mysqld",
                                       "--skip-grant-tables",
                                       "--skip-networking"],
                                      None,
                                      None,
                                      None,
                                      None)
        thread_mysqld.start()
        pwd_change = False
        for i in range(1, 6):
            logger.info("%s.%s changing password ... [attempt %s/5]",
                        self.lf_name,
                        self.name,
                        i)
            thread_mysql = ProcessThread("mysql -u root CHANGE_PWD to %s" % requires.auth.variables().password.value, None, "test",
                                         ["/usr/bin/mysql",
                                          "-u", "root",
                                          "-e", "use mysql;update user set password=PASSWORD('%s') where User='root';flush privileges;" % requires.auth.variables().password.value
                                          ])
            thread_mysql.start()
            thread_mysql.join()
            if thread_mysql.code == 0:
                pwd_change = True
                break
            logger.info("%s.%s changing password ... attempt %s FAIL",
                        self.lf_name,
                        self.name, i)
            time.sleep(1)
        thread_mysqld.stop()
        if pwd_change:
            logger.info("%s.%s mysql root password is now '%s'",
                        self.lf_name,
                        self.name,
                        requires.auth.variables().password.value)
        else:
            logger.info("%s.%s mysql root password changing fail",
                        self.lf_name,
                        self.name)


class ActiveOnDebian(ActiveWithSystemV):
    services = ["mysql"]
    service_name = "MySQL"


class ActiveOnMBS(ActiveWithSystemd):
    services = ["mysqld"]
    service_name = "MySQL"


class EnsureMysqlIsStopped(ActiveWithSystemd):
    services = ["mysqld"]
    service_name = "MySQL"

    def enter(self, requires):
        ActiveWithSystemd.leave(self)


class Active(MetaState):
    """Launch mysql server and provide some actions on databases."""
    implementations = [ActiveOnDebian, ActiveOnMBS]

    @Provide(tags=['internal'])
    @Require("auth", [VString('user'), VString('password')])
    def get_databases(self, requires):
        user = requires.get('auth').variables().get('user').value
        password = requires.get('auth').variables().get('password').value

        con = MySQLdb.connect('localhost',
                              user,
                              password)
        cur = con.cursor()
        cur.execute("show databases;")
        rows = cur.fetchall()
        return [d[0] for d in rows]

    @Provide(label='Create a MySQL database',
             tags=['database', 'mysql'])
    @Require('auth',
             variables=[Password(
                 'root_password',
                 from_xpath="Mysql/SetRootPassword/enter/auth/password")])
    @Require('data', [VString('user',
                              label="Database user name",
                              help="A user will be created for this database."),
                      VString('password',
                              label="Database user password"),
                      VString('database', label="Database name")])
    def add_database(self, requires):
        """Add a user and a database.
        User have permissions on all databases."""
        database = requires.get('data').variables().get('database').value
        user = requires.get('data').variables().get('user').value
        password = requires.get('data').variables().get('password').value
        mysql_root_pwd = requires.get('auth').variables().get('root_password').value

        if database in ['database']:
            raise Exception("database name can not be '%s'" % database)
        self.add_user('root', mysql_root_pwd, user, password)
        con = MySQLdb.connect('localhost', user, password)
        cur = con.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS %s;" % database)
        #rows = cur.fetchall()
        #return [d[0] for d in rows]
        return {}

    @Provide(label='Delete a MySQL database',
             tags=['database', 'mysql'])
    @Require('auth',
             variables=[Password(
                 'root_password',
                 from_xpath="Mysql/SetRootPassword/enter/auth/password")])
    @Require('data', [VString('database')])
    def rm_database(self, user, password, database):
        con = MySQLdb.connect('localhost', user,
                              password)
        cur = con.cursor()
        cur.execute("DROP DATABASE %s;" % database)
        return True

    #@Require('auth', [VString('user'), VString('password')])
    #@Require('user', [VString('username'), VString('userpassword')])
    def add_user(self, user, password, newUser, userPassword):
        con = MySQLdb.connect('localhost', user, password)
        cur = con.cursor()
        cmd = "GRANT ALL PRIVILEGES ON *.* TO '%s'@'%%' IDENTIFIED BY '%s' WITH GRANT OPTION;" % (newUser, userPassword)
        logger.debug("$mysql> %s" % cmd)
        cur.execute(cmd)
        cmd = "GRANT ALL PRIVILEGES ON *.* TO '%s'@'localhost' IDENTIFIED BY '%s' WITH GRANT OPTION;" % (newUser, userPassword)
        logger.debug("$mysql> %s" % cmd)
        cur.execute(cmd)
        logger.info("mysql user '%s' with password '%s' has been created." %
                    (newUser, userPassword))
        return True


class ConfiguredAsSlave(State):
    """Configure Mysql as a slave"""
    @Require('conf', [VInt('server_id', default=2)])
    @Require('augeas', [VString("root", default="/")])
    def enter(self, requires):
        self.config = configuration.Mysql(autoload=True,
                                          augeas_root=requires.augeas.variables().root.value)
        self.config.server_id.set(str(requires.conf.variables().server_id.value))
        self.config.log_bin.set("mysql-bin")
        self.config.save()


class ActiveAsSlave(MetaState):
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

    @Require('auth',
             variables=[Password(
                 'root_password',
                 from_xpath="Mysql/SetRootPassword/enter/auth/password")])
    @RequireExternal('dump', xpath='//Mysql//get_dump',
                     provide_ret=[VUrl('fileUrl'),
                                  VString('logFile'),
                                  VInt('logPosition')])
    @RequireExternal('auth', xpath='//Mysql//add_slave_auth',
                     provide_args=[VString('user', default='replication'),
                                   VString('password', default='repl_pwd')])
    def enter(self, requires):
        root_user = "root"
        root_password = requires.auth.variables().root_password.value
        # We are using VUrl object retrieve the dump.
        filePath = requires.dump.variables().fileUrl.get_file()
        logFile = requires.dump.variables().logFile.value
        logPosition = requires.dump.variables().logPosition.value
        slave_user = requires.auth.variables().user.value
        slave_password = requires.auth.variables().password.value
        master_host = requires.auth.variables().host.value

        logger.debug("%s %s %s", filePath, logFile, logPosition)
        thread = ProcessThread("mysql", None, "test",
                               ["/usr/bin/mysql",
                                "-u", "root",
                                "--password=%s" % root_password,
                                "-e", "stop slave ; source %s;" % filePath])
        if not thread.launch():
            logger.info("Error during mysql source dumpfile")
            raise Exception("Error during mysql source dumpfile")

        con = MySQLdb.connect('localhost', root_user, root_password)
        cur = con.cursor()
        cur.execute("slave stop;")
        cur.execute("CHANGE MASTER TO MASTER_HOST='%s', MASTER_USER='%s', MASTER_PASSWORD='%s', MASTER_LOG_FILE='%s', MASTER_LOG_POS=%s;" % (
                master_host,
                slave_user,
                slave_password,
                logFile,
                logPosition))
        cur.execute("slave start;")

    @Provide(tags=['internal'])
    @Require('auth',
             variables=[Password(
                 'root_password',
                 from_xpath="Mysql/SetRootPassword/enter/auth/password")])
    def slave_status(self, requires):
        root_user = "root"
        root_password = requires.auth.variables().root_password.value

        con = MySQLdb.connect('localhost', root_user, root_password)
        cur = con.cursor()
        cur.execute("SHOW SLAVE STATUS;")
        rows = cur.fetchall()
        return rows


class ConfiguredAsMaster(State):
    """Expose all databases to slave except mysql and informationshema."""
    @Require('conf', [VInt('server_id', default=1)])
    @Require('augeas', [VString("root", default="/")])
    def enter(self, requires):
        self.config = configuration.Mysql(autoload=True,
                                          augeas_root=requires.augeas.variables().root.value)
        self.config.server_id.set(str(requires.conf.variables().server_id.value))
        self.config.log_bin.set("mysql-bin")

        # Management of bin_log_ignore directive.
        # First we remove all of them
        for i in range(len(self.config.binlog_ignore_dbs) - 1, -1, -1):
            self.config.binlog_ignore_dbs[i].rm()
        # Second, we add mysql and informationschema
        tmp = configuration.BinLogIgnoreDb()
        tmp.value = "mysql"
        self.config.binlog_ignore_dbs.append(tmp)
        tmp = configuration.BinLogIgnoreDb()
        tmp.value = "informationschema"
        self.config.binlog_ignore_dbs.append(tmp)

        self.config.save()


class ActiveAsMaster(MetaState):
    implementations = [ActiveOnDebian, ActiveOnMBS]

    @Provide(tags=['internal'])
    @Require('slave_id', [VString('user', default='replication'),
                          VString('password', default='password')])
    @Require('auth',
             variables=[Password(
                 'root_password',
                 from_xpath="Mysql/SetRootPassword/enter/auth/password")])
    def add_slave_auth(self, requires):
        root_user = "root"
        root_password = requires.get('auth').variables().get('root_password').value
        slave_user = requires.get('slave_id').variables().get('user').value
        slave_password = requires.get('slave_id').variables().get('password').value

        con = MySQLdb.connect('localhost', root_user, root_password)
        cur = con.cursor()
        cur.execute("GRANT REPLICATION SLAVE ON *.* TO '%s'@'%%' IDENTIFIED BY '%s';" % (slave_user, slave_password))
        cur.execute("FLUSH PRIVILEGES;")

    @Provide(tags=['internal'])
    @Require('auth',
             variables=[Password(
                 'root_password',
                 from_xpath="Mysql/SetRootPassword/enter/auth/password")])
    @RequireLocal('share', "//Sharing//get_file_access",
                  provide_ret=[VString("filePath"), VString("fileUrl")])
    def get_dump(self, requires):
        """Dump datas to file and return in a dict its filePath, the
        logPosition and the logFile"""
        root_user = "root"
        root_password = requires.get('auth').variables().get('root_password').value
        con = MySQLdb.connect('localhost', root_user, root_password)
        cur = con.cursor()
        # First, we lock all tables
        cur.execute("FLUSH TABLES WITH READ LOCK;")
        # Second, we get log postion and log file
        cur.execute("SHOW MASTER STATUS;")
        rows = cur.fetchall()

        # Thirst, we dump datas
        filePath = "/tmp/dbdump.db"
        filePath = requires.get("share").variables[0].get('filePath').value
        fileUrl = requires.get("share").variables[0].get('fileUrl').value
        logger.debug("Dump will be saved in %s" % filePath)
        logger.debug("Dump can be accessed at %s" % fileUrl)
        thread = ProcessThread("mysqldump", None, "test",
                               ["/usr/bin/mysqldump",
                                "-u", "root",
                                "--password=%s" % root_password,
                                "--all-databases", "--master-data",
                                "--result-file", filePath])
        logger.info("Dump has been generated in %s" % filePath)
        if not thread.launch():
            logger.info("Error during mysqldump")
            raise Exception("Error during mysqldump")
        # mysqldump -u root -p --all-databases --master-data > /root/dbdump.db
        # Finally, we unlock tables
        cur.execute("UNLOCK TABLES;")

        return {'fileUrl': fileUrl,
                'logFile': rows[0][0],
                'logPosition': int(rows[0][1])}
#                     provide_ret=[VString('filePath'),VString('logFile'), VInt('logPostion')])
#        return "/tmp/dump_db.sql"

    @Provide(label='Create a database on a MySQL master',
             tags=['database', 'mysql', 'expert'])
    @Require('auth',
             variables=[Password(
                 'root_password',
                 from_xpath="Mysql/SetRootPassword/enter/auth/password")])
    @Require('data', [VString('user'),
                      VString('password'),
                      VString('database')])
    def add_database_master(self, requires):
        """Add a user and a database. User have permissions on all databases.
        """
        database = requires.get('data').variables().get('database').value
        user = requires.get('data').variables().get('user').value
        password = requires.get('data').variables().get('password').value
        mysql_root_pwd = requires.get('auth').variables().get('root_password').value

        if database in ['database']:
            raise Exception("database name can not be '%s'" % database)
        self.add_user('root', mysql_root_pwd, user, password)
        con = MySQLdb.connect('localhost', user, password)
        cur = con.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS %s;" % database)
        rows = cur.fetchall()
        return [d[0] for d in rows]

    def add_user(self, user, password, newUser, userPassword):
        con = MySQLdb.connect('localhost',
                              user,
                              password)

        cur = con.cursor()
        cmd = "GRANT ALL PRIVILEGES ON *.* TO '%s'@'%%' IDENTIFIED BY '%s' WITH GRANT OPTION;" % (newUser, userPassword)
        logger.debug("$mysql> %s" % cmd)
        cur.execute(cmd)
        cmd = "GRANT ALL PRIVILEGES ON *.* TO '%s'@'localhost' IDENTIFIED BY '%s' WITH GRANT OPTION;" % (newUser, userPassword)
        logger.debug("$mysql> %s" % cmd)
        cur.execute(cmd)
        logger.info("mysql user '%s' with password '%s' has been created." %
                    (newUser, userPassword))
        return True

    def cross(self, restart=False):
        pass


class InstalledOnMBS(InstallPackagesUrpm):
    packages = ["mysql-MariaDB"]


class InstalledOnDebian(InstallPackagesApt):
    packages = ["mysql-server"]


class Installed(armonic.lifecycle.MetaState):
    """Install mysql package (metastate)"""
    implementations = [InstalledOnMBS, InstalledOnDebian]


class Mysql(Lifecycle):
    """Mysql lifecycle permit to install and manage a mysql
    server. Several running mode are available:
    - use mysql as a single database server
    - use mysql as a slave database server
    - use mysql as a master database server
    """
    initial_state = NotInstalled()
    transitions = [
        Transition(NotInstalled(), Installed()),
        Transition(Installed(), SetRootPassword()),
        Transition(SetRootPassword(), Configured()),
        Transition(Installed(), ResetRootPassword()),
        Transition(Configured(), Active()),
        # Slave Branch
        Transition(Configured(), ConfiguredAsSlave()),
        Transition(ConfiguredAsSlave(), ActiveAsSlave()),
        # Master Branch
        Transition(Configured(), ConfiguredAsMaster()),
        Transition(ConfiguredAsMaster(), ActiveAsMaster()),
    ]
