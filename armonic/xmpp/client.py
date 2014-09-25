from __future__ import absolute_import

import sys
import json
import logging

from sleekxmpp import ClientXMPP, Iq, Message
from sleekxmpp.jid import JID, InvalidJID
from sleekxmpp.exceptions import IqError, IqTimeout
from sleekxmpp.xmlstream import register_stanza_plugin
from sleekxmpp.xmlstream.handler import Callback
from sleekxmpp.xmlstream.matcher import StanzaPath
from threading import Event

from armonic.xmpp.stanza import ArmonicResult, ArmonicLog, \
    ArmonicCall, ArmonicStatus, ArmonicException
from armonic.frontends.utils import COLOR_SEQ, RESET_SEQ, GREEN, CYAN

if sys.version_info < (3, 0):
    from sleekxmpp.util.misc_ops import setdefaultencoding
    setdefaultencoding('utf8')
else:
    raw_input = input


logger = logging.getLogger(__name__)


class LifecycleException(Exception):
    pass


class XMPPError(Exception):
    pass


class XMPPClientBase(ClientXMPP):
    base_plugins = [
        ('xep_0030',),  # Disco
        ('xep_0004',),  # Dataforms
        ('xep_0045',),  # MUC
        ('xep_0199', {'keepalive': True, 'frequency': 15})
    ]
    """Always loaded plugins"""

    def __init__(self, jid, password, plugins=[], muc_domain=None):
        if JID(jid).resource:
            raise InvalidJID("The provided JID shouldn't have a resource")
        ClientXMPP.__init__(self, jid, password)
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("roster_update", self.changed_roster)
        self.add_event_handler("got_online", self.changed_presence)
        self.add_event_handler("got_offline", self.changed_presence)
        self.add_event_handler("stream_error", self.got_stream_error)
        self.add_event_handler("failed_auth", self.failed_auth)
        #  self.add_event_handler("presence_available", self._handle_presence_available)
        self.add_event_handler("session_end", self.session_end)

        register_stanza_plugin(Iq, ArmonicCall)
        register_stanza_plugin(Iq, ArmonicResult)
        register_stanza_plugin(Iq, ArmonicStatus)
        register_stanza_plugin(Iq, ArmonicException)
        register_stanza_plugin(Message, ArmonicLog)

        self.registerHandler(
            Callback('handle armonic exceptions',
                     StanzaPath('iq/exception'),
                     self._handle_armonic_exception)
        )
        self.add_event_handler('armonic_exception',
                               self.handle_armonic_exception)

        for plugin in self.base_plugins + plugins:
            if len(plugin) > 1:
                config = plugin[1]
            else:
                config = {}
            self.register_plugin(plugin[0], config)

        self.muc_domain = muc_domain
        self.muc_rooms = []

    def _handle_armonic_exception(self, iq):
        self.event('armonic_exception', iq['exception'])
        logger.debug("Handle exception '%s': %s" % (iq['exception']['code'],
                                                    iq['exception']['message']))

    def handle_armonic_exception(self, exception):
        logger.error("%s: %s" % (exception['code'],
                                 exception['message']))

    def session_start(self, event):
        self.send_presence()
        self.get_roster()

    def session_end(self, event):
        logger.info("Exiting...")

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
        logger.debug("%s is %s" % (event['from'], event['type']))

    def failed_auth(self, event):
        logger.error("Authentification failed for '%s'" % self.fulljid)
        self.disconnect()

    def parse_json(self, data):
        return json.loads(data)

    def report_exception(self, jid, exception, deployment_id=None):
        iq = self.Iq()
        iq.error()
        iq['to'] = jid
        iq['subject'] = 'An error has occured.'
        iq['exception']['code'] = exception.__class__.__name__
        iq['exception']['message'] = exception.message
        if deployment_id is not None:
            iq['exception']['deployment_id'] = deployment_id
        try:
            iq.send(block=False)
        except IqTimeout:
            pass

    def _get_muc_room_name(self, id):
        return "%s@%s" % (id, self.muc_domain)

    def leave_muc_room(self, id):
        if self.muc_domain is None:
            return
        logger.debug('Leaving muc_room %s' % self._get_muc_room_name(id))
        self['xep_0045'].leaveMUC(self._get_muc_room_name(id), self.boundjid.user)
        self.muc_rooms.remove(self._get_muc_room_name(id))

    def join_muc_room(self, id):
        if self.muc_domain is None:
            logger.warning("MUC domain not set, can't send or read logs.")
            return
        logger.debug('Joining muc_room %s' % self._get_muc_room_name(id))
        self['xep_0045'].joinMUC(self._get_muc_room_name(id), self.boundjid.user)
        self.muc_rooms.append(self._get_muc_room_name(id))

    def send_muc_message(self, id, message):
        if self.muc_domain is None:
            return
        message['to'] = self._get_muc_room_name(id)
        message['type'] = 'groupchat'
        message.send()


