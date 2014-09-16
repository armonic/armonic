from sleekxmpp.xmlstream import ElementBase


class ArmonicCall(ElementBase):
    """
    A stanza class for XML content of the form:
    <call xmlns="armonic">
      <deployment_id>X</deployment_id>
      <method>X</method>
      <params>X</params>
    </call>
    """
    name = 'call'
    namespace = 'armonic'
    plugin_attrib = 'call'
    interfaces = set(('method', 'params', 'deployment_id'))
    sub_interfaces = interfaces


class ArmonicStatus(ElementBase):
    """
    A stanza class for XML content of the form:
    <status xmlns="armonic">
      <deployment_id>X</deployment_id>
      <value>X</value>
    </status>
    """
    name = 'status'
    namespace = 'armonic'
    plugin_attrib = 'status'
    interfaces = set(('value', 'deployment_id'))
    sub_interfaces = interfaces


class ArmonicResult(ElementBase):
    """
    A stanza class for XML content of the form:
    <result xmlns="armonic">
      <deployment_id>X</deployment_id>
      <value>X</value>
    </result>
    """
    name = 'result'
    namespace = 'armonic'
    plugin_attrib = 'result'
    interfaces = set(('value', 'deployment_id'))
    sub_interfaces = interfaces


class ArmonicException(ElementBase):
    """
    A stanza class to send armonic exception over XMPP
    """
    name = 'exception'
    namespace = 'armonic'
    plugin_attrib = 'exception'
    interfaces = set(('code', 'message', 'deployment_id'))
    sub_interfaces = interfaces


class ArmonicLog(ElementBase):
    name = 'log'
    namespace = 'armonic'
    plugin_attrib = 'log'
    interfaces = set(('level', 'level_name', 'deployment_id'))
    sub_interfaces = interfaces
