#!/usr/bin/python

from mss.client.smart import Provide, ShowAble, update_empty, user_input_variable, user_input_confirm
import mss.client.smart
import mss.require

import argparse

Variables=[]

class RequireSimple(mss.require.Require, mss.client.smart.Require, ShowAble):
    def build_values(self):
        needed = self.get_values()
        suggested = dict([(s.name,s.value) for s in self.provide_caller.suggested_args])
        ret = update_empty(suggested,needed)
        return ret

    def build_save_to(self, variable):
        variable.url.host = self.provide_caller.host
        Variables.append((variable.url,variable.value))

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
        for (url,value) in Variables:
            if ("%s.%s" % (self.provide_caller.host,self.provided_by)) == str(url):
                print url , value
                return {self.variables[0].name : value}

    def build_save_to(self, variable):
        variable.url.host = self.provide_caller.host
        Variables.append((variable.url,variable.value))

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
        variable.url.host = self.provide_caller.host
        Variables.append((variable.url,variable.value))

class RequireLocal(mss.require.RequireLocal, RequireWithProvide, ShowAble):
    def on_require_not_filled_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide_name)
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep(), prefill=self.provide.host))
        return values

    def on_validation_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' has been set with wrong value.\n'%s' = '%s'\nPlease change it:"%(
            err_variable, self.name, self.provide_name,
            err_variable, values[err_variable])
        values.update(user_input_variable(variable_name = err_variable, prefix=self.sep(), message = msg))

class RequireExternal(mss.require.RequireExternal, RequireWithProvide, ShowAble):
    def on_require_not_filled_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide_name)
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
            err_variable, self.name, self.provide_name,
            err_variable, value)
        values.update(user_input_variable(variable_name = err_variable, prefix=self.sep(), message = msg, prefill = prefill))
        return values



class MyProvide(Provide):
    def handle_call(self):
        """To validate that the inferred provide should be called.
        Moreover, you can set the host variable of this provide.

        :rtype: bool. Return True if the provide must be called, false otherwise.
        """
        self.show("Preparing the call of provide %s.%s..." % (self.lf_name,self.provide_name))
        msg = "Where do you want to call it?"
        ret = user_input_variable(prefix=self.sep(), variable_name = 'host', message = msg, prefill = self.caller_provide.host)
        host = ret['host']
        self.host = host
        msg = ("Do you really want to call %s.%s on '%s' ?" % (
                self.lf_name,
                self.provide_name,
                host))
        return user_input_confirm(msg, prefix=self.sep())

    def confirm_call(self):
        """Redefine it to confirm the provide call.

        :rtype: boolean"""
        self.show("Provide '%s' will be called with Requires:" % (self.provide_name))
        for r in self.requires:
            self.show("%s" % (r.name) , indent=1)
            self.show("%s" % (r.get_values()) , indent = 2)
        return user_input_confirm("Confirm the call?", prefix=self.sep())

MyProvide.set_require_class("external",RequireExternal)
MyProvide.set_require_class("simple",RequireSimple)
MyProvide.set_require_class("local",RequireLocal)
MyProvide.set_require_class("user",RequireUser)


description="""
mss-smart calls a provide and try to automatically fill its
requires. If provides have to be called to satisfate these requires, it
does it recursively.
"""

parser = argparse.ArgumentParser(prog='mss3-smart', description=description)
parser.add_argument('--host', type=str, default=None,help='Host where to call the provide')
parser.add_argument('--lifecyle','-l', type=str, required=True, help='The provide lifecyle name')
parser.add_argument('--provide','-p', type=str, required=True, help='The provide name')
args = parser.parse_args()

class ProvideInit(object):
    host = args.host

p = MyProvide(lf_name=args.lifecyle, provide_name=args.provide, caller_provide=ProvideInit())
print p.call()

print "Filled variables during this deployment:"
for v in Variables:
    print v
