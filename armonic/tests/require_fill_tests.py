import unittest
import logging
from platform import uname

from armonic.lifecycle import State, LifecycleManager, Lifecycle, Transition
from armonic.require import Require
from armonic.variable import VString


class StateA(State):

    @Require('require1', [VString('bar1'), VString('bar2')])
    def provide1(self):
        pass

    @Require('require22', [VString('bar221'), VString('bar222')])
    @Require('require21', [VString('bar211'), VString('bar212')])
    def provide2(self):
        pass

    @Require('require3', [VString('bar3')], nargs="*")
    def provide3(self):
        pass


class StateB(State):
    pass


class RequireFillFL(Lifecycle):
    initial_state = StateA()
    transitions = [Transition(StateA(), StateB())]


class TestProvideValidation(unittest.TestCase):

    def setUp(self):
        self.hostname = uname()[1]
        self.lfm = LifecycleManager(load_state=False)
        self.maxDiff = None

    def test_fill_simple_require(self):
        require = self.lfm.from_xpath('//RequireFillFL//require1', ret='require')
        values = [
            ('//RequireFillFL//require1/bar1', {0: 'test1'}),
            ('//RequireFillFL//require1/bar2', {0: 'test2'})
        ]
        require.fill(values)
        ret = [
            ['/%s/RequireFillFL/StateA/provide1/require1/bar1' % self.hostname, {0: 'test1'}],
            ['/%s/RequireFillFL/StateA/provide1/require1/bar2' % self.hostname, {0: 'test2'}]
        ]
        self.assertEqual(require.get_values(), ret)

    def test_fill_muliple_requires(self):
        provide = self.lfm.from_xpath('//RequireFillFL//provide2', ret='provide')
        values = [
            ('//RequireFillFL//require21/bar211', {0: 'test1'}),
            ('//RequireFillFL//require22/bar221', {0: 'test2'})
        ]
        provide.fill(values)
        ret = [
            ['/%s/RequireFillFL/StateA/provide2/require21/bar211' % self.hostname, {0: 'test1'}],
            ['/%s/RequireFillFL/StateA/provide2/require21/bar212' % self.hostname, {0: None}],
            ['/%s/RequireFillFL/StateA/provide2/require22/bar221' % self.hostname, {0: 'test2'}],
            ['/%s/RequireFillFL/StateA/provide2/require22/bar222' % self.hostname, {0: None}]
        ]
        self.assertEqual(provide.get_values(), ret)
        values = [
            ('//RequireFillFL//require21/bar212', {0: 'test11'}),
            ('//RequireFillFL//require22/bar222', {0: 'test22'})
        ]
        provide.fill(values)
        ret = [
            ['/%s/RequireFillFL/StateA/provide2/require21/bar211' % self.hostname, {0: 'test1'}],
            ['/%s/RequireFillFL/StateA/provide2/require21/bar212' % self.hostname, {0: 'test11'}],
            ['/%s/RequireFillFL/StateA/provide2/require22/bar221' % self.hostname, {0: 'test2'}],
            ['/%s/RequireFillFL/StateA/provide2/require22/bar222' % self.hostname, {0: 'test22'}]
        ]
        self.assertEqual(provide.get_values(), ret)

    def test_fill_nargs(self):
        provide = self.lfm.from_xpath('//RequireFillFL//provide3', ret='provide')
        values = [
            ('//RequireFillFL//require3/bar3', {0: 'test1', 1: 'test2', 2: 'test3'})
        ]
        provide.fill(values)
        ret = [
            ['/%s/RequireFillFL/StateA/provide3/require3/bar3' % self.hostname, {0: 'test1', 1: 'test2', 2: 'test3'}],
        ]
        self.assertEqual(provide.get_values(), ret)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
