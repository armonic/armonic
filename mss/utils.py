"""This module defines some utils used by mss."""

import platform
import netifaces
from IPy import IP

class OsType(object):
    """Represent an linux distribution type.  :py:meth:`__eq__` is
    used to know if a state has the current linux distribution in his
    supported_os_type.
    """
    def __init__(self,name,release=None):
        self.name = name
        self.release = release

    def __eq__(self,other):
        if isinstance(other,OsTypeAll):
            return True
        else:
            return (self.name == other.name and
                    (self.release == None or 
                     other.release == None or
                     self.release == other.release))

    def __repr__(self):
        if self.release == None:
            return "%s - all" % (self.name)
        else :
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

    def __repr__(self):
        return "all"


class OsTypeMBS1(OsType):
    def __init__(self):
        self.name = "Mandriva Business Server"
        self.release = "1"

class OsTypeDebian(OsType):
    def __init__(self):
        OsType.__init__(self,"debian")

class OsTypeDebianWheezy(OsTypeDebian):
    def __init__(self):
        self.name = 'debian'
        self.release = 'wheezy/sid'
        

def find_distribution():
    t=platform.linux_distribution()
    return OsType(t[0],t[1])

os_type=find_distribution()


def ethernet_ifs():
    ifs = []
    for interface in netifaces.interfaces():
        if interface.startswith("eth"):
            if_detail = netifaces.ifaddresses(interface)
            # check if interface is configured
            if netifaces.AF_INET in if_detail:
                addr = if_detail[netifaces.AF_INET][0]['addr']
                netmask = if_detail[netifaces.AF_INET][0]['netmask']
                network = IP(addr).make_net(netmask).strNormal(0)
                ifs.append([interface, addr, network, netmask])

    return ifs
