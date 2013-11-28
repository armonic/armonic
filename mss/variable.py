from mss.common import ValidationError, IterContainer
import copy
import inspect
import re

from mss.xml_register import XmlRegister

class VariableNotSet(Exception):pass

class Variable(XmlRegister):
    """
    The type of a variable is validate (with _validate_type method)
    when the value is set. The value of a variable can be validate by
    hand with validate method. """ 

    type = 'variable'
    _value = None

    def __init__(self, name, default=None, required=True):
        # FIXME : this is a problem if we use two time this require:
        # First time, we specified a value
        # Second time, we want to use default value but it is not use, first value instead.
        self.name = name
        self.required = required
        self.default = default
        if default is not None:
            self.value = default

    def _xml_tag(self):
        return self.name
    def _xml_ressource_name(self):
        return "variable"


    def to_primitive(self):
        return {'name':self.name, 
#                'uri':self.uri, 
                'type':self.type, 'default': self.default}

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
        #self._value = self._validate_type(value)

    def fill(self, value):
        self.value = value

    def _validate_type(self, value):
        if value == None:
            raise VariableNotSet("value can't be None")
#        if not type(value) == int and len(value) == 0:
#            raise TypeError("value can't be empty")
        return value

    def _validate(self):
        if not self._value and self.required:
            raise ValidationError(variable_name=self.name , msg="%s is required" % self.name)

    def validate(self):
        """Override for custom validation.
        Raise ValidationError in case of error."""
        return True

    def has_default_value(self):
        print self.default
        return self.default != None

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "<%s(%s, value=%s, default=%s)>" % (self.__class__.__name__, self.name, self.value, self.default)


class VList(Variable):
    """
    :class:`VList` provide a list container for :class:`Variable` instances.

    Running the validation on :class:`VList` will recursively run the validation
    for all contained instances.
    """

    type = 'list'
    _inner_class = None
    _inner_inner_class = None

    def __init__(self, name, inner, default=None, required=True):
        if inspect.isclass(inner):
            self._inner_class = inner
        else:
            self._inner_class = inner.__class__
        if self._inner_class == VList:
            self._inner_inner_class = inner._inner_class
        Variable.__init__(self, name, default, required)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.fill(value)

    def fill(self, primitive):
        self._validate_type(primitive)
        values = []
        for key, value in enumerate(primitive):
            if not self._inner_inner_class:
                var = self._inner_class(key)
            else:
                var = self._inner_class(key, self._inner_inner_class)
            var.fill(value)
            values.append(var)
        if not len(value) == 0:
            self._value = values

    def _validate_type(self, value):
        Variable._validate_type(self, value)
        if not type(value) == list:
            raise TypeError("value must be a list")
        return value

    def _validate(self):
        Variable._validate(self)
        for value in self.value:
            value._validate()
        return self.validate()

    def __iter__(self):
        return iter(self.value)

    def __repr__(self):
        return "<%s(%s, value=%s, default=%s)>" % (self.__class__.__name__, self.name, self.value, self.default)


#class VDict(Variable):
    #type = 'dict'

    #def __getitem__(self, item):
        #return self.value[item]

    #def _validate_type(self, value):
        #Variable._validate_type(self, value)
        #if not type(value) == dict:
            #raise TypeError("value must be a dict")
        #return value

    #def _validate(self):
        #Variable._validate(self)
        #for key, value in self.value.items():
            #if isinstance(value, Variable):
                #value._validate()
        #return self.validate()


class VString(Variable):
    type = 'str'
    pattern = None
    pattern_error = None

    def _validate(self):
        Variable._validate(self)
        if self.pattern and not re.match(self.pattern, self.value):
            raise ValidationError(variable_name=self.name , msg=self.pattern_error)
        return self.validate()

    def _validate_type(self, value):
        Variable._validate_type(self, value)
        if not isinstance(value, basestring):
            raise TypeError("value must be a string")
        return value


class VInt(Variable):
    type = 'int'
    min_val = None
    max_val = None

    def _validate(self):
        Variable._validate(self)
        if self.min_val and self.value < self.min_val:
            raise ValidationError(variable_name=self.name , msg="%s value must be greater than %s" % (self.name, self.min_val))
        if self.max_val and self.value > self.max_val:
            raise ValidationError(variable_name=self.name , msg="%s value must be lower than %s" % (self.name, self.max_val))
        return self.validate()

    def _validate_type(self, value):
        Variable._validate_type(self, value)
        if not type(value) == int:
            raise TypeError("value must be an int (instead %s)"%type(value))
        return value

    def __int__(self):
        return self._value


class Hostname(VString):
    pattern = '^[a-z]+[a-z0-9]*$'
    pattern_error = 'Incorrect Hostname'


class Port(VInt):
    min_val = 0
    max_val = 65535

class Password(VString):
    pass


import urllib2
import tempfile
class VUrl(VString):
    def get_file(self):
        """
        :rtype: A local file name which contain uri object datas."""
        u = urilib2.urlopen(self.value)
        localFile = tempfile.NamedTemporaryFile(dir="/tmp", delete=False)
        localFile.write(u.read())
        localFile.close()
        return localFile.name
