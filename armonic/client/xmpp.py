from __future__ import absolute_import

import sys
import json
import logging

from sleekxmpp import ClientXMPP, Iq, Message
from sleekxmpp.exceptions import IqError
from sleekxmpp.xmlstream import ElementBase, register_stanza_plugin
if sys.version_info < (3, 0):
    from sleekxmpp.util.misc_ops import setdefaultencoding
    setdefaultencoding('utf8')
else:
    raw_input = input


logger = logging.getLogger(__name__)


class XMPPError(Exception):
    pass


class ArmonicCall(ElementBase):
    """
    A stanza class for XML content of the form:
    <call xmlns="armonic">
      <deployment_id>X</deployment_id>
      <method>X</method>
      <params>X</params>
      <status>X</status>
    </call>
    """
    name = 'call'
    namespace = 'armonic'
    plugin_attrib = 'call'
    interfaces = set(('method', 'params', 'status', 'deployment_id'))
    sub_interfaces = interfaces


class ArmonicError(ElementBase):
    """
    A stanza class to send armonic exception over XMPP
    """
    name = 'exception'
    namespace = 'armonic'
    plugin_attrib = 'exception'
    interfaces = set(('code', 'message'))
    sub_interfaces = interfaces


class XMPPClientBase(ClientXMPP):
    base_plugins = [
        ('xep_0030',),  # Disco
        ('xep_0004',),  # Dataforms
        ('xep_0045',),  # MUC
        ('xep_0199', {'keepalive': True, 'frequency': 15})
    ]
    """Always loaded plugins"""

    def __init__(self, jid, password, plugins=[], muc_domain=None):
        ClientXMPP.__init__(self, jid, password)
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("roster_update", self.changed_roster)
        self.add_event_handler("got_online", self.changed_presence)
        self.add_event_handler("got_offline", self.changed_presence)
        self.add_event_handler("stream_error", self.got_stream_error)
        self.add_event_handler("failed_auth", self.failed_auth)
        #  self.add_event_handler("presence_available", self._handle_presence_available)
        self.add_event_handler("session_end", lambda e: logger.info("Disconnecting..."))

        register_stanza_plugin(Iq, ArmonicCall)
        register_stanza_plugin(Message, ArmonicError)

        for plugin in self.base_plugins + plugins:
            if len(plugin) > 1:
                config = plugin[1]
            else:
                config = {}
            self.register_plugin(plugin[0], config)

        self.muc_domain = muc_domain
        self.muc_rooms = []

    def session_start(self, event):
        self.send_presence()
        self.get_roster()

    def got_stream_error(self, event):
        if event['condition'] == "conflict":
            logger.error("The JID %s is already in use." % self.boundjid.jid)

    def changed_roster(self, event):
        valid_subscriptions = ('to', 'from', 'both')  # 'none', 'remove'
        logger.debug("Updated roster (version %s)" % event['roster']['ver'])
        items = event['roster']['items']
        for jid, item in items.items():
            if item['subscription'] in valid_subscriptions:
                logger.debug(" - subscription %s : %s " % (jid, item['subscription']))

    def changed_presence(self, event):
        logger.info("%s is %s" % (event['from'], event['type']))

    def failed_auth(self, event):
        logger.error("Authentification failed for '%s'" % self.fulljid)
        self.disconnect()

    def parse_json(self, data):
        return json.loads(data)

    def report_error(self, code, message, jid):
        msg = self.Message()
        msg['to'] = jid
        msg['type'] = 'error'
        msg['subject'] = 'An error has occured.'
        msg['exception']['code'] = code
        msg['exception']['message'] = message
        msg.send()

    def _get_muc_room_name(self, id):
        return "%s@%s" % (id, self.muc_domain)

    def leave_muc_room(self, id):
        if self.muc_domain is None:
            return
        self['xep_0045'].leaveMUC(self._get_muc_room_name(id), self.boundjid.jid)
        self.muc_rooms.remove(self._get_muc_room_name(id))

    def join_muc_room(self, id):
        if self.muc_domain is None:
            return
        logger.info('Joining muc_room %s' % self._get_muc_room_name(id))
        self['xep_0045'].joinMUC(self._get_muc_room_name(id), self.boundjid.jid)
        self.muc_rooms.append(self._get_muc_room_name(id))

    def send_muc_message(self, id, message):
        if self.muc_domain is None:
            return
        self.send_message(mto=self._get_muc_room_name(id),
                          mbody="[%s] %s" % (self.boundjid.user, message),
                          mtype='groupchat')


class XMPPAgentApi(object):

    def __init__(self, client, agent_jid, deployment_id=None):
        self.client = client
        self.jid = agent_jid
        self.deployment_id = deployment_id

    def call(self, method, *args, **kwargs):
        iq = self.client.Iq()
        iq['to'] = self.jid
        iq['type'] = 'set'
        iq['call']['method'] = method
        iq['call']['params'] = json.dumps({'args': args, 'kwargs': kwargs})
        if self.deployment_id:
            iq['call']['deployment_id'] = self.deployment_id
        try:
            resp = iq.send()
        except IqError:
            logger.exception("Failed to send message to %s" % self.jid)
            raise XMPPError("Failed to contact %s" % self.jid)
        return json.loads(resp['call']['status'])

    def info(self):
        return self.call("info")

    def lifecycle(self, xpath, long_description=False):
        return self.call("lifecycle", xpath, long_description)

    def provide_call_validate(self, provide_xpath_uri, requires):
        return self.call("provide_call_validate",
                         provide_xpath_uri=provide_xpath_uri,
                         requires=requires)

    def uri(self, xpath, relative=False, resource=None):
        return self.call("uri",
                         xpath=xpath,
                         relative=relative,
                         resource=resource)

    def to_xml(self, xpath=None):
        """Return the xml representation of agent."""
        return self.call("to_xml", xpath=xpath)

    def provide(self, provide_xpath):
        return self.call("provide", provide_xpath=provide_xpath)

    def provide_call_path(self, provide_xpath):
        return self.call("provide_call_path", provide_xpath=provide_xpath)

    def provide_call_requires(self, provide_xpath_uri, path_idx=0):
        return self.call("provide_call_requires",
                         provide_xpath_uri=provide_xpath_uri,
                         path_idx=path_idx)

    def provide_call(self, provide_xpath_uri, requires=[], path_idx=0):
        return self.call("provide_call",
                         provide_xpath_uri=provide_xpath_uri,
                         requires=requires, path_idx=path_idx)

    def state(self, xpath, doc=False):
        return self.call("state", xpath=xpath, doc=doc)

    def state_goto(self, xpath, requires={}):
        return self.call("state_goto",
                         xpath=xpath,
                         requires=requires)

    def state_current(self, xpath):
        return self.call("state_current",
                         xpath=xpath)
