import os
import unittest
import logging

from mss.lifecycle import State, LifecycleManager, Lifecycle, Transition
from mss.require import Require
from mss.variable import VString
from mss.common import ValidationError


class StateA(State):
    pass


class StateB(State):

    @Require('bar', [VString('foo')])
    def entry(self):
        pass

    @Require('foo1', [VString('bar')])
    def provide1(self, requires):
        return (1, 2)


class ProvideCallLF(Lifecycle):
    transitions = [Transition(StateA(), StateB())]

    def __init__(self):
        Lifecycle.__init__(self)
        self.init(StateA(), {})


class TestProvideCall(unittest.TestCase):

    def setUp(self):
        self.lfm = LifecycleManager(modules_dir=os.getcwd(), autoload=True, include_modules="")

    def test_missing_provide_arg(self):
        with self.assertRaisesRegexp(ValidationError, "Provided values doesn't met provide requires"):
            self.lfm.provide_call("//ProvideCallLF//provide1", requires=[("//ProvideCallLF//bar/foo", "test1")])

    def test_missing_require(self):
        with self.assertRaisesRegexp(ValidationError, "Provided values doesn't met provide requires"):
            self.lfm.provide_call("//ProvideCallLF//provide1", provide_args=[("//ProvideCallLF//foo1/bar", "test1")])

    def test_valid(self):
        self.assertEqual(self.lfm.provide_call("//ProvideCallLF//provide1", requires=[("//ProvideCallLF//bar/foo", "test1")], provide_args=[("//ProvideCallLF//foo1/bar", "test1")]), (1, 2))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
