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

Zephyrus_components = []
Zephyrus_implementations = []

class Provide(mss.client.smart.Provide):
    _xpaths = {}
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
        provide_xpath = self.lf_manager.call("uri", self.helper_used_xpath())[0]
        
        xpath = (self.helper_used_xpath() + 
                 "/ancestor::node()[@ressource='lifecycle']//repository/..")
        name = self.lf_manager.call("xpath", "name(%s/../..)" % provide_xpath)[0]
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

#        self.helper_requirer_type == 'external':
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
#    def build_provide_class(self):
#        return Provide

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
               "implementation" : Zephyrus_implementations})
