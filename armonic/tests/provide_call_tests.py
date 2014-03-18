import unittest
import logging

from armonic.lifecycle import State, LifecycleManager, Lifecycle, Transition
from armonic.require import Require
from armonic.provide import Provide
from armonic.variable import VString
from armonic.common import ValidationError, ProvideError


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

    def test_provide_clear(self):
        self.lfm.state_goto("//ProvideCallLF/StateA")
        provide1 = self.lfm.from_xpath("//ProvideCallLF//provide1", ret="provide")
        enter = self.lfm.from_xpath("//ProvideCallLF/StateB/enter", ret="provide")
        print provide1
        self.assertEqual(provide1.foo1.variables().bar.value, None)
        self.assertEqual(enter.bar.variables().foo.value, None)
        self.assertEqual(self.lfm.provide_call("//ProvideCallLF//provide1",
                                               requires=[("//ProvideCallLF//bar/foo", "test1"), ("//ProvideCallLF//foo1/bar", "test1")]), (1, 2))
        self.assertEqual(provide1.foo1.variables().bar.value, None)
        self.assertEqual(enter.bar.variables().foo.value, None)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
