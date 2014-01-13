import logging
# import augeas


import mss.modules.shorewall.configuration
import mss.modules.apache.configuration
import mss.configuration_augeas

# mss.configuration_augeas.log_off()


print "Shorewall demo"
print "-----------"
s = mss.modules.shorewall.configuration.Shorewall(augeas_root="/tmp",
                                                  autoload=True)
print "Rules:"
for r in s.rules:
    print "\t", r.action
    print "\t", r.source

print "Log verbosity: %s" % s.logVerbosity.value
print "Log verbosity: %s" % s.logVerbosity.set("3")
s.save()

print "Log verbosity: %s (after saving)" % s.logVerbosity.value
print "Append a new rule ACCEPT lan0"
newRule = mss.modules.shorewall.configuration.Rule()
newRule.setRule("ACCEPT", "lan0")
s.rules.append(newRule)
s.save()

print "Apache demo"
print "-----------"
a = mss.modules.apache.configuration.Apache(augeas_root="/tmp",
                                            autoload=True)
print "Listen port %s " % a.port.value

print "VirutalHost:"
for v in a.virtualHosts:
    print "\t", v.path.value

print "Add a virtual host:"
a.addVirtualHost("/tmp/")
for v in a.virtualHosts:
    print "\t", v.path.value
a.save()
