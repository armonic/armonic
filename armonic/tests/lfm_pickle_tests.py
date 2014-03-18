import unittest
import logging
import pickle

from armonic import State, LifecycleManager, Lifecycle, Transition, \
                    MetaState, Require
from armonic.variable import VString
from armonic.common import ValidationError


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
    implementations = [StateD()]


class LFMPickle(Lifecycle):
    initial_state = StateA()
    transitions = [Transition(StateA(), StateB()),
                   Transition(StateB(), StateC()),
                   Transition(StateC(), StateE())]


class TestLFMPickle(unittest.TestCase):

    def test_states(self):
        lfm = LifecycleManager()
        lfm.state_goto("//LFMPickle/StateC", requires=[('//LFMPickle//bar/foo', 'test')])
        state = pickle.dumps(lfm)
        lfm_pickle = pickle.loads(state)
        self.assertEqual(lfm_pickle.state_current('//LFMPickle')[0].name,
                         lfm.state_current('//LFMPickle')[0].name)
        self.assertEqual(lfm_pickle.state_current('//LFMPickle')[0].name,
                         lfm.state_current('//LFMPickle')[0].name)
        lfm_pickle.state_goto("//LFMPickle/StateA")
        self.assertEqual(lfm_pickle.state_current('//LFMPickle')[0].name, "StateA")

    def test_validation_error(self):
        lfm = LifecycleManager()
        try:
            lfm.state_goto("//LFMPickle/StateC")
        except ValidationError:
            pass
        state = pickle.dumps(lfm)
        lfm_pickle = pickle.loads(state)
        self.assertEqual(lfm_pickle.from_xpath('//LFMPickle//bar/foo', ret="variable").error, "foo is required")

    def test_metastate(self):
        lfm = LifecycleManager()
        lfm.state_goto("//LFMPickle/StateE", requires=[('//LFMPickle//bar/foo', 'test1'),
                                                       ('//LFMPickle//foo/bar', 'test2')])
        state = pickle.dumps(lfm)
        lfm_pickle = pickle.loads(state)
        self.assertEqual(lfm_pickle.state_current('//LFMPickle')[0].name, "StateE")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
