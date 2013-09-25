from mss.common import ValidationError, IterContainer

import inspect
import re


class Variable(object):
    type = 'variable'
    _value = None

    def __init__(self, name, default=None, label=None, help=None, required=True):
        self.name = name
        self.label = label if label else name
        self.help = help
        self.required = required
        self.default=default
        if default is not None:
            self.value = default

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = self._validate_type(value)

    def fill(self, value):
        self.value = value

    def _validate_type(self, value):
        if value == None:
            raise TypeError("value can't be None")
#        if not type(value) == int and len(value) == 0:
#            raise TypeError("value can't be empty")
        return value

    def _validate(self):
        if not self._value and self.required:
            raise ValidationError("%s is required" % self.name)

    def validate(self):
        """Override for custom validation.
        Raise ValidationError in case of error."""
        return True

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "<%s(%s, value=%s)" % (self.__class__.__name__, self.name, self.value)


class VList(Variable):
    type = 'list'
    _inner_class = None
    _inner_inner_class = None

    def __init__(self, name, inner, default=None, label=None, help=None, required=True):
        if inspect.isclass(inner):
            self._inner_class = inner
        else:
            self._inner_class = inner.__class__
        if self._inner_class == VList:
            self._inner_inner_class = inner._inner_class
        Variable.__init__(self, name, default, label, help, required)

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
        return "<%s(%s, value=%s)" % (self.__class__.__name__, self.name, self.value)


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
            raise ValidationError(self.pattern_error)
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
            raise ValidationError("%s value must be greater than %s" % (self.name, self.min_val))
        if self.max_val and self.value > self.max_val:
            raise ValidationError("%s value must be lower than %s" % (self.name, self.max_val))
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
