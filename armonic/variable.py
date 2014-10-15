import inspect
import re
import tempfile
import urllib2

from armonic.common import ValidationError, ExtraInfoMixin
from armonic.xml_register import XMLRessource


class Variable(XMLRessource, ExtraInfoMixin):
    """Describes a value used in a state provide.

    Only name is required.

    The type of a variable is validated (with :meth:`_validate_type()`)
    when the value is set. The value of a variable can be validated by
    hand with the :meth:`_validate()` method.

    :param name: variable name
    :type name: str
    :param default: default value
    :param required: required variable
    :type required: bool
    :param from_xpath: use the xpath value for this variable
    :type from_xpath: str
    :param **extra: extra variable fields
    """
    type = None

    def __init__(self, name, default=None, required=True, from_xpath=None, **extra):
        XMLRessource.__init__(self)
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

        # FIXME: This is only implemented by VString
        self._modifier = None

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
             'modifier': self._modifier,
             'from_xpath': self.from_xpath})
        return primitive

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def fill(self, value):
        self.value = value

    def base_validation(self, value):
        if self.required and value is None:
            self.error = "%s is required" % self.name
            raise ValidationError(variable_name=self.name,
                                  msg="%s is required" % self.name)
        elif self.required and value is None:
            # return early from validation since there is no
            # value and the variable is not required
            return

        try:
            length = len(value)
            if self.required and length == 0:
                raise ValidationError(variable_name=self.name,
                                      msg="%s is required" % self.name)
            elif self.required and length == 0:
                return
        except TypeError:
            # Can't calculate length
            pass

    def validation(self, value):
        """Override for custom validation
        """
        return True

    def validate(self, value=None):
        """Run the variable validation

        Validate value or self.value if value is not set.
        If values is specified, they are used to validate
        the require variables. Otherwise, you must already
        have fill it because filled values will be used.

        Set self.error when ValidationError is raised.

        :raises: ValidationError
        """
        self.error = None

        if value is None:
            value = self.value

        try:
            self.base_validation(value)
            self.validation(value)
        except ValidationError as e:
            self.error = e.msg
            raise
        return True

    def has_error(self):
        return self.error is not None

    def has_default_value(self):
        return self.default is not None

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "<%s(%s, xpath=%s, value=%s, default=%s)>" % (
            self.__class__.__name__, self.name, self._xpath, self.value, self.default)


class VList(Variable):
    """:class:`VList` provide a list container for :class:`Variable` instances.

    Running the validation on :class:`VList` will recursively run the
    validation for all contained instances.

    :param name: variable name
    :type name: str
    :param inner: the type of variable used in the list
    :type inner: all instances of :class:`Variable`
    :param default: default value
    :type default: list
    :param required: required variable
    :type required: bool
    :param **extra: extra variable fields
    """
    type = 'list'
    _inner_class = None
    _inner_inner_class = None

    def __init__(self, name, inner, default=None, required=True, from_xpath=None, **extra):
        if inspect.isclass(inner):
            self._inner_class = inner
        else:
            self._inner_class = inner.__class__
        if self._inner_class == VList:
            self._inner_inner_class = inner._inner_class

        Variable.__init__(self, name, self._fill(default), required, from_xpath=from_xpath, **extra)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.fill(value)

    @property
    def raw_value(self):
        return self._raw(self.value)

    @property
    def raw_default(self):
        return self._raw(self.default)

    def _raw(self, selector):
        values = []

        # If it is not a list, we return the current value to help
        # user to know what is wrong
        if not type(selector) is list:
            return selector

        if not selector:
            return values
        for variable in selector:
            # List of lists
            if self._inner_inner_class:
                values.append(variable.raw_value)
            else:
                values.append(variable.value)
        return values

    def to_primitive(self):
        primitive = Variable.to_primitive(self)
        primitive["value"] = self.raw_value
        primitive["default"] = self.raw_default
        return primitive

    def fill(self, primitive):
        self._value = self._fill(primitive)

    def _fill(self, primitive):
        values = []

        # If the primitive is not a list, we fill the value with the
        # primitive. The validation will detect an error and raise an
        # exception. We have to do a special thing because some types
        # (such as a str) can be enumerate...
        if not type(primitive) == list:
            return primitive

        for key, val in enumerate(primitive):
            if not self._inner_inner_class:
                var = self._inner_class(key)
            else:
                var = self._inner_class(key, self._inner_inner_class)
            var.fill(val)
            values.append(var)
        if values:
            return values
        return values

    def base_validation(self, value):
        Variable.base_validation(self, value)
        if not type(value) == list:
            msg = "%s must be a list (instead of %s)" % (self.name, type(value))
            raise ValidationError(msg=msg, variable_name=self.name)
        for key, val in enumerate(value):
            if not isinstance(val, Variable):
                if not self._inner_inner_class:
                    value[key] = self._inner_class(key)
                else:
                    value[key] = self._inner_class(key, self._inner_inner_class)
                value[key].validate(val)
            else:
                value[key].validate()

    def __iter__(self):
        return iter(self.value)

    def __repr__(self):
        return "<%s(%s, value=%s, default=%s)>" % (self.__class__.__name__,
                                                   self.name,
                                                   self.value,
                                                   self.default)


