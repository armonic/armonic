from mss.lifecycle import State, Transition, Lifecycle, provide, flags
from mss.require import Require, RequireExternal
from mss.variable import Port, Host, VString
import mss.state

import mss.configuration_augeas as augeas

import mss.common
import logging
logger=logging.getLogger(__name__)



class Options(augeas.Nodes):
    label = "option"
    cls = augeas.Node

class Client(augeas.Node):
    options = Options

class Clients(augeas.Nodes):
    label = "client"
    cls = Client

class Dir(augeas.Node):
    clients = Clients

class Dirs(augeas.Nodes):
    label = "dir"
    baseXpath = "/files/etc/exports"
    cls = Dir

class Configuration(augeas.Configuration):
    lenses={"Exports":["/etc/exports"]}
    dirs = Dirs

    def add_dir(self, directory, client_addr, options = []):
        dir = Dir()
        dir.value = directory
        self.dirs.append(dir)

        client = Client()
        client.value = client_addr
        dir.clients.append(client)
        option = augeas.Node()
        option.value = "ro"
        client.options.append(option)

    def rm_dir(self, directory, client):
        """To remove the dir of a client. If several client use this dir, all
        of them will be removed.
        """
        for d in self.dirs:
            if client != None:
                for c in d.clients:
                    if c.value == client:
                        d.rm()
                        return

class NotInstalled(State):pass
class Installed(mss.state.InstallPackagesUrpm):
    packages=["nfs-utils"]
class Configured(State):
    
    @Require("export", variables=[VString("dir"), Host("host")])
    @flags({'restart':True})
    def add_dir(self, requires):
        conf = Configuration()
        dir = requires.get("export").variables().get("dir").value
        host = requires.get("export").variables().get("host").value
    
        conf.add_dir(dir, host, ["rw", "sync"])
        conf.save()

class Active(mss.state.ActiveWithSystemd):
    services=["nfs-common", "nfs-server"]
    
    @provide()
    def get_dir(self, requires):
        return {"remotetarget" : "undefined/remote/target"}

class Nfs_server(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,Active()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
