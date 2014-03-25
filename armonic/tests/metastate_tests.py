import unittest
import logging

from armonic import Lifecycle, State, Transition, MetaState, Provide


logger = logging.getLogger()


class a(State):
    pass

class b(State):
    @Provide()
    def p():
        pass


class c(State):
    @Provide()
    def p():
        pass


class m1(MetaState):
    implementations = [b, c]


class m2(MetaState):
    implementations = [b, c]


class TestProvide(unittest.TestCase):

    def test_simple(self):
        """
           -> b.m1 -> m1
          /
        a
          \
           -> b.m2 -> m2
        """
        class TestLifecycle(Lifecycle):
            initial_state = a()
            transitions = [
                Transition(a(), m1()),
                Transition(a(), m2())
            ]

        lf = TestLifecycle()
        self.assertNotEqual(id(lf.state_by_name("m1.b").provide_by_name("p")),
                            id(lf.state_by_name("m2.b").provide_by_name("p")))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
