import inspect
import re
import tempfile
import urllib2

from mss.common import ValidationError, ExtraInfoMixin
from mss.xml_register import XmlRegister


class Variable(XmlRegister, ExtraInfoMixin):
    """A object :py:class:`Variable` is a container for a value used by a
    provide. The minimal definition is just the name of the
    variable. It is possbile to specify a default value. Moreover, it
    is also possible to specify an xpath from where the value must be retreive.

    The type of a variable is validate (with _validate_type method)
    when the value is set. The value of a variable can be validate by
    hand with validate method.

    About from_xpath parameter. The goal it to reuse a value already provided.
    We can not directly use the value because at init time, it is not
    been filled yet. So, another way is to use a lamdba but in this case
    we must go to a state state per state if we want to know the value
    before using it. Indeed, if

    :param from_xpath: If this parameter is set, the client can reuse
    a value already used by the varaible targeted by this xpath.

    """

    type = None

    def __init__(self, name, default=None, required=True, from_xpath=None, **extra):
        ExtraInfoMixin.__init__(self, **extra)
        # FIXME : this is a problem if we use two time this require:
        # First time, we specified a value
        # Second time, we want to use default value but it is not use, first value instead.
        self.name = name
        self.required = required
        self.default = default
        self._value = default
        self.from_xpath = from_xpath
        self.error = None

    def _xml_tag(self):
        return self.name

    def _xml_ressource_name(self):
        return "variable"

    def to_primitive(self):
        primitive = ExtraInfoMixin.to_primitive(self)
        primitive.update(
            {'name': self.name,
             'xpath': self.get_xpath_relative(),
             'required': self.required,
             'type': self.type,
             'default': self.default,
             'value': self.value,
             'error': self.error,
             'from_xpath': self.from_xpath})
        return primitive

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = self._validate_type(value)

    def fill(self, value):
        self.value = value

    def _validate_type(self, value):
        self.error = None
        if value is None:
            self.error = "%s is required" % self.name
            raise ValidationError(variable_name=self.name,
                                  msg="%s value can't be None" % self.name)
        return value

    def _validate(self, value=None):
        """Validate value or self.value if value is not set.
        If values is specified, they are
        used to validate the require variables. Otherwise, you must
        already have fill it because filled values will be used.
        """
        self.error = None
        if not value:
            value = self.value

        if not value and self.required:
            self.error = "%s is required" % self.name
            raise ValidationError(variable_name=self.name,
                                  msg="%s is required" % self.name)

    def _custom_validation(self):
        try:
            self.validate()
        except ValidationError as e:
            self.error = e.msg
            raise
        return True

    def validate(self):
        """Override for custom validation.
        Raise ValidationError in case of error."""
        return True

    def has_error(self):
        return self.error is not None

    def has_default_value(self):
        return self.default is not None

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "<%s(%s, value=%s, default=%s)>" % (self.__class__.__name__,
                                                   self.name, self.value,
                                                   self.default)


class VList(Variable):
    """
    :class:`VList` provide a list container for :class:`Variable` instances.

    Running the validation on :class:`VList` will recursively run the
    validation for all contained instances.
    """

    type = 'list'
    _inner_class = None
    _inner_inner_class = None

    def __init__(self, name, inner, default=None, required=True, **extra):
        if inspect.isclass(inner):
            self._inner_class = inner
        else:
            self._inner_class = inner.__class__
        if self._inner_class == VList:
            self._inner_inner_class = inner._inner_class
        Variable.__init__(self, name, default, required, from_xpath=None, **extra)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.fill(value)

    def fill(self, primitive):
        self._validate_type(primitive)
        values = []
        for key, val in enumerate(primitive):
            if not self._inner_inner_class:
                var = self._inner_class(key)
            else:
                var = self._inner_class(key, self._inner_inner_class)
            var.fill(val)
            values.append(var)
        if values:
            self._value = values

    def _validate_type(self, value):
        Variable._validate_type(self, value)
        if not type(value) == list:
            raise ValidationError(msg="%s must be a list" % self.name, variable_name=self.name)
        return value

    def _validate(self):
        Variable._validate(self)
        for value in self.value:
            value._validate()
        return self._custom_validation()

    def __iter__(self):
        return iter(self.value)

    def __repr__(self):
        return "<%s(%s, value=%s, default=%s)>" % (self.__class__.__name__,
                                                   self.name,
                                                   self.value,
                                                   self.default)


