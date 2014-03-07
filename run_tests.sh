#!/bin/sh

python=python
[ -x /usr/bin/python2 ] && python=python2

${python} -m unittest discover tests '*_tests.py'
