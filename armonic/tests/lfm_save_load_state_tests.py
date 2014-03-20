import unittest
import logging
import tempfile

from armonic import State, LifecycleManager, Lifecycle, Transition, \
                    MetaState, Require
from armonic.variable import VString


class StateA(State):
    pass


class StateB(State):

    @Require('bar', [VString('foo')])
    def enter(self, requires):
        pass


class StateC(State):
    pass


class StateD(State):

    @Require('foo', [VString('bar')])
    def enter(self, requires):
        pass


class StateE(MetaState):
    implementations = [StateD]


class LFMStateLoad(Lifecycle):
    initial_state = StateA()
    transitions = [Transition(StateA(), StateB()),
                   Transition(StateB(), StateC()),
                   Transition(StateC(), StateE())]


class TestLFMStateLoad(unittest.TestCase):

    def test_save_load(self):
        fh, state_file = tempfile.mkstemp()
        lfm = LifecycleManager(load_state=False, state_file=state_file)
        lfm.state_goto("//LFMStateLoad/StateC", requires=[('//LFMStateLoad//bar/foo', 'test')])
        lfm.close()
        lfm = LifecycleManager(state_file=state_file)
        self.assertEqual(lfm.state_current('//LFMStateLoad')[0].name, "StateC")

    def test_metastate(self):
        fh, state_file = tempfile.mkstemp()
        with LifecycleManager(load_state=False, state_file=state_file) as lfm:
            lfm.state_goto("//LFMStateLoad/StateE", requires=[('//LFMStateLoad//bar/foo', 'test1'),
                                                              ('//LFMStateLoad//foo/bar', 'test2')])
        lfm = LifecycleManager(state_file=state_file)
        self.assertEqual(lfm.state_current('//LFMStateLoad')[0].name, "StateE")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