class VString(Variable):
    """:param modifier: a format string with one string arg which will be the
    value."""
    type = 'str'
    pattern = None
    pattern_error = None

    def __init__(self, name, default=None, required=True, from_xpath=None, modifier="%s", **extra):
        Variable.__init__(self, name, default, required, from_xpath, **extra)
        self._modifier = modifier

    @property
    def value(self):
        if self._value is not None:
            return self._modifier % self._value
        else:
            return None

    @value.setter
    def value(self, value):
        self._value = self._validate_type(value)

    def _validate(self, value=None):
        if not value:
            value = self.value

        Variable._validate(self, value)
        if self.pattern and not re.match(self.pattern, value):
            self.error = self.pattern_error
            raise ValidationError(variable_name=self.name,
                                  msg=self.pattern_error)
        return self._custom_validation()

    def _validate_type(self, value):
        Variable._validate_type(self, value)
        return str(value)


class VInt(Variable):
    type = 'int'
    min_val = None
    max_val = None

    def _validate(self, value=None):
        if not value:
            value = self.value

        Variable._validate(self, value)
        if self.min_val is not None and value < self.min_val:
            raise ValidationError(variable_name=self.name,
                                  msg="%s value must be greater than %s" %
                                  (self.name, self.min_val))
        if self.max_val is not None and value > self.max_val:
            raise ValidationError(variable_name=self.name,
                                  msg="%s value must be lower than %s" %
                                  (self.name, self.max_val))
        return self._custom_validation()

    def _validate_type(self, value):
        Variable._validate_type(self, value)
        try:
            value = int(value)
        except ValueError:
            raise ValidationError(msg="%s must be an int" % self.name,
                                  variable_name=self.name)
        return value

    def __int__(self):
        return self.value


class VFloat(VInt):
    type = 'float'

    def _validate_type(self, value):
        Variable._validate_type(self, value)
        try:
            value = float(value)
        except ValueError:
            raise ValidationError(msg="%s must be a float" % self.name,
                                  variable_name=self.name)
        return value

    def __float__(self):
        return self.value


class VBool(Variable):
    type = 'bool'

    def _validate(self, value=None):
        Variable._validate(self, value)
        if not (value is True or value is False):
            raise ValidationError(variable_name=self.name,
                                  msg="%s value must be a boolen" % self.name)
        return True

    def _validate_type(self, value):
        Variable._validate_type(self, value)
        if value in ('True',):
            value = True
        if value in ('False',):
            value = False
        if not type(value) == bool:
            raise ValidationError(msg="%s must be a boolean" % self.name,
                                  variable_name=self.name)
        return value


class Host(VString):
    pattern = '^(\d{1,3}\.){3}\d{1,3}$|^[a-z]+[a-z0-9]*$'
    pattern_error = 'Incorrect host (pattern: %s)' % pattern


class Hostname(VString):
    pattern = '^[a-z]+[a-z0-9]*$'
    pattern_error = 'Incorrect Hostname (pattern: %s)' % pattern


class Port(VInt):
    min_val = 0
    max_val = 65535


class VUrl(VString):
    def get_file(self):
        """
        :rtype: A local file name which contain uri object datas."""
        u = urllib2.urlopen(self.value)
        localFile = tempfile.NamedTemporaryFile(dir="/tmp", delete=False)
        localFile.write(u.read())
        localFile.close()
        return localFile.name


class Password(VString):
    pass
