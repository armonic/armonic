import unittest
import logging

from mss.lifecycle import State, Lifecycle, Transition
from mss.provide import Flags, Provide
from mss.common import ProvideError


class StateA(State):

    @Flags(reload=True)
    def provide_flag(self):
        return True

    @Flags(reload=True, foo="bar")
    def provide_flag2(self, requires):
        return False

    @Provide()
    def provide_noflag(self):
        return 12


class StateB(State):

    def cross(self, reload=False):
        self.reload = reload


class StateC(State):
    pass


class ProvideFlagsLF(Lifecycle):
    initial_state = StateA()
    transitions = [Transition(StateA(), StateB()),
                   Transition(StateB(), StateC())]


class TestProvideFlags(unittest.TestCase):

    def setUp(self):
        self.lf = ProvideFlagsLF()

    def test_provide_flags(self):
        self.lf.state_goto(StateB())
        self.assertEqual(self.lf.state_current(), StateB())
        ret = self.lf.provide_call(StateA(), 'provide_flag')
        self.assertEqual(ret, True)
        self.assertEqual(StateB().reload, True)

    def test_cross_missing_flag(self):
        self.lf.state_goto(StateB())
        self.assertEqual(self.lf.state_current(), StateB())
        with self.assertRaisesRegexp(ProvideError, 'takes exactly 2 arguments'):
            self.lf.provide_call(StateA(), 'provide_flag2')

    def test_cross_no_flag(self):
        self.lf.state_goto(StateC())
        self.assertEqual(self.lf.state_current(), StateC())
        ret = self.lf.provide_call(StateA(), 'provide_noflag')
        self.assertEqual(ret, 12)
        self.assertEqual(StateB().reload, False)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
