from mss.configuration_augeas import *


class Mysql(Configuration):
    port=Child("Port",baseXpath='//target[. = "mysqld"]/',label="port")
    skipNetworking=Child("SkipNetworking",baseXpath='//my.cnf/target[*]/',label="skip-networking")
    lenses={"MySQL":["/etc/mysql/my.cnf","/etc/my.cnf"]}
