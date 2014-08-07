from __future__ import absolute_import

import sleekxmpp
from sleekxmpp import Iq
from sleekxmpp.exceptions import XMPPError, IqTimeout
from sleekxmpp.xmlstream import register_stanza_plugin
from armonic.iq_xmpp_armonic import ActionProvider
import sys
import json
import logging
if sys.version_info < (3, 0):
    from sleekxmpp.util.misc_ops import setdefaultencoding
    setdefaultencoding('utf8')
else:
    raw_input = input
logger = logging.getLogger()


class ClientXmppProvider():
    def __init__(self, jid, password, jid_agent, host, port):
        self.clientxmpp = sleekxmpp.ClientXMPP(jid, password)
        self.clientxmpp.add_event_handler("session_start", self.start, threaded=True)
        self.clientxmpp.add_event_handler("changed_status", self.changed_status)
        self.clientxmpp.add_event_handler("roster_update", self.show_roster)
        self.clientxmpp.add_event_handler("got_online", self.now_online)
        self.clientxmpp.add_event_handler("got_offline", self.now_offline)
        self.clientxmpp.add_event_handler('presence_probe', self.handle_probe)
        self.agent=False
        register_stanza_plugin(Iq, ActionProvider)
        self._host = jid_agent
        self.clientxmpp.auto_reconnect = False
        if self.clientxmpp.connect(address=(host, port)):
            self.clientxmpp.process(block=False)
        else:
            sys.stderr.write("Unable to connect.")
            sys.exit(1)

    def get_host(self):
        return self._host

    def set_host(self, jid_agent_host):
        self._host = jid_agent_host
        if not self.check_agent():
            logger.error("%s is not an Agent" %self._host)
            self.close()
            sys.exit(1)
            
    def _handle_roster(self,iq):
        items = event['roster']['items']
        valid_subscriptions = ('to', 'from', 'both')#, 'none', 'remove'
        for jid, item in items.items():
            if item['subscription'] in valid_subscriptions:
                logger.info("subcription %s : %s " % (jid , item['subscription']))

    def changed_status(self, event):
        logger.info("changed status: %s :[%s] %s " % (event['from'],event['status'], event['message']))
  
    def show_roster(self, event):
        logger.info("ROSTER VERSION %s" % event['roster']['ver'])
        #roster = self.clientxmpp.client_roster
        items = event['roster']['items']
        valid_subscriptions = ('to', 'from', 'both')#, 'none', 'remove'
        for jid, item in items.items():
            if item['subscription'] in valid_subscriptions:
                logger.info("subcription %s : %s " % (jid , item['subscription'])) 

    def now_online(self, event):
        print "online : %s %s [%s]" % (event['from'],event['type'],event['status'])


    def now_offline(self, event):
        print "offline : %s %s [%s]" % (event['from'],event['type'],event['status'])
        
    def handle_probe(self, presence):
        sender = presence['from']
        self.clientxmpp.sendPresence(pto=sender, pstatus="armonic", pshow="chat")

    def check_agent(self):
        self.clientxmpp.sendPresence(pto=self._host, ptype='probe')
        subcribe_armonic=[]
        presence_armonic=[]
        self.clientxmpp.get_roster()
        for subscribe in self.clientxmpp.client_roster:
            subcribe_armonic.append( str(subscribe))
        for presence in self.clientxmpp.client_roster:
            presence_armonic.append( str(presence))
        hosts1=self._host.split('/')
        print presence_armonic
        print subcribe_armonic
        if hosts1[0] in presence_armonic and hosts1[0] in subcribe_armonic:
            self.agent=True
            return True
        else:
            self.agent=False
            return False

    def start(self, event):
        self.clientxmpp.send_presence()


    def call(self, method, *args, **kwargs):
        if self.check_agent():
            iq = self.clientxmpp.Iq()
            iq['to'] = self._host
            iq['type'] = 'set'
            iq['action']['method'] = method
            iq['action']['param'] = json.dumps({'args': args, 'kwargs': kwargs})
            try:
                resp = iq.send()
                #self.disconnect(wait=True)
            except XMPPError:
                resp='{"return": ["There was an error sending the %s action."]}'%method
                return json.loads(resp)
                #return resp
            return json.loads(resp['action']['status'])
        else:
            logger.error("%s is not an Agent" %self._host)
            self.close()
            sys.exit(1)

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
        self.clientxmpp.disconnect(wait=True)

    def global_timeout(self,timeout):
        self.clientxmpp.response_timeout = timeout

