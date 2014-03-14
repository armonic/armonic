#!/bin/sh

python=python
[ -x /usr/bin/python2 ] && python=python2

${python} -m unittest discover armonic/tests -v '*_tests.py'
