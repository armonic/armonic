from __future__ import absolute_import

import sleekxmpp
from sleekxmpp import Iq
from sleekxmpp.exceptions import IqTimeout, IqError
from sleekxmpp.xmlstream import register_stanza_plugin
from armonic.iq_xmpp_armonic import ActionProvider
import sys
import json
import logging
import threading

if sys.version_info < (3, 0):
    from sleekxmpp.util.misc_ops import setdefaultencoding
    setdefaultencoding('utf8')
else:
    raw_input = input
logger = logging.getLogger(__name__)


class XmppError(Exception):
    pass


class Xmpp():
    def __init__(self, jid, password, jid_agent, host, port):
        self._client_xmpp = sleekxmpp.ClientXMPP(jid, password)

        # Use to wait until client is connected
        self.ready = threading.Event()
        # Set to true when connected
        self.connected = False
        
        self._client_xmpp.add_event_handler("session_start", self.start)
        self._client_xmpp.add_event_handler("changed_status", self.changed_status)
        self._client_xmpp.add_event_handler("roster_update", self.show_roster)
        self._client_xmpp.add_event_handler("got_online", self.now_online)
        self._client_xmpp.add_event_handler("got_offline", self.now_offline)
        self._client_xmpp.add_event_handler("failed_auth", self._handle_failed_auth)
        self._client_xmpp.add_event_handler("session_end",
                               lambda e : logger.info("Disconnecting..."))

        #self._client_xmpp.add_event_handler('presence_probe', self.handle_probe)

        self.agent = False
        register_stanza_plugin(Iq, ActionProvider)
        self._host = jid_agent
        self._client_xmpp.auto_reconnect = False
        logger.info("Connection with account '%s'..." % self._client_xmpp.jid)
        if self._client_xmpp.connect(address=(host, port)):
            self._client_xmpp.process(block=False)
        else:
            logger.error("Unable to connect")
            sys.exit(1)

    def disconnect(self):
        """Disconnect xmpp and release locks"""
        self._client_xmpp.disconnect()
        self.ready.set()

    def _handle_failed_auth(self, event):
        logger.error("Authentification failed for '%s'" % self._client_xmpp.fulljid)
        self.disconnect()

    def get_host(self):
        return self._host

    def set_host(self, jid_agent_host):
        self._host = jid_agent_host
        self.check_agent()
            
    def _handle_roster(self,iq):
        items = iq['roster']['items']
        valid_subscriptions = ('to', 'from', 'both')#, 'none', 'remove'
        for jid, item in items.items():
            if item['subscription'] in valid_subscriptions:
                logger.info("subcription %s : %s " % (jid , item['subscription']))

    def changed_status(self, event):
        logger.debug("changed status: %s :[%s] %s " % (event['from'],event['status'], event['message']))
  
    def show_roster(self, event):
        logger.debug("Roster version: %s" % event['roster']['ver'])
        #roster = self._client_xmpp.client_roster
        items = event['roster']['items']
        valid_subscriptions = ('to', 'from', 'both')  # 'none', 'remove'
        for jid, item in items.items():
            if item['subscription'] in valid_subscriptions:
                logger.debug("subcription %s : %s " % (jid, item['subscription'])) 

    def now_online(self, event):
        logger.debug("online : %s %s [%s]" % (event['from'],event['type'],event['status']))


    def now_offline(self, event):
        logger.debug( "offline : %s %s [%s]" % (event['from'],event['type'],event['status']))
        
    #def handle_probe(self, presence):
        #sender = presence['from']
        #self._client_xmpp.sendPresence(pto=sender, pstatus="armonic", pshow="chat")

    def check_agent(self):
        self._client_xmpp.sendPresence(pto=self._host, ptype='probe')
        subcribe_armonic=[]
        presence_armonic=[]
        self._client_xmpp.get_roster()
        for subscribe in self._client_xmpp.client_roster:
            subcribe_armonic.append( str(subscribe))
        for presence in self._client_xmpp.client_roster:
            presence_armonic.append( str(presence))
        hosts1=self._host.split('/')
        if not hosts1[0] in presence_armonic or not hosts1[0] in subcribe_armonic:
            logger.error("%s is not an Agent" % self._host)
            self.close()
            sys.exit(1)

    def start(self, event):
        logger.info("Connected")
        self._client_xmpp.send_presence()
        self.connected = True
        self.ready.set()

    def call(self, method, *args, **kwargs):
        logger.debug("Waiting connection...")
        # We are wainting for threading.Event which is set on
        # start_session or on error
        self.ready.wait()
        if self.connected:
            self.check_agent()
            iq = self._client_xmpp.Iq()
            iq['to'] = self._host
            iq['type'] = 'set'
            iq['action']['method'] = method
            iq['action']['param'] = json.dumps({'args': args, 'kwargs': kwargs})
            try:
                resp = iq.send()
            except IqError:
                msg = "Can not communicate with '%s'. Is it connected?" % self._host
                logger.critical(msg)
                raise XmppError(msg)
            return json.loads(resp['action']['status'])

        return {}

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

    def close(self):
        self._client_xmpp.disconnect(wait=True)

    def global_timeout(self, timeout):
        self._client_xmpp.response_timeout = timeout

