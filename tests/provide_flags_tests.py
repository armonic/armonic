import unittest
import logging

from mss.lifecycle import State, Lifecycle, Transition
from mss.provide import Flags


class StateA(State):

    @Flags(reload=True)
    def provideFlag(self, requires):
        return True

    @Flags(reload=True, foo="bar")
    def provideFlag2(self, requires):
        return False


class StateB(State):

    def cross(self, reload=False):
        self.reload = reload


class ProvideFlagsLF(Lifecycle):
    initial_state = StateA()
    transitions = [Transition(StateA(), StateB())]


class TestProvideFlags(unittest.TestCase):

    def setUp(self):
        self.lf = ProvideFlagsLF()

    def test_provide_flags(self):
        self.lf.state_goto(StateB())
        self.assertEqual(self.lf.state_current(), StateB())
        ret = self.lf.provide_call(StateA(), 'provideFlag')
        self.assertEqual(ret, True)
        self.assertEqual(StateB().reload, True)

    def test_cross_missing_flag(self):
        self.lf.state_goto(StateB())
        self.assertEqual(self.lf.state_current(), StateB())
        with self.assertRaises(TypeError):
            self.lf.provide_call(StateA(), 'provideFlag2')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