class VString(Variable):
    """Variable of type string
    """
    type = 'str'
    pattern = None
    """Validate the value again a regexp"""
    pattern_error = None
    """Error message if the value doesn't match the regexp"""

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
        self._value = value

    def base_validation(self, value):
        Variable.base_validation(self, value)
        if self.pattern and not re.match(self.pattern, value):
            msg = "%s (current value is %s)" % (self.pattern_error, value)
            raise ValidationError(variable_name=self.name,
                                  msg=msg)


class VInt(Variable):
    """Variable of type int."""
    type = 'int'
    min_val = None
    """Minimum value"""
    max_val = None
    """Maximum value"""

    def base_validation(self, value):
        Variable.base_validation(self, value)
        try:
            value = int(value)
        except ValueError:
            raise ValidationError(msg="%s must be an int" % self.name,
                                  variable_name=self.name)
        if self.min_val is not None and value < self.min_val:
            raise ValidationError(variable_name=self.name,
                                  msg="%s value must be greater than %s" %
                                  (self.name, self.min_val))
        if self.max_val is not None and value > self.max_val:
            raise ValidationError(variable_name=self.name,
                                  msg="%s value must be lower than %s" %
                                  (self.name, self.max_val))

    def __int__(self):
        return self.value


class VFloat(VInt):
    """Variable of type float."""
    type = 'float'

    def base_validation(self, value):
        VInt.base_validation(self, value)
        try:
            value = float(value)
        except ValueError:
            raise ValidationError(msg="%s must be a float" % self.name,
                                  variable_name=self.name)

    def __float__(self):
        return self.value


class VBool(Variable):
    """Variable of type boolean."""
    type = 'bool'

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value in ('True', 'y', 'Y'):
            value = True
        if value in ('False', 'n', 'N'):
            value = False
        self._value = value

    def base_validation(self, value):
        Variable.base_validation(self, value)
        if value in ('True', 'y', 'Y'):
            value = True
        if value in ('False', 'n', 'N'):
            value = False
        if not type(value) == bool:
            raise ValidationError(variable_name=self.name,
                                  msg="%s value must be a boolen" % self.name)


class ArmonicFirstInstance(VBool):
    """This variable must be used to specify if an instance is the first
    one or not. This will be used by the lifecycle to realize some special
    initial stuff.

    This special variable type allows smartlib to specify first
    instance and other. This is useful for replicated instances such
    as Galera.
    """
    type = 'armonic_first_instance'


class ArmonicHost(VString):
    """Internal variable that contains the host of an RequireExternal
    """
    type = 'armonic_host'
    pattern = '^(\d{1,3}\.){3}\d{1,3}$|^[a-z]+[a-z0-9]*$'
    pattern_error = 'Incorrect host (pattern: %s)' % pattern


class ArmonicHosts(VList):
    """Internal variable to store the list of hosts
    when deploying multiple instances."""
    type = 'armonic_hosts'

    def __init__(self, name, default=None, required=True, from_xpath=None, **extra):
        VList.__init__(self, name, ArmonicHost,
                       default=default, required=required, from_xpath=from_xpath, **extra)


class Host(VString):
    """Variable for hosts.

    Validate that the value is an IP or a hostname
    """
    type = "host"
    pattern = '^(\d{1,3}\.){3}\d{1,3}$|^[a-z]+[a-z0-9]*$'
    pattern_error = 'Incorrect host (pattern: %s)' % pattern


class ArmonicThisHost(Host):
    """This variable describe the host where the current provide is
    executed.
    """
    type = 'armonic_this_host'


class Hostname(VString):
    """Variable for hostnames.

    Validate that the value is a hostname
    """
    pattern = '^[a-z]+[a-z0-9]*$'
    pattern_error = 'Incorrect Hostname (pattern: %s)' % pattern


class Port(VInt):
    """Variable for port numbers.

    Validate that the value is between 0 and 65535
    """
    min_val = 0
    max_val = 65535


class VUrl(VString):
    """Open an url, download the remote object to a local file and return
    the local path of this object.
    
    This should be renamed.
    """
    def get_file(self):
        """
        :rtype: A local file name which contain uri object datas."""
        u = urllib2.urlopen(self.value)
        localFile = tempfile.NamedTemporaryFile(dir="/tmp", delete=False)
        localFile.write(u.read())
        localFile.close()
        return localFile.name


class Url(VString):
    pass


class Password(VString):
    min_chars = 6

    def validation(self, value):
        if len(value) < self.min_chars:
            raise ValidationError(
                variable_name=self.name,
                msg='Password too short. %s chars minimum.' % self.min_chars
            )