class XMPPCallSync(XMPPClientBase):

    def __init__(self, *args, **kwargs):
        XMPPClientBase.__init__(self, *args, **kwargs)
        # To handle LifecycleManager method calls
        self.registerHandler(
            Callback('handle result of a call',
                     StanzaPath('iq@type=set/result'),
                     self._handle_armonic_result)
        )
        self.add_event_handler('armonic_result',
                               self.handle_armonic_result,
                               threaded=True)

        self.registerHandler(
            Callback('handle armonic log messages',
                     StanzaPath('message/log'),
                     self._handle_armonic_log)
        )
        self.add_event_handler('armonic_log',
                               self.handle_armonic_log,
                               threaded=True)

        # flag to wait for a result
        self._result_ready = Event()
        # This will contains the result
        self._result_ready._result = None
        # This is used to know if the result is an exception or not
        self._result_ready._result_is_exception = False

    def _handle_armonic_result(self, iq):
        self.event('armonic_result', iq)

    def handle_armonic_result(self, iq):
        result = iq['result']['value']

        iq.reply()
        iq['status']['value'] = 'received'
        iq.send()

        self._result_ready._result_is_exception = False
        self._result_ready._result = result
        self._result_ready.set()

    def handle_armonic_exception(self, exception):
        self._result_ready._result_is_exception = True
        self._result_ready._result = exception
        self._result_ready.set()

    def _handle_armonic_log(self, message):
        self.event('armonic_log', message)

    def handle_armonic_log(self, msg):
        logger_method = logger.info
        if msg['log']:
            try:
                logger_method = getattr(logger, msg['log']['level_name'])
            except AttributeError:
                logger_method = logger.info
        logger_method('[%s%s%s] %s%s%s' % (COLOR_SEQ % GREEN, msg['from'].resource, RESET_SEQ,
                                           COLOR_SEQ % CYAN, msg['body'], RESET_SEQ))

    def call(self, jid, deployment_id, method, *args, **kwargs):
        iq = self.Iq()
        iq['to'] = jid
        iq['type'] = 'set'
        iq['call']['method'] = method
        iq['call']['params'] = json.dumps({'args': args, 'kwargs': kwargs})
        if deployment_id is not None:
            iq['call']['deployment_id'] = deployment_id
        try:
            resp = iq.send()
        except IqError:
            logger.error("Failed to send message to %s" % jid)
            raise XMPPError("Failed to contact %s" % jid)

        if not resp['status']['value'] == 'executing':
            logger.error(resp)

        # Waiting for a result
        self._result_ready.wait()
        self._result_ready.clear()
        if self._result_ready._result_is_exception:
            raise LifecycleException("%s: %s" % (
                self._result_ready._result['code'],
                self._result_ready._result['message']))
        else:
            return json.loads(self._result_ready._result)


class XMPPAgentApi(object):

    def __init__(self, client, agent_jid, deployment_id=None):
        self.client = client
        self.jid = agent_jid
        self.deployment_id = deployment_id

    def call(self, method, *args, **kwargs):
        return self.client.call(self.jid, self.deployment_id, method, *args, **kwargs)

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
