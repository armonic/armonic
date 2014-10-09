"""This module defines some utils used by armonic."""

import re
import platform
import netifaces
from IPy import IP

import logging
logger = logging.getLogger(__name__)


class OsType(object):
    """Represent an Linux distribution type. :py:meth:`__eq__` is
    used to know if a state has the current linux distribution in its
    supported_os_type.
    """
    def __init__(self, name, release=None):
        self.name = name
        self.release = release

    def __eq__(self, other):
        if isinstance(other, OsTypeAll):
            return True
        else:
            return (self.name == other.name and
                    (self.release is None or
                     other.release is None or
                     self.release == other.release))

    def __repr__(self):
        if self.release is None:
            return "<OsType(%s - all)>" % (self.name)
        else:
            return "<OsType(%s - %s)>" % (self.name, self.release)

    def to_primitive(self):
        return {'name': self.name, 'release': self.release}


class OsTypeAll(OsType):
    """Use this class to specify that a state supports all os type. It
    is equal to any OsType* object.
    """
    def __init__(self):
        self.name = "all"
        self.release = "all"

    def __eq__(self, other):
        if isinstance(other, OsType) or isinstance(other, OsTypeAll):
            return True
        return False

    def __repr__(self):
        return "<OsTypeAll>"


class OsTypeMBS(OsType):
    def __init__(self):
        OsType.__init__(self, "Mandriva Business Server")


class OsTypeUbuntu(OsType):
    def __init__(self):
        OsType.__init__(self, "ubuntu")


class OsTypeDebian(OsType):
    def __init__(self):
        OsType.__init__(self, "debian")


class OsTypeArch(OsType):
    def __init__(self):
        OsType.__init__(self, "arch")


class OsTypeDebianWheezy(OsTypeDebian):
    def __init__(self):
        self.name = 'debian'
        self.release = 'wheezy/sid'


def find_distribution():
    distname, version, id = platform.linux_distribution()
    # Try to find unkwown distribs
    if not distname and not version:
        distname, version, id = platform.linux_distribution(supported_dists=('arch',))
    if not distname and not version:
        raise Exception('OS info not found. Aborting.')
    os = OsType(distname, version)
    logger.debug("Running on %s" % os)
    return os

OS_TYPE = find_distribution()


def ethernet_ifs():
    ifs = []
    for interface in netifaces.interfaces():
        # support new ethernet device naming style
        # http://www.freedesktop.org/wiki/Software/systemd/PredictableNetworkInterfaceNames/
        if interface.startswith(("eth", "en")):
            if_detail = netifaces.ifaddresses(interface)
            # check if interface is configured
            if netifaces.AF_INET in if_detail:
                addr = if_detail[netifaces.AF_INET][0]['addr']
                netmask = if_detail[netifaces.AF_INET][0]['netmask']
                network = IP(addr).make_net(netmask).strNormal(0)
                ifs.append([interface, addr, network, netmask])

    return ifs


def get_first_ip():
    try:
        return ethernet_ifs()[0][1]
    except IndexError:
        return '127.0.0.1'


def get_subclasses(c):
    subclasses = c.__subclasses__()
    for d in list(subclasses):
        subclasses.extend(get_subclasses(d))
    return subclasses


# From http://stackoverflow.com/questions/13506033/filtering-out-ansi-escape-sequences
def strip_ansi_codes(s):
    """
    >>> import blessings
    >>> term = blessings.Terminal()
    >>> foo = 'hidden'+term.clear_bol+'foo'+term.color(5)+'bar'+term.color(255)+'baz'
    >>> repr(strip_ansi_codes(foo))
    u'hiddenfoobarbaz'
    """
    return re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', s)


class Singleton(type):

    def __init__(cls, name, bases, dict):
        super(Singleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls, *args, **kw):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kw)
        return cls.instance


class DoesNotExist(Exception):
    pass


class IterContainer(list):
    """
    Simple object container

    Is an iterator to loop over objects:
        objects = IterContainer(*objects)
        for object in objects:
            print object.name, object.value

    And provide easy way to retrieve objects
    that have a name attribute:

        objects = IterContainer(*objects)
        object = objects.object_name
        print object.name, object.value
        object = objects.get("object_name")
        print object.name, object.value

    """
    def __init__(self, *args):
        super(IterContainer, self).__init__([arg for arg in args])
        self._register_args(*args)

    def _register_args(self, *args):
        for arg in args:
            if hasattr(arg, 'name'):
                setattr(self, arg.name, arg)

    def get(self, attr):
        if hasattr(self, attr):
            return getattr(self, attr)
        raise DoesNotExist("%s does not exist" % attr)

    def append(self, arg):
        super(IterContainer, self).append(arg)
        self._register_args(arg)
