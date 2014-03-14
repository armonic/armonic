from armonic.configuration_augeas import *


class BinLogIgnoreDb(Node):
    label = "binlog-ignore-db"


class BinLogIgnoreDbs(Nodes):
    baseXpath = '//target[. = "mysqld"]'
    label = "binlog-ignore-db"
    cls = BinLogIgnoreDb


class Mysql(Configuration):
    port = Child("Port", baseXpath='//target[. = "mysqld"]', label="port")
    log_bin = Child("LogBin",
                    baseXpath='//target[. = "mysqld"]',
                    label="log-bin")
    server_id = Child("ServerId",
                      baseXpath='//target[. = "mysqld"]',
                      label="server-id")
    binlog_ignore_dbs = BinLogIgnoreDbs
    skipNetworking = Child("SkipNetworking",
                           baseXpath='//my.cnf/target[*]',
                           label="skip-networking")
    lenses = {"MySQL": ["/etc/mysql/my.cnf", "/etc/my.cnf"]}
