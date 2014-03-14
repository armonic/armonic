#!/usr/bin/python

from armonic.client.smart import Provide, update_empty, LocalProvide
import armonic.client.smart
import armonic.require
import readline
from itertools import repeat
import termcolor

import sys
import argparse

Variables=[]

import logging
logger_root = logging.getLogger()
logger_root.setLevel(logging.DEBUG)


class ShowAble(object):
    def sep(self,offset=0):
        if self.depth + offset == 0:
            return ""
#        return str(self.depth)+"/"+str(offset)+"".join(repeat("    ",self.depth+offset))
        return "".join(repeat("    ",self.depth+offset))

    def show(self,str,indent=0):
        print "%s%s" % (self.sep(offset=indent) , str)


class RequireSimple(armonic.client.smart.Require, ShowAble):
    def build_values(self):
        return update_empty(self.helper_suggested_values(),
                            self.helper_needed_values())

    def build_save_to(self, variable):
        abs_xpath="/"+self.provide_caller.host+"/"+variable.get_xpath_relative()
        Variables.append((abs_xpath,variable.value))

    def on_require_not_filled_error(self,err_variable,values):
        msg = ("Variable '%s' of simple require '%s' of provide '%s' is not set.\n"
               "%sPlease set it:" % (
                   err_variable, 
                   self.name, 
                   self.provide_caller.provide_name,
                   self.sep()))
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep()))
        return values

    def on_validation_error(self,err_variable,values):
        msg = ("Variable '%s' of simple require '%s' of provide '%s' is not set.\n"
               "%sPlease set it:" % (
                   err_variable, 
                   self.name,
                   self.provide_caller.provide_name, 
                   self.sep()))
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep()))
        return values



class RequireUser(armonic.client.smart.RequireUser, ShowAble):
    def build_values(self):
        # Here we generate require value
        host = self.provide_caller.host
        for (absXpath,value) in Variables:
            if ("/"+host+"/"+self.provided_by) == absXpath:
                return {self._variables[0][0].name : value}
        self.show("Variable %s not found is already set variables!" % self.provided_by)
        return {}

    def build_save_to(self, variable):
        xpath_rel = variable.get_xpath_relative()
        xpath_abs = "/" + self.provide_caller.host + "/" + xpath_rel
        Variables.append((xpath_abs,variable.value))

    def on_validation_error(self,err_variable,values):
        msg = ("Variable '%s' of user require '%s' of provide '%s' is not set.\n"
               "%sPlease set it:" % (
                   err_variable, 
                   self.name,
                   self.provide_caller.provide_name, 
                   self.sep()))
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep()))
        return values

class RequireWithProvide(armonic.client.smart.RequireSmartWithProvide):
    def build_provide_class(self):
        return provide_cls

    def handle_many_requires(self, counter):
        msg = ("Do you want to call again %s (already called %s time(s))?" % (
                self.xpath, counter))
        return user_input_confirm(msg, prefix=self.sep())
        

    def build_values(self):
        return update_empty(
            self.helper_needed_values(), 
            self.helper_current_provide_result_values())


    def build_save_to(self, variable):
        xpath_rel = variable.get_xpath_relative()
        xpath_abs = "/" + self.provide_caller.host + "/" + xpath_rel
        Variables.append((xpath_abs,variable.value))

class RequireLocal(armonic.client.smart.RequireLocal, RequireWithProvide, ShowAble):
    def on_validation_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' has been set with wrong value.\n'%s' = '%s'\nPlease change it:"%(
            err_variable, self.name, self.provide_name,
            err_variable, values[err_variable])
        values.update(user_input_variable(
            variable_name = err_variable, 
            prefix=self.sep(), 
            message = msg))

class RequireExternal(armonic.client.smart.RequireExternal, RequireWithProvide, ShowAble):
    def on_validation_error(self,err_variable,values):
        try :
            value = values[err_variable]
        except KeyError :
            value = None
        if err_variable == 'host':
            values.update({'host': self._provide_current.host})
        else:
            prefill = ""
            msg = ("Variable '%s' of require '%s' of provide '%s' has "
                   "been set with wrong value.\n'%s' = '%s'\nPlease change it:")%(
                       err_variable, 
                       self.name, 
                       self._provide_current.requirer.used_xpath,
                       err_variable, value)
            values.update(user_input_variable(
                variable_name = err_variable, 
                prefix=self.sep(), 
                message = msg, 
                prefill = prefill))
        return values


class ColorFormatter(logging.Formatter):
    def format(self,record):
        ret = logging.Formatter.format(self, record)
        return termcolor.colored(ret, 'grey')

class MyProvide(Provide, ShowAble):
    
    def handle_provide_xpath(self,xpath, matches):
        return user_input_choose_amongst(matches, self.sep())

    def handle_call(self):
        """To validate that the inferred provide should be called.
        Moreover, you can set the host variable of this provide.

        :rtype: bool. Return True if the provide must be called, false otherwise.
        """
        self.show("Preparing the call of provide %s ..." % (self.used_xpath))
        if self.requirer_type == 'external':
            msg = "Where do you want to call it?"
            ret = user_input_variable(prefix=self.sep(), variable_name = 'host', message = msg, prefill = self.requirer.host)
            host = ret['host']
        else:
            host = self.requirer.host
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


    def set_logging_handlers(self):
        handler = logging.StreamHandler(sys.stdout)
        format = '%(levelname)5s %(ip)15s - %(message)s'
        handler.setFormatter(ColorFormatter(format))
        return [handler]


class MyLocalProvide(LocalProvide, MyProvide):
    def _lf_manager(self):
        if args.os_type is not None:
            os_type = armonic.utils.OsType(args.os_type)
        else :
            os_type = None
        return armonic.lifecycle.LifecycleManager(modules_dir="armonic/modules", os_type=os_type)



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
armonic-smart calls a provide and try to automatically fill its
requires. If provides have to be called to satisfate these requires, it
does it recursively.
"""

parser = argparse.ArgumentParser(prog='armonic-smart', description=description)
parser.add_argument('--host', type=str, default=None,help='Host where to call the provide')
parser.add_argument('--xpath','-x', type=str, required=True, help='A provide Xpath')
parser.add_argument('--os-type','-o', type=str, default=None, help='The os type to use')
args = parser.parse_args()


class ProvideInit(object):
    host = args.host
    requirer = None
    suggested_args = []
    xpath = "Init"



if args.host is None:
    provide_cls = MyLocalProvide
else:
    provide_cls = MyProvide

provide_cls.set_require_class("external",RequireExternal)
provide_cls.set_require_class("simple",RequireSimple)
provide_cls.set_require_class("local",RequireLocal)
provide_cls.set_require_class("user",RequireUser)

p = provide_cls(xpath=args.xpath, requirer=ProvideInit())
print p.call()


print "Filled variables during this deployment:"
for v in Variables:
    print v
