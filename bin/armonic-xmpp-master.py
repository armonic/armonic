import logging
import argparse
import time

from sleekxmpp import ClientXMPP

from sleekxmpp.thirdparty import OrderedDict

import mss.serialize
from mss.client.iter_smart import Provide, walk


lfm = mss.serialize.Serialize(
    modules_dir="mss/modules/",
    os_type=mss.utils.OsType("Mandriva Business Server"))


root_provide = Provide(generic_xpath="//Varnish//start", lfm=lfm)
smart = walk(root_provide)

class Master(ClientXMPP):

    def __init__(self, jid, password, lfm):
        ClientXMPP.__init__(self, jid, password)
        self.add_event_handler("session_start", self.session_start)
        self.lfm = lfm
        self.smart = None

    def session_start(self, event):
        self.send_presence()
        self.get_roster()

        self['xep_0050'].add_command(node='provides',
                                     name='Get the list of provides',
                                     handler=self._handle_command_provides)
        self['xep_0050'].add_command(node='build',
                                     name='Build a provide',
                                     handler=self._handle_command_build)
        

    def _handle_command_provides(self, iq, session):
        print "_handle_command_provides"
        form = self['xep_0004'].makeForm('form', 'List of provides')
        form['instructions'] = 'Choose a xpath amongst them'
        form.add_reported("xpath")
        form.add_reported("tag")
        form.add_reported("label")
        form.add_reported("help")

        for p in self.lfm.provide("//*"):
            form.add_item(OrderedDict({
                "xpath":p['xpath'],
                "tag":"TODO",
                "label": "Un nom de provide humain",
                "help": "Un tres long message d'aide qui decrit precismeent ce que fait le provide"}))
        
        session['payload'] = form
        session['next'] = None # self._handle_command_init_walk
        session['has_next'] = False
        session['id'] = "session_id_pour_test"
            
        return session


    def _handle_command_build(self, iq, session):
        form = self['xep_0004'].makeForm('form', 'Specify a provide')
        form['instructions'] = 'Specify a provide'
        form.add_field(var="xpath")
        session['payload'] = form
        session['next'] = self._handle_command_init_build_next
        session['has_next'] = False
        session['id'] = "session_id_pour_test"

        self.smart = None
        self.root_provide = None
        self.current_step = None
        
        return session


    def _handle_command_init_build_next(self, payload, session):
        if self.smart is None:
            print "Step: Create root_provide"
            xpath = payload['values']['xpath']
            self.root_provide = Provide(generic_xpath=xpath, lfm=self.lfm)
            self.smart = walk(self.root_provide)

        try:
            print "Tring to configure step %s by smart.sending value %s" % (
                self.current_step, payload['values'][self.current_step])
            provide, step, args = self.smart.send(payload['values'][self.current_step])
        except KeyError:
            provide, step, args = self.smart.next()

        form = self['xep_0004'].makeForm('form', 'Build a provide')
        self.current_step = step
        print "Current step is now %s" % step

        form['instructions'] = step
        form.add_field(var="provide", ftype="fixed", value=provide.generic_xpath)

        if step == 'manage':
            form.add_field(var="manage", ftype="boolean", desc="manage this provide")

        elif step == 'specialize':
            form.add_field(var="specialize", 
                           ftype="list-single", 
                           desc="specialize the provide",
                           options=provide.matches())
            
        session['payload'] = form
        session['next'] = self._handle_command_init_build_next
        session['has_next'] = False
        session['id'] = "session_id_pour_test"

        return session





if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='scheduler')
    parser.add_argument('--host', 
                        required=True, type=str,
                        help="XMPP server host")
    parser.add_argument('--port', 
                        default=5222, type=int,
                        help="XMPP server port (default '%(default)s')")
    parser.add_argument('--jid','-j', 
                        default='test1@im.aeolus.org', type=str,
                        help="Jid (default '%(default)s')")
    parser.add_argument('--password','-p', 
                        default='test1', type=str,
                        help="Password (default '%(default)s')")
    parser.add_argument('--input-event-file','-i', 
                        default='-', type=argparse.FileType('r', 0),
                        help="Input file where events are read")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-8s %(message)s')


    xmpp = Master('%s/master' % args.jid, args.password, lfm=lfm)

    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0004') # Data Forms
    xmpp.register_plugin('xep_0050') # Adhoc Commands
    xmpp.register_plugin('xep_0199', {'keepalive': True, 'frequency':15})

    xmpp.connect(address=(args.host, args.port))
    try:
        xmpp.process(block=True)
    except KeyboardInterrupt:
        pass



