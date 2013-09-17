""" This module contains requires classes.

Requires are used to apply a state. The minimal requires definition
MUST contains a method :py:meth:`Require.validate`.

The method :py:meth:`Require.validate` takes as input a list a
dict. Each dict contain a variable name and its value ::

    [{'variable1' : 'value1' , 'variable2' : 'value2' , ...},
     {'variable1' : 'value3' , 'variable2' : 'value4' , ...},
     ...
    ]

"""

class MissingRequire(Exception):
    def __init__(self, variable="", state=None):
        self.variable = variable
        self.state = state

    def __str__(self):
        return "Require '%s' of state '%s' is missing" % (self.variable, self.state)

    def __repr__(self):
        return "Missing require %s" % self.variable


class Variable(object):
    type = 'undefined'

    def __init__(self, name, default=None):
        self.name = name
        self.default = default

    def __repr__(self):
        if self.default:
            return "name:%s,type:%s,default:%s" % (self.name, self.type, self.default)
        else:
            return "name:%s,type:%s" % (self.name, self.type)

    def to_primitive(self):
        if self.default:
            return {'name': self.name, 'type': self.type,
                    'default': self.default}
        else:
            return {'name': self.name, 'type': self.type}

    @property
    def has_default_value(self):
        return self.default != None


class VString(Variable):
    type = 'str'
class VPassword(Variable):
    type = 'password'
class VHost(Variable):
    type = 'host'
class VPort(Variable):
    type = 'port'


class Require(object):
    """A require to specify a configuration variable of a state.
    :param args: A array of variables
    :param name: A optionnal name for this require
    """
    def __init__(self, args, name=None):
        """
        :param args: A variable definition
        :param name: A optionnal name for this require
        """
        if name:
            self.name = name
        elif args != []:
            self.name = args[0].name
        else:
            self.name = 'undefined'
        self.args = args
        self.type = "simple"

    def __repr__(self):
        return "type:%s,name:%s,args:%s" % (self.type, self.name, self.args)

    def validate(self, values):
        """Return a dict containing this args or the defaultValue"""
        tacc = []
        if values == []:
            values = [{}]
        for vDct in values:
            acc = {}
            for v in self.args:
                if v.name in vDct:
                    acc.update({v.name: vDct[v.name]})
                elif v.default:
                    acc.update({v.name: v.default})
                else:
                    raise MissingRequire(v.name)
            tacc.append(acc)
        return tacc

    def to_primitive(self):
        return {"name": self.name, "args": [a.to_primitive() for a in self.args],
                "type": "simple"}

    def generate_args(self, dct={}):
        """Return a tuple. First element of tuple a dict of
        argName:value where value is the default value. Second is a
        list of argName without default value.

        :param dct: To specify a argName and its value.
        """
        ret = ({}, [])
        for a in self.args:
            if a.name in dct:
                ret[0].update({a.name: dct[a.name]})
            elif a.has_default_value:
                ret[0].update({a.name: a.default})
            else:
                ret[1].append(a.name)
        return ret


class RequireLocal(Require):
    """To specify a configuration variable which can be provided
    by a *provide* of a local module."""
    def __init__(self, module, provide, args, name=None):
        self.module = module
        self.provide = provide
        self.args = args
        self.type = "local"
        self.name = name if name else "%s.%s" % (self.module, self.provide)

    def to_primitive(self):
        return {"name": self.name,
                "type": self.type,
                "module": self.module,
                "provide": self.provide,
                "args": [v.to_primitive() for v in self.args]}

    def __repr__(self):
        return "type:%s,name:%s,module:%s,provide:%s,args:%s" % (self.type, self.name, self.module,
                                                                 self.provide, self.args)

    def generate_provide_args(self, dct={}):
        return self.generate_args(dct)


class RequireExternal(RequireLocal):
    """To specify a configuration variable which can be provided
    by a *provide* of a external module.
    A 'host' variable is automatically added to the args list.
    It MUST be provided.
    """
    def __init__(self, module, provide, args, name=None):
        RequireLocal.__init__(self, module, provide, args, name)
        args.append(VHost('host'))
        self.type = "external"

    def generate_provide_args(self, dct={}):
        ret = ({},[])
        for a in self.args:
            if a.name == 'host':
                continue
            if a.name in dct:
                ret[0].update({a.name: dct[a.name]})
            elif a.has_default_value:
                ret[0].update({a.name: a.default})
            else:
                ret[1].append(a.name)
        return ret
