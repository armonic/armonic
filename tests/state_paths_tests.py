import unittest
import logging

from mss.lifecycle import Lifecycle, State, Transition, MetaState
from mss.utils import OsTypeDebian, OsTypeMBS, OS_TYPE


class a(State):
    pass


class b(State):
    pass


class c(State):
    pass


class d(State):
    pass


class e(State):
    pass


class f(State):
    pass


class g(State):
    pass


class i(State):
    supported_os_type = [OsTypeDebian()]


class j(State):
    supported_os_type = [OsTypeMBS()]


class h(MetaState):
    implementations = [i, j]


class TestPathGeneration(unittest.TestCase):

    def test_simple_path(self):
        """
        a -> b -> c -> d
        """
        class TestLifecycle(Lifecycle):
            initial_state = a()
            transitions = [
                Transition(a(), b()),
                Transition(b(), c()),
                Transition(c(), d())
            ]

        lf = TestLifecycle()
        self.assertEqual(lf._get_from_state_paths(a(), d()),
                         [[(b(), 'enter'), (c(), 'enter'), (d(), 'enter')]])
        self.assertEqual(lf._get_from_state_paths(b(), c()),
                         [[(c(), 'enter')]])
        lf.state_goto(d(), {})
        self.assertEqual(lf._get_from_state_paths(d(), a()),
                         [[(d(), 'leave'), (c(), 'leave'), (b(), 'leave')]])
        lf.state_goto(c(), {})
        self.assertEqual(lf._get_from_state_paths(c(), a()),
                         [[(c(), 'leave'), (b(), 'leave')]])
        self.assertEqual(lf._get_from_state_paths(a(), a()),
                         [])

    def test_multiple_paths(self):
        """
             b ------>
        a ->           e -> f
             c -> d ->
        """
        class TestLifecycle(Lifecycle):
            initial_state = a()
            transitions = [
                Transition(a(), b()),
                Transition(a(), c()),
                Transition(b(), e()),
                Transition(c(), d()),
                Transition(d(), e()),
                Transition(e(), f())
            ]

        lf = TestLifecycle()
        self.assertEqual(lf._get_from_state_paths(a(), f()),
                         [[(b(), 'enter'), (e(), 'enter'), (f(), 'enter')],
                          [(c(), 'enter'), (d(), 'enter'), (e(), 'enter'), (f(), 'enter')]])
        self.assertEqual(lf._get_from_state_paths(a(), d()),
                         [[(c(), 'enter'), (d(), 'enter')]])
        lf.state_goto(f(), {}, 1)
        self.assertEqual(lf._get_from_state_paths(f(), a()),
                         [[(f(), 'leave'), (e(), 'leave'), (d(), 'leave'), (c(), 'leave')]])
        lf.state_goto(a(), {})
        lf.state_goto(f(), {}, 0)
        self.assertEqual(lf._get_from_state_paths(f(), a()),
                         [[(f(), 'leave'), (e(), 'leave'), (b(), 'leave')]])

    def test_multiple_ends(self):
        """
        a -> b ->        -> f
                  d -> e
             c ->        -> g
        """
        class TestLifecycle(Lifecycle):
            initial_state = a()
            transitions = [
                Transition(a(), b()),
                Transition(c(), d()),
                Transition(b(), d()),
                Transition(d(), e()),
                Transition(e(), f()),
                Transition(e(), g())
            ]

        lf = TestLifecycle()
        self.assertEqual(lf._get_from_state_paths(a(), f()),
                         [[(b(), 'enter'), (d(), 'enter'), (e(), 'enter'), (f(), 'enter')]])
        self.assertEqual(lf._get_from_state_paths(c(), g()),
                         [[(d(), 'enter'), (e(), 'enter'), (g(), 'enter')]])
        lf.state_goto(g(), {})
        self.assertEqual(lf._get_from_state_paths(g(), a()),
                         [[(g(), 'leave'), (e(), 'leave'), (d(), 'leave'), (b(), 'leave')]])
        self.assertEqual(lf._get_from_state_paths(g(), c()),
                         [])

    def test_metastates(self):
        """
             i (debian) ->
        a ->               h (meta) -> g
             j (mbs)    ->
        """
        class TestLifecycle(Lifecycle):
            initial_state = a()
            transitions = [
                Transition(a(), h()),
                Transition(h(), g())
            ]

        OS_TYPE.name = "Mandriva Business Server"
        OS_TYPE.version = "1.0"
        lf = TestLifecycle()
        path = lf._get_from_state_paths(a(), g())[0]
        path = [(state.name, method) for state, method in path]
        self.assertEqual(path, [('h.j', 'enter'), ('h', 'enter'), ('g', 'enter')])

        OS_TYPE.name = "debian"
        OS_TYPE.version = "wheezy"
        lf = TestLifecycle()
        path = lf._get_from_state_paths(a(), g())[0]
        path = [(state.name, method) for state, method in path]
        self.assertEqual(path, [('h.i', 'enter'), ('h', 'enter'), ('g', 'enter')])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
