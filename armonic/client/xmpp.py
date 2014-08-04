from __future__ import absolute_import

import sleekxmpp
from sleekxmpp import Iq
from sleekxmpp.exceptions import XMPPError
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
        register_stanza_plugin(Iq, ActionProvider)
        self.action_provider = jid_agent
        self.clientxmpp.register_plugin('xep_0030')  # Service Discovery
        if self.clientxmpp.connect(address=(host, port)):
            self.clientxmpp.process(block=False)
        else:
            sys.stderr.write("Unable to connect.")
            sys.exit(1)
            
    def get_host(self):
        return self.action_provider
    
    def set_host(self, jid_agent_host):
        self.action_provider = jid_agent_host
    
    def start(self, event):
        self.clientxmpp.send_presence()
        self.clientxmpp.get_roster()

    def call(self, method, *args, **kwargs):
        iq = self.clientxmpp.Iq()
        iq['to'] = self.action_provider
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
