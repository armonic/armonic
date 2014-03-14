import os
import unittest
import logging

from armonic.lifecycle import State, LifecycleManager, Lifecycle, Transition
from armonic.require import Require
from armonic.provide import Provide
from armonic.variable import VString, Hostname
from armonic.common import DoesNotExist
from armonic.xml_register import XpathMultipleMatch


class StateA(State):
    pass


class StateB(State):

    @Require('bar', [VString('foo')])
    def enter(self):
        pass

    @Provide()
    def provide(self, requires):
        pass

    @Require('foo1', [VString('bar')])
    def provide1(self, requires):
        pass

    @Require('foo2', [VString('bar1'), VString('bar2')])
    def provide2(self, requires):
        pass

    @Require('foo3', [VString('bar1')])
    @Require('bar3', [VString('foo1')])
    def provide3(self, requires):
        pass

    @Require('foo4', [Hostname('host4')])
    def provide4(self, requires):
        pass

    @Require('foo5', [VString('bar5')], nargs="*")
    def provide5(self, requires):
        pass

    @Require('foo6', [VString('bar6')], nargs="2")
    def provide6(self, requires):
        pass

    @Require('foo7', [VString('bar7')], nargs="?")
    def provide7(self, requires):
        pass

    @Require('foo8', [VString('bar')])
    @Require('bar8', [VString('bar')])
    def provide8(self, requires):
        pass


class ProvideValidationLF(Lifecycle):
    initial_state = StateA()
    transitions = [Transition(StateA(), StateB())]


class TestProvideValidation(unittest.TestCase):

    def setUp(self):
        self.lfm = LifecycleManager(modules_dir=os.getcwd(), autoload=True, include_modules="")

    def test_no_require_provide(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1")])
        self.assertFalse(validation['errors'])

    def test_missing_provide_arg(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide1",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1")])
        self.assertTrue(validation['errors'])
        self.assertFalse(validation['requires'].enter.bar.variables().foo.error)
        self.assertEqual(validation['requires'].provide1.foo1.variables().bar.error, 'bar is required')

    def test_missing_require(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide1",
                                                    requires=[("//ProvideValidationLF//foo1/bar", "test1")])
        self.assertTrue(validation['errors'])
        self.assertEqual(validation['requires'].enter.bar.variables().foo.error, 'foo is required')
        self.assertFalse(validation['requires'].provide1.foo1.variables().bar.error)

    def test_valid(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide1",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo1/bar", "test1")])
        self.assertEqual(validation['requires'].provide1.foo1.variables().bar.error, None)
        self.assertEqual(validation['requires'].enter.bar.variables().foo.error, None)
        self.assertFalse(validation['errors'])

    def test_multiple_variables(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide2",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo2/bar1", "test1")])
        self.assertTrue(validation['errors'])
        self.assertEqual(validation['requires'].provide2.foo2.variables().bar2.error, 'bar2 is required')
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide2",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo2/bar2", "test1")])
        self.assertTrue(validation['errors'])
        self.assertEqual(validation['requires'].provide2.foo2.variables().bar1.error, 'bar1 is required')
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide2",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo2/bar2", "test1"),
                                                              ("//ProvideValidationLF//foo2/bar1", "test2")])
        self.assertFalse(validation['errors'])

    def test_multiple_requires(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide3",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo3/bar1", "test1")])
        self.assertTrue(validation['errors'])
        self.assertEqual(validation['requires'].provide3.bar3.variables().foo1.error, 'foo1 is required')
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide3",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo3/bar1", "test1"),
                                                              ("//ProvideValidationLF//bar3/foo1", "test2")])
        self.assertFalse(validation['errors'])

    def test_custom_validation(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide4",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo4/host4", "44")])
        self.assertTrue(validation['errors'])
        self.assertIn('Incorrect Hostname', validation['requires'].provide4.foo4.variables().host4.error)
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide4",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo4/host4", "myhost33")])
        self.assertFalse(validation['errors'])

    def test_nargs_unlimited(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide5",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo5/bar5", {0: "test1", 1: "test2"})])
        self.assertFalse(validation['errors'])
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide5",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo5/bar5", "test1")])
        self.assertFalse(validation['errors'])
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide5",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1")])
        self.assertFalse(validation['errors'])

    def test_nargs_fixed(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide6",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1")])
        self.assertTrue(validation['errors'])
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide6",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo6/bar6", "test1")])
        self.assertTrue(validation['errors'])
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide6",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo6/bar6", {0: "test1", 1: "test2"})])
        self.assertFalse(validation['errors'])
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide6",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo6/bar6", {0: "test1", 1: "test2", 2: "test3"})])
        # "//ProvideValidationLF//foo6[3]/bar6" is ignored
        with self.assertRaises(DoesNotExist):
            validation['requires'].provide6.foo6.variables(2)
        self.assertFalse(validation['errors'])

    def test_nargs_zero_or_one(self):
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide7",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1")])
        self.assertFalse(validation['errors'])
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide7",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo7/bar7", "test1")])
        self.assertFalse(validation['errors'])
        validation = self.lfm.provide_call_validate("//ProvideValidationLF//provide7",
                                                    requires=[("//ProvideValidationLF//bar/foo", "test1"),
                                                              ("//ProvideValidationLF//foo7/bar7", {0: "test1", 1: "test2"})])
        with self.assertRaises(DoesNotExist):
            validation['requires'].provide7.foo7.variables(2)
        self.assertFalse(validation['errors'])

    def test_variable_path_ambigious(self):
        with self.assertRaises(XpathMultipleMatch):
            self.lfm.provide_call_validate("//ProvideValidationLF//provide8",
                                           requires=[("//ProvideValidationLF//foo", "test1"),
                                                     ("//ProvideValidationLF//bar", "test1")])

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
