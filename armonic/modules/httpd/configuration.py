""" Features are
- configure (set/get) listen port
- list virtual hosts
- configure virtual hosts
- add a virtual hosts.

This mapping is complicated because we want to map configuration elt by name in
a virtual host directory. In augeas lenses, they are addressed by
index. We then have to map this array with the name of option.

To do this, we have to use different xpath for reading and for creation.
This is done with xpath_create
Moreover, we have to control the children order
This is done with children method.
"""

from armonic.configuration_augeas import *


class Arg(Node):
    label = "arg"


class Path(Arg):
    pass


class Args(Nodes):
    label = "arg"


class Directive(Node):
    label = "directive"

    def xpath_access(self):
        return "%s[. = '%s']" % (self.label, self.value)

    def xpath_create(self):
        """We need to specify how to create this directive. Because a
        directory has an array of directive, we have to associate
        index to directive value."""
        if self.value == 'AllowOverride':
            index = 1
        elif self.value == 'Options':
            index = 2
        elif self.value == 'Order':
            index = 3
        return "%s[%s]" % (self.label, index)


class AllowOverride(Directive):
    value = "AllowOverride"
    arg = Arg


class Order(Directive):
    value = "Order"
    arg1 = Child(Arg, label='arg[1]')
    arg2 = Child(Arg, label='arg[2]')


class Options(Directive):
    value = "Options"
    args = Args


class Directory(Node):
    label = "Directory"
    path = Path
    allowOverride = AllowOverride
    option = Options
    order = Order

    def children(self):
        return [self.path,
                self.allowOverride,
                self.option,
                self.order]


class Directories(Nodes):
    label = "Directory"
    cls = Directory
    baseXpath = "/files/etc/apache2/sites-available/default/VirtualHost[arg = '*:80']"

# class VirtualHost(Node):


class DefaultVirtualHost(Nodes):
    label = "VirtualHost"
#   cls=VirtualHost
    baseXpath = "/files/etc/apache2/sites-available/default/"


class Apache(Configuration):
#    directories=Directories
    port = Child("port",
                 baseXpath="//*[label() != IfModule[*]]/directive[. = 'Listen']",
                 label="arg")
    portVhost = Child("portVhost",
                      baseXpath="/files/etc/apache2/sites-available/default/VirtualHost",
                      label="arg")
#    documentRoot=Child("documentRoot",baseXpath="/files/etc/apache2/sites-available/default/VirtualHost/directive[. = 'DocumentRoot']",label="arg") # DEBIAN ONLY
    documentRoot = Child("documentRoot",
                         baseXpath="//*[label() != 'default-ssl']/*/*/directive[. = 'DocumentRoot']",
                         label="arg")

    lenses = {"Httpd": ["/etc/apache2/ports.conf",
                        "/etc/apache2/apache2.conf",
                        "/etc/apache2/sites-available/*",
                        "/etc/httpd/conf/httpd.conf"]}

    # def addDirectory(self,path):
    #     """Add a directory if it doesn't exist"""
    #     if path not in [d.path.value for d in self.directories]:
    #         new=Directory()
    #         new.path.value=path
    #         self.directories.append(new)

    def setPort(self, port):
#        print "port %s" , port
        self.port.set(port)
#        self.portVhost.set("*:%s"%port) # DEBIAN ONLY FIXME
        self.save()
