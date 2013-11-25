#!/usr/bin/python

from mss.client.smart import Provide, ShowAble, update_empty
import mss.client.smart
import mss.require
import readline

import argparse

Variables=[]

class RequireSimple(mss.require.Require, mss.client.smart.Require, ShowAble):
    def build_values(self):
        needed = self.get_values()
        if self in self.provide_caller.provide_requires:
            suggested = dict([(s.name,s.value) for s in self.provide_caller.suggested_args])
        else :
            suggested = {}
        ret = update_empty(suggested,needed)
        return ret

    def build_save_to(self, variable):
        variable.uri.host = self.provide_caller.host
        Variables.append((variable.uri,variable.value))

    def on_require_not_filled_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide_caller.provide_name)
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep()))
        return values

    def on_validation_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide_caller.provide_name)
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep()))
        return values



class RequireUser(mss.require.RequireUser, mss.client.smart.Require, ShowAble):
    def build_values(self):
        # Here we generate require value
        self.provided_by.host = self.provide_caller.host
        for (uri,value) in Variables:
            if str(self.provided_by) == str(uri):
                return {self.variables[0].name : value}
        self.show("Variable %s not found is already set variables!" % self.provided_by)
        return {}

    def build_save_to(self, variable):
        variable.uri.host = self.provide_caller.host
        Variables.append((variable.uri,variable.value))

    def on_validation_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide_caller.provide_name)
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep()))
        return values

class RequireWithProvide(mss.client.smart.RequireWithProvide):
    def build_provide_class(self):
        return MyProvide

    def build_values(self):
        # Here we generate require value
#        print "PROVIDE RET" , self.provide.provide_ret
#        print "GET VALUE" , self.get_values()
#        print "PROVIDE ARGS" , self.provide_args
        
#        print "REQUIRE" , self.variables
        ret = update_empty(self.get_values(), self.provide.provide_ret)
#        print "RET VALUE" , ret
        return ret

    def build_save_to(self, variable):
        variable.uri.host = self.provide_caller.host
        Variables.append((variable.uri,variable.value))

class RequireLocal(mss.require.RequireLocal, RequireWithProvide, ShowAble):
    def on_require_not_filled_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide.caller_provide.used_xpath)
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep(), prefill=self.provide.host))
        return values

    def on_validation_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' has been set with wrong value.\n'%s' = '%s'\nPlease change it:"%(
            err_variable, self.name, self.provide_name,
            err_variable, values[err_variable])
        values.update(user_input_variable(variable_name = err_variable, prefix=self.sep(), message = msg))

class RequireExternal(mss.require.RequireExternal, RequireWithProvide, ShowAble):
    def on_require_not_filled_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide.caller_provide.used_xpath)
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep(), prefill=self.provide.host))
        return values

    def on_validation_error(self,err_variable,values):
        try :
            value = values[err_variable]
        except KeyError :
            value = None
        if err_variable == 'host':
            prefill = self.provide.host
        else:
            prefill = ""
        msg = "Variable '%s' of require '%s' of provide '%s' has been set with wrong value.\n'%s' = '%s'\nPlease change it:"%(
            err_variable, self.name, self.provide.caller_provide.used_xpath,
            err_variable, value)
        values.update(user_input_variable(variable_name = err_variable, prefix=self.sep(), message = msg, prefill = prefill))
        return values



class MyProvide(Provide):
    
    def handle_provide_xpath(self,xpath, matches):
        return user_input_choose_amongst(matches, self.sep())

    def handle_call(self):
        """To validate that the inferred provide should be called.
        Moreover, you can set the host variable of this provide.

        :rtype: bool. Return True if the provide must be called, false otherwise.
        """
        self.show("Preparing the call of provide %s ..." % (self.used_xpath))
        msg = "Where do you want to call it?"
        ret = user_input_variable(prefix=self.sep(), variable_name = 'host', message = msg, prefill = self.caller_provide.host)
        host = ret['host']
        self.host = host
        msg = ("Do you really want to call %s on '%s' ?" % (
                self.used_xpath,
                host))
        return user_input_confirm(msg, prefix=self.sep())

    def confirm_call(self):
        """Redefine it to confirm the provide call.

        :rtype: boolean"""
        self.show("Provide '%s' will be called with Requires:" % (self.used_xpath))
        for r in self.requires:
            self.show("%s" % (r.name) , indent=1)
            self.show("%s" % (r.get_values()) , indent = 2)
        return user_input_confirm("Confirm the call?", prefix=self.sep())

MyProvide.set_require_class("external",RequireExternal)
MyProvide.set_require_class("simple",RequireSimple)
MyProvide.set_require_class("local",RequireLocal)
MyProvide.set_require_class("user",RequireUser)


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
            

def user_input_confirm(msg, prefix=''):
    """Ask the user if he confirm the msg question.

    :rtype: True if user confirm, False if not"""
    answer = raw_input("%s%s\n%s[Y]/n: " % (prefix, msg ,prefix))
    if answer == 'n':
        return False
    return True

def user_input_variable(variable_name, message, prefix="", prefill=""):
    """
    :param variable_name: The name of the variable that user must set
    :param message: A help message
    :rtype: {variable_name:value}
    """
    prompt = "%s%s\n%s%s = " % (prefix, message, prefix, variable_name)
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return {variable_name:raw_input(prompt)}
    finally:
        readline.set_startup_hook()



description="""
mss-smart calls a provide and try to automatically fill its
requires. If provides have to be called to satisfate these requires, it
does it recursively.
"""

parser = argparse.ArgumentParser(prog='mss3-smart', description=description)
parser.add_argument('--host', type=str, default=None,help='Host where to call the provide')
parser.add_argument('--xpath','-x', type=str, required=True, help='A provide Xpath')
args = parser.parse_args()

class ProvideInit(object):
    host = args.host

p = MyProvide(xpath=args.xpath, caller_provide=ProvideInit())
print p.call()

print "Filled variables during this deployment:"
for v in Variables:
    print v
