#!/usr/bin/python

# Known Limitations!
# ------------------
#
# Currently, if the xpath of a require is ambigous, the specialised
# (choosen by user) xpath is used for all iteration of this
# require. But this doesn't work if several require have the same
# xpath.


import argparse

import mss.client.smart
from mss.client_socket import ClientSocket

Zephyrus_components = []
Zephyrus_implementations = []

class Provide(mss.client.smart.Provide):
    # This global variable is used to store all needed xpath
    _xpaths = {}
    
    # This will contain all used module by this deployment
    _used_lifecycles = []

    def handle_call(self):
        
        if self.host is None:
            self.host = self.requirer.host
        return True

    def handle_provide_xpath(self, xpath, matches):
        # WARNING. This doesn't work if several require have the same xpath.
        if xpath not in self._xpaths:
             self._xpaths[xpath] = user_input_choose_amongst(matches)
        return self._xpaths[xpath]

    def confirm_call(self):
        if self.xpath not in self._xpaths:
            self._xpaths[self.xpath] = self.helper_used_xpath()

        provide_xpath = self.lf_manager.call("uri", self.helper_used_xpath())[0]
        
        xpath = (self.helper_used_xpath() + 
                 "/ancestor::node()[@ressource='lifecycle']//repository/..")
        name = self.lf_manager.call("xpath", "name(%s/../..)" % provide_xpath)[0]

        # We add this lifecycle to the global used lifecycles array
        if name not in self._used_lifecycles:
            self._used_lifecycles.append(name)

        requires = []
        for r in self.requires:
            if r.nargs == '*':
                nargs = r._used_nargs
            else :
                nargs = r.nargs
            if r.type == 'external':
                requires += [{'nargs':nargs, 'xpath': p.helper_used_xpath()} for p in r.provides]
            if r.type == 'local':
                for rs in r.provides:
                    for i in rs.requires:
                        if i.type == 'external':
                            requires += [{'nargs':nargs, 'xpath': p.helper_used_xpath()} for p in i.provides]
        
        uris = self.lf_manager.call("uri", xpath)
        implementations = []
        for u in uris :
            xpath = u + "/package/text()"
            repo = self.lf_manager.call("xpath", "%s/repository/text()" % u)
            pkgs = self.lf_manager.call("xpath", "%s/package/text()" % u)
            implementations.append({"repository": repo, "packages": pkgs})

        if self.helper_requirer_type() == 'external' or self.helper_requirer_type() is None:
            Zephyrus_components.append({"name": name,
                                        "provide": [[provide_xpath,["FiniteProvide", 1]]],
                                        "requires" : [["@%s" % r['xpath'] , r['nargs']] for r in requires]})

            Zephyrus_implementations.append([
                name, [[i['repository'][0], i['packages'][0]] 
                       for i in implementations if i['repository'][0] == "mbs"]])
            

        return False


def user_input_choose_amongst(choices, prefix=''):
    """Ask the user if he confirm the msg question.

    :rtype: True if user confirm, False if not"""
    while True:
        print "%sYou must choose a provide amongst:" % prefix
        for i, c in enumerate(choices) :
            print "  %s%d) %s" % (prefix, i, c)
        answer = raw_input("%sChoose a provide [0-%d]: " % (prefix, len(choices)-1))
        try:
            return choices[int(answer)]
        except Exception as e:
            print e
            print "%sInvalid choice. Do it again!" % (prefix)


class Require(object):
    def build_values(self):
        return {}

    def handle_validation_error(self):
        return False


    def handle_many_requires(self, counter):
        if not hasattr(self, "_counter"):
            while True:
                answer = raw_input(
                    "How many time you want to call the provide\n\t%s ? "% self.xpath)
                try:
                    int(answer)
                    break
                except Exception as e:
                    print e
                    print "Invalid choice. Do it again!"
            self._counter = int(answer) - 1
            self._used_nargs = int(answer)
        return False
        
class RequireExternal(Require, mss.client.smart.RequireExternal):
    pass
class RequireLocal(Require, mss.client.smart.RequireLocal):
    pass
class RequireSimple(Require, mss.client.smart.Require):
    pass
class RequireUser(Require, mss.client.smart.RequireUser):
    pass

Provide.set_require_class("external",RequireExternal)
Provide.set_require_class("simple",RequireSimple)
Provide.set_require_class("local",RequireLocal)
Provide.set_require_class("user",RequireUser)


description=""" mss-zephyrus asks user what kind of provide he wants to call and
construct input zephyrus files.  """

parser = argparse.ArgumentParser(prog='mss3-aeolus', description=description)
parser.add_argument('--host', type=str, required=True, help='Host where to call the provide')
parser.add_argument('--xpath','-x', type=str, required=True, help='A provide Xpath')
args = parser.parse_args()

provide = mss.client.smart.build_initial_provide(Provide, args.host, args.xpath)
provide.call()

import pprint
pprint.pprint({"component_types": Zephyrus_components,
               "implementation": Zephyrus_implementations,
               "specialisation": Provide._xpaths})


def compute_requires(provide_xml_elt):
    """From a provide element in xml, this function return the list of all
    requires xpath useful for Metis. In fact, we accumulate remote requires
    of all provides and entry method.

    This has to be discussed ...
    """
    requires = []
    for require in provide_xml_elt:
        if require.tag not in ["cross","leave"]:
            rtype = require.find('properties/type')
            if rtype is not None and rtype.text in ['external', 'local']:
                requires.append(require.find('properties/xpath').text)
    return requires

def specialize_requires(requires_xpath, bindings):
    """From a list of xpath, try to find a corresponding specialized xpath
    that comes from user choice.
    """
    spec = []
    for x in requires_xpath:
        try:
            spec.append(bindings[x])
        except KeyError:
            spec.append(x)
    return spec

def is_mbs_state(state_xml_elt):
    """Hack to avoid state diamonds.
    Return True is mbs compatbible"""
    test = False
    for os_name in state_xml_elt.findall("properties/supported_os/name"):
        if os_name.text in ['Mandriva Business Server','all']:
            test = True
            break;
    return test


import lxml
xml_data = ClientSocket(host=args.host).call("to_xml") 
tree = lxml.etree.fromstring(xml_data)
root = tree.getroottree()

metis_json = []

# For each used lifecycle by zephyrus,
# we compute an automaton
for lf_name in Provide._used_lifecycles:
    lf_elt = tree.findall(lf_name)[0]
    states = []

    # For each state, we generate its successors, 
    # requires and provides
    for state_elt in lf_elt:
        if state_elt.tag != "properties":

            # Hack to avoid diamond
            if not is_mbs_state(state_elt):
                continue
                
            # We generate the remote requires of a state. Currently,
            # we accumulate the remote requires of entry method and
            # all provides.  
            #
            # In a second step, the provide xpath are
            # specialized according with the xpaths used by zephyrus.
            requires = []
            for provide_elt in state_elt:
                requires += specialize_requires(
                    compute_requires(provide_elt),
                    Provide._xpaths)
     
            states.append({
                "u_name" : state_elt.tag,
                "u_successors" : [e[1].text 
                                  for e in lf_elt.findall("properties/transition") 
                                  if ((e[0].text == state_elt.tag and
                                       is_mbs_state(lf_elt.find(e[1].text))
                                   ))
                              ],
                "u_provides" : [root.getpath(e)
                                for e in state_elt
                                if e.tag not in ["properties","entry","cross","leave"]],
                "u_requires" : requires
            })
    metis_json.append({"u_cname": lf_name,
                       "u_automaton": states})

print
print
import json
print json.dumps(metis_json)
    
    
