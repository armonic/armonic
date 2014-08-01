from sleekxmpp.xmlstream import ElementBase


class ActionProvider(ElementBase):
    """
    A stanza class for XML content of the form:
    <action xmlns="armonic:provider:action">
      <method>X</method>
      <param>X</param>
      <status>X</status>
    </action>
    """
    name = 'provider'
    namespace = 'armonic:provider:action'
    plugin_attrib = 'action'
    interfaces = set(('method', 'param', 'status'))
    sub_interfaces = interfaces
