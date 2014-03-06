from mss.lifecycle import State, Transition, Lifecycle
from mss.require import Require, RequireExternal, VPort
import json
import logging
import os
import pprint


class NotInstalled(State):
    pass


class Installed(State):
    packages = []

    def enter(self, requires):
        """apt-get install wordpress"""
        return "urpmi %s" % self.packages

    def leave(self, requires):
        """apt-get remove wordpress"""
        pass

    @classmethod
    def setPackagesFromJson(cls, json):
        for i in json['packages']:
            for j in i['rpms']:
                cls.packages.append(j)


class ConfiguredAndActive(State):
    requires = []

    def enter(self, requires):
        """ set wordpress.php """
        return "Call setup.py %s" % requires

    @classmethod
    def setRequiresFromJson(cls, json):
        for i in json['config']:
            cls.requires.append(Celt(i['name']))


class Wrapper(Lifecycle):
    stack = []

    def __init__(self):
        self.push(self.initialState, {})


def readJson(path):
    try:
        with open(os.path.join(path, "desc.json")) as f:
            desc = json.load(f)
            return desc
    except (ValueError, IOError):
        logging.exception("Failed to load %s" % (path))


def BuildLifecycleFromJson(moduleName, modulePath):
    j = readJson(modulePath)
    pprint.pprint(j)
    n = type("NotInstalled", (NotInstalled,), {})
    i = type("Installed", (Installed,), {})
    i.setPackagesFromJson(j)

    c = type("ConfiguredAndActive", (ConfiguredAndActive,), {})
    c.setRequiresFromJson(j)

    m = type(moduleName, (Wrapper,), {
            'initialState':n,
            'transitions':[Transition(n, i),
                           Transition(i, c)]
            }
           )

    return m


m = BuildLifecycleFromJson("Owncloud", "./owncloud/")()
print "Build lifecycle class for Owncloud module (based on existing owncloud module)"
print "States are"
for s in m.getStates():
    print "\t", s
print "Requires to go to ConfiguredAndActive are"
print "\t", m.gotoRequires('ConfiguredAndActive')
dct = {'owncloud_adminUser': 'user',
       'owncloud_adminPass': 'password',
       'owncloud_dataPath': '/tmp/'}
print "Configure Owncloud with %s", dct
print m.goto('ConfiguredAndActive', dct)
