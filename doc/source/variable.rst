.. _variable:

Variables
#########

Variables types
===============

Armonic provides base classes for defining your own variables. They all
inherit from :class:`armonic.variable.Variable`. No dict like variable is
provided since all variables have names.

.. autoclass:: armonic.variable.VString
    :members: pattern, pattern_error
    :noindex:

.. autoclass:: armonic.variable.VInt
    :members: min_val, max_val
    :noindex:

.. autoclass:: armonic.variable.VFloat
    :members: min_val, max_val
    :noindex:

.. autoclass:: armonic.variable.VBool
    :noindex:

.. autoclass:: armonic.variable.VList
    :noindex:

Predefined variables
====================

.. autoclass:: armonic.variable.Host
    :noindex:

.. autoclass:: armonic.variable.Hostname
    :noindex:

.. autoclass:: armonic.variable.Port
    :noindex:

Custom validation
=================

To specifiy a custom validation method subclass the variable type of your
choice and implement a validate function. If the validation fails you must
raise :class:`armonic.common.ValidationError` with an error message::

    from armonic.common import ValidationError
    from armonic.variable import VString

    class CustomVar(VString):

        def validate(self):
            if not self.value in ('foo', 'bar'):
                raise ValidationError('%s value should be foo or bar' % self.name)
            return True

Extra variable info
===================

If you wish to provide additional context to the variable you can define extra
arguments in the variable constructor::

    >>> from armonic.variable import VString
    >>> var = VString('username', label="Username", help="Type your username")
    >>> print var.to_primitive()
    {'default': None,
     'error': None,
     'extra': {'help': 'Type your username', 'label': 'Username'},
     'from_xpath': None,
     'name': 'username',
     'required': True,
     'type': 'str',
     'value': None,
     'xpath': None}

These extra infos can be used in clients that consume the :class:`armonic.lifecycle.Lifecycle` API.
