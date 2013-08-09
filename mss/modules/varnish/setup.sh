#!/bin/bash

# Takes as input a list of backend separated by commas and a listening port.
# Format of list of backend is ip1:port1,ip2:port2,...
# Note that port is optionnal. Default port is 8080
# FIXME It also add a secret file.

backend=$1
port=$2
varnish_conf_file="/etc/varnish/default.vcl"
varnish_general_conf_file="/etc/varnish/varnish.params"

# Define the list of backends (web servers).
# Port 80 Backend Servers
echo "Generate" ${varnish_conf_file} "file"
echo "#Generated by Aeolus" > ${varnish_conf_file}
i=1
for b in `echo $backend | tr "," " "`  ; do
    b_host=`echo $b | cut -d":" -f1`
    b_port=`echo $b | cut -d":" -f2 -s`
    if [ $b_port ] ; then
	true
    else
	b_port=8080
    fi
    echo "backend web${i} { .host = \"${b_host}\"; .port = \"${b_port}\";}" >> ${varnish_conf_file}
    i=$(($i + 1))
done

# Define the director that determines how to distribute incoming requests.
echo 'director default_director round-robin {' >> ${varnish_conf_file}
for (( j = 1 ; j < i ; j++ )) ; do
    echo "{ .backend = web${j}; }" >> ${varnish_conf_file}
done
echo "}" >> ${varnish_conf_file}

# Respond to incoming requests.
echo 'sub vcl_recv {  set req.backend = default_director;}' >> ${varnish_conf_file}

echo "Generate" "/etc/varnish/secret" "file"
echo "1111111111" > /etc/varnish/secret

echo "Set port in" ${varnish_general_conf_file}
sed -i "s/VARNISH_LISTEN_PORT=[0-9]\{0,6\}/VARNISH_LISTEN_PORT=${port}/" ${varnish_general_conf_file}
