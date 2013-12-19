from mss.lifecycle import State, Transition, Lifecycle, provide, flags
from mss.require import Require, RequireExternal
from mss.variable import Port, Host, VString
import mss.state
import mss.utils
import os
import os.path

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
        """This add a new dir in /etc/exports. It tries to update the dir if
        it already exists."""
        dir = None
        for d in self.dirs:
            if d.value == directory:
                dir = d
        if dir is None:
            dir = Dir()
            dir.value = directory
            self.dirs.append(dir)
            
        client = None
        for c in dir.clients:
            if c.value == client_addr:
                client = c
        if client is None:
            client = Client()
            client.value = client_addr
            dir.clients.append(client)
        
        for o in options:
            if o not in [ tmp.value for tmp in client.options]:
                option = augeas.Node()
                option.value = o
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
    
    @Require("export", variables=[VString("name"), Host("client")])
    @flags({'restart':True})
    def get_dir(self, requires):
        conf = Configuration()
        name = requires.get("export").variables().get("name").value
        client = requires.get("export").variables().get("client").value
        
        dir = "/var/mss/nfs/%s" % name
        if not os.path.exists(dir):
            logger.debug("Directory %s has been created" % dir)
            os.makedirs(dir)
        conf.add_dir(dir, client, ["rw", "sync", "no_root_squash"])
        conf.save()
        remotetarget = "%s:%s" % (mss.utils.get_ip(), dir)
        return {'remotetarget':remotetarget}

class Active(mss.state.ActiveWithSystemd):
    services=["nfs-common", "nfs-server"]
    
    # This should be useless because we shoyuld call it in state
    # Configuration and the n call start provide. But Zephyrus is
    # currently not able to call two provide...
    @Require("export", variables=[VString("name"), Host("client")])
    @flags({'restart':True})
    def get_dir(self, requires):
        conf = Configuration()
        name = requires.get("export").variables().get("name").value
        client = requires.get("export").variables().get("client").value
        
        dir = "/var/mss/nfs/%s" % name
        if not os.path.exists(dir):
            logger.debug("Directory %s has been created" % dir)
            os.makedirs(dir)
        conf.add_dir(dir, client, ["rw", "sync", "no_root_squash"])
        conf.save()
        remotetarget = "%s:%s" % (mss.utils.get_ip(), dir)
        return {'remotetarget':remotetarget}


class Nfs_server(Lifecycle):
    transitions=[
        Transition(NotInstalled()    ,Installed()),
        Transition(Installed()    ,Configured()),
        Transition(Configured()      ,Active()),
        ]

    def __init__(self):
        self.init(NotInstalled(),{})
