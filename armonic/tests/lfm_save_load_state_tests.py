import unittest
import logging
import tempfile

from armonic import State, LifecycleManager, Lifecycle, Transition, \
                    MetaState, Require
from armonic.persist import Persist
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

    def setUp(self):
        self.pconfig = Persist(save_state=True)

    def test_save_load(self):
        fh, state_path = tempfile.mkstemp(suffix="_%s%s")
        self.pconfig.load_state = False
        self.pconfig.save_state = True
        self.pconfig.state_path = state_path
        lfm = LifecycleManager()
        lfm.state_goto("//LFMStateLoad/StateC", requires=[[('//LFMStateLoad//bar/foo', 'test')]])
        self.pconfig.save()
        self.pconfig.ressources = []
        self.pconfig.load_state = True
        self.pconfig.save_state = False
        lfm = LifecycleManager()
        self.assertEqual(lfm.state_current('//LFMStateLoad')[0].name, "StateC")

    def test_metastate(self):
        fh, state_path = tempfile.mkstemp(suffix="%s%s")
        self.pconfig.load_state = False
        self.pconfig.save_state = True
        self.pconfig.state_path = state_path
        lfm = LifecycleManager()
        lfm.state_goto("//LFMStateLoad/StateE", requires=[[('//LFMStateLoad//bar/foo', 'test1'),
                                                           ('//LFMStateLoad//foo/bar', 'test2')]])
        self.pconfig.save()
        self.pconfig.ressources = []
        self.pconfig.load_state = True
        self.pconfig.save_state = False
        self.pconfig.save()
        lfm = LifecycleManager()
        self.assertEqual(lfm.state_current('//LFMStateLoad')[0].name, "StateE")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
