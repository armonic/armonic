import os
import unittest
import logging

from mss.lifecycle import State, LifecycleManager, Lifecycle, Transition
from mss.require import Require
from mss.provide import Provide
from mss.variable import VString
from mss.common import ValidationError, ProvideError


class StateA(State):
    pass


class StateB(State):

    @Require('bar', [VString('foo')])
    def enter(self, requires):
        pass

    @Require('foo1', [VString('bar')])
    def provide1(self, requires):
        return (1, 2)

    @Provide()
    def provide_error(self):
        raise Exception("some error")


class StateC(State):

    def enter(self):
        print self.bar


class ProvideCallLF(Lifecycle):
    initial_state = StateA()
    transitions = [Transition(StateA(), StateB()),
                   Transition(StateB(), StateC())]


class TestProvideCall(unittest.TestCase):

    def setUp(self):
        self.lfm = LifecycleManager()

    def test_missing_provide_arg(self):
        with self.assertRaisesRegexp(ValidationError, "Provided values doesn't met provide requires"):
            self.lfm.provide_call("//ProvideCallLF//provide1",
                                  requires=[("//ProvideCallLF//bar/foo", "test1")])

    def test_missing_require(self):
        with self.assertRaisesRegexp(ValidationError, "Provided values doesn't met provide requires"):
            self.lfm.provide_call("//ProvideCallLF//provide1",
                                  requires=[("//ProvideCallLF//foo1/bar", "test1")])

    def test_valid(self):
        self.assertEqual(self.lfm.provide_call("//ProvideCallLF//provide1",
                                               requires=[("//ProvideCallLF//bar/foo", "test1"), ("//ProvideCallLF//foo1/bar", "test1")]), (1, 2))

    def test_provide_exception(self):
        with self.assertRaisesRegexp(ProvideError, 'some error'):
            self.lfm.provide_call("//ProvideCallLF//provide_error",
                                  requires=[("//ProvideCallLF//bar/foo", "test1")])

    def test_enter_exception(self):
        with self.assertRaisesRegexp(ProvideError, 'object has no attribute'):
            self.lfm.state_goto("//ProvideCallLF/StateC",
                                requires=[("//ProvideCallLF//bar/foo", "test1")])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
