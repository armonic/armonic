"""This module defines some utils used by mss."""

import platform

class OsType(object):
    """Represent an linux distribution type"""
    def __init__(self,name,release):
        self.name = name
        self.release = release

    def __eq__(self,other):
        if isinstance(other,OsTypeAll):
            return True
        else:
            return (self.name == other.name and
                    self.release == other.release)

    def __repr__(self):
        return "%s - %s" % (self.name,self.release)

class OsTypeAll():
    """Use this class to specify that a state supports all os type. It
    is equal to any OsType* object."""
    def __init__(self):
        self.name = "all"
        self.release = "all"
    def __eq__(self,other):
        if isinstance(other,OsType) or isinstance(other,OsTypeAll):
            return True
        return False

class OsTypeMBS1(OsType):
    def __init__(self):
        self.name = "Mandriva Business Server"
        self.release = "1"

class OsTypeDebianWheezy(OsType):
    def __init__(self):
        self.name = 'debian'
        self.release = 'wheezy/sid'


def find_distribution():
    t=platform.linux_distribution()
    return OsType(t[0],t[1])

os_type=find_distribution()
