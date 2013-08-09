from mss.configuration_augeas import *


class Action(Node):
    label="action"

class Rule(Node):
    action=Action
    source=Child("Source",label="source")
    
    def setRule(self,action,source):
        self.action.value=action
        self.source.value=source

class Rules(Nodes):
    label="directive"
    cls=Rule
    baseXpath="/files/etc/shorewall/rules"

class LogVerbosity(Node):
    label="LOG_VERBOSITY"
    baseXpath="/files/etc/shorewall/shorewall.conf/"


class Shorewall(Configuration):
    rules=Rules
    logVerbosity=LogVerbosity
    lenses={"Shorewall":["/etc/shorewall/shorewall.conf"],
            "ShorewallRules":["/etc/shorewall/rules"]}

