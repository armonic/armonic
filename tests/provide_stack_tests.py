import unittest
import logging

from armonic.lifecycle import State
from armonic.provide import Flags, Provide
from armonic.require import Require
from armonic.variable import VString


class StateA(State):

    @Flags(reload=True, foo="bar")
    @Require('bar', [VString('foo')])
    @Provide()
    @Flags(restart=False)
    @Require('foo', [VString('bar', default='bar')])
    def enter(self):
        return True


class TestProvideStack(unittest.TestCase):

    def test_provide(self):
        state = StateA()
        provide = state.provide_enter
        self.assertEqual(provide.name, 'enter')
        self.assertEqual(provide.flags, {'reload': True, 'restart': False, 'foo': 'bar'})
        self.assertEqual(provide.bar.variables().foo.value, None)
        self.assertEqual(provide.foo.variables().bar.value, 'bar')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
