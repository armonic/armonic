from mss.configuration_augeas import *

class Wordpress(Configuration):
    dbname=Child("Dbname",baseXpath='/files/var/www/wordpress/wp-config.php/define[. = "DB_NAME"]',label="value") 
    dbuser=Child("Dbuser",baseXpath='/files/var/www/wordpress/wp-config.php/define[. = "DB_USER"]',label="value") 
    dbpwd=Child("Dbpassword",baseXpath='/files/var/www/wordpress/wp-config.php/define[. = "DB_PASSWORD"]',label="value") 
    dbhost=Child("Dbhost",baseXpath='/files/var/www/wordpress/wp-config.php/define[. = "DB_HOST"]',label="value") 
    lenses={"Wordpress":["/var/www/wordpress/wp-config.php"]}

    def configure(self,dbName,dbUser,dbPwd,dbHost):
        self.dbname.set("'%s'"%dbName)
        self.dbuser.set("'%s'"%dbUser)
        self.dbpwd.set("'%s'"%dbPwd)
        self.dbhost.set("'%s'"%dbHost)
        self.save()
        
