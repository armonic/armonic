import logging

import readline
from itertools import repeat
import json

from armonic.frontends.utils import read_variable, show_variable, \
    COLOR_SEQ, RESET_SEQ, CYAN
from armonic.client.smart import smart_call, SmartException


logger = logging.getLogger()


def user_input_confirm(msg, prefix=''):
    """Ask the user if he confirm the msg question.

    :rtype: True if user confirm, False if not"""
    answer = raw_input(msg)
    if answer == 'n':
        return False
    return True


def user_input_choose_amongst(choices, message, prefix=''):
    """Ask the user if he confirm the msg question.

    :rtype: True if user confirm, False if not"""
    while True:
        print "%s%s:" % (prefix, message)
        for i, c in enumerate(choices):
            print "%s  %d) %s" % (prefix, i, c['label'])
        answer = raw_input("%sChoose [0-%d]: " % (prefix, len(choices) - 1))
        try:
            return choices[int(answer)]['value']
        except Exception as e:
            print e
            print "%sInvalid choice. Do it again!" % (prefix)


def user_input_variable(variable_name, message, prefix="", prefill=""):
    """
    :param variable_name: The name of the variable that user must set
    :param message: A help message
    :rtype: {variable_name:value}
    """
    prompt = "%s%s\n%s%s = " % (prefix, message, prefix, variable_name)
    data = None
    while True:
        readline.set_startup_hook(lambda: readline.insert_text(prefill))
        try:
            data = read_variable(raw_input(prompt))
            break
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print "%sThe folowing error occurs:" % prefix
            print "%s  %s" % (prefix, e)
            continue
        finally:
            readline.set_startup_hook()
    return {variable_name: data}


def run(root_provide, prefill, output_file, manage, autofill):
    generator = smart_call(root_provide, prefill)

    # Data sent to the generator
    data = None

    def indent(depth, msg=""):
        prefix = "".join(repeat("  ", depth))
        return prefix + msg

    while True:

        try:
            if data is None:
                (provide, step, args) = generator.next()
            else:
                (provide, step, args) = generator.send(data)
                data = None
            if isinstance(args, SmartException):
                logger.error("%s: %s" % (args.name, args.message))
        except StopIteration:
            break

        if provide is None and step is None:
            if output_file:
                with open(output_file, 'w') as fp:
                    json.dump(args, fp, indent=2)
                    logger.info("Deployment values written in %s" % output_file)
            break

        if provide.tree_id is None:
            pass
#        print "%s [%s %s] " % (provide.generic_xpath.ljust(60+2*provide.depth),
#                               provide.step.ljust(16), provide.tree_id)

        if provide.step == "manage":
            if manage:
                data = True
            else:
                data = user_input_confirm(
                    indent(provide.depth,
                           "Do you want to configure and call '%s' [Y/n]? " % provide.generic_xpath))

        elif provide.step == "lfm":
            msg = "You have to set a location:"
            if provide.lfm_host is not None:
                prefill = show_variable(provide.lfm_host)
            elif provide.has_requirer():
                prefill = show_variable(provide.requirer.lfm_host)
            else:
                prefill = ""
            # If the provide can list possible locations
            if hasattr(provide, "list_locations"):
                locations = provide.list_locations()
                data = user_input_choose_amongst(locations,
                                                 "Choose between available locations",
                                                 prefix=indent(provide.depth))
            else:
                host = user_input_variable(variable_name="location", message=msg, prefix=indent(provide.depth), prefill=prefill)
                data = host['location']

        elif provide.step == "specialize":
            xpaths = []
            for arg in args:
                if 'extra' in arg and 'label' in arg['extra']:
                    label = '%s %s(%s)%s' % (arg['extra']['label'], COLOR_SEQ % CYAN, arg['xpath'], RESET_SEQ)
                else:
                    label = arg['xpath']
                xpaths.append({'value': arg['xpath'], 'label': label})
            data = user_input_choose_amongst(xpaths,
                                             "Which provide do you want to call",
                                             prefix=indent(provide.depth))

        elif provide.step == "validation":
            if provide.variables() != []:
                logger.info(indent(provide.depth, "Variables are:"))

                def xpathOrNone(var):
                    if var is not None:
                        return var.xpath
                    else:
                        return None

                for v in provide.variables():
                    logger.debug("\tXpath          : %s" % v.xpath)
                    logger.debug("\tValue          : %s" % v.value)
                    logger.debug("\tValueResolved  : %s" % v.value_resolved)
                    logger.debug("\tDefault        : %s" % v.default)
                    logger.debug("\tDefaultResolved: %s" % v.default_resolved)
                    logger.debug("\tResolvedBy     : %s" % xpathOrNone(v._resolved_by))
                    logger.debug("\tSetBy          : %s" % xpathOrNone(v._set_by))
                    logger.debug("\tSuggestedBy    : %s %s" % (xpathOrNone(v._suggested_by), v.value_get_one()))
                    logger.info(indent(provide.depth, "\t%s : %s [%s]" % (v.name.ljust(25), str(v.value_get_one()).ljust(25), v.xpath)))

                if provide.variables_scope() != []:
                    logger.info(indent(provide.depth, "Variables scope is:"))

                for v in provide.variables_scope():
                    logger.info(indent(provide.depth, "\t%s : %s [%s]" % (v.name.ljust(25), str(v.value_get_one()).ljust(25), v.xpath)))

                for v in provide.variables():
                    if v.value is None or v.error is not None:
                        # The user has to manually fill the variable
                        if autofill is False or v.value_get_one() is None or v.error is not None:
                            message = "Fill the variable %s (suggested value '%s')" % (v.xpath, v.value_get_one())
                            if v.error:
                                message = "Variable %s=%s doesn't validate : %s" % (v.xpath, v.value, v.error)
                            ret = user_input_variable(variable_name=v.name,
                                                      prefix=indent(provide.depth),
                                                      message=message,
                                                      prefill=show_variable(v.value_get_one()))
                            v.value = ret[v.name]
                            if v.error:
                                break
                        # The value is auto filled.
                        else:
                            v.value = v.value_get_one()
                        logger.info("Variable '%s' set with value '%s'" % (v.xpath, v.value))

                logger.debug("Serialized variables:")
                serialized = provide.variables_serialized()
                logger.debug("\t%s" % str(serialized[1]))
                for v in serialized[0]:
                    logger.debug("\t%s" % str(v))

                # send variables for validation
                data = serialized[0]

        elif provide.step == "multiplicity":
            require = args
            while True:
                answer = raw_input(indent(provide.depth, "How many time to call %s? " % require.skel.provide_xpath))
                try:
                    answer = int(answer)
                    break
                except Exception as e:
                    print e
                    print indent(provide.depth, "Invalid choice. Do it again!")
            data = answer

            adresses = []
            if require.skel.type == 'external':
                for i in range(0, data):
                    tmp_var = "host[%d]" % i
                    adresses.append(user_input_variable(variable_name=tmp_var,
                                                        message=indent(provide.depth, "What is adress of node %s? " % i))[tmp_var])
                data = adresses

        elif provide.step == "call":
            data = user_input_confirm(indent(provide.depth, "Call %s [Y/n]?" % provide.generic_xpath))
