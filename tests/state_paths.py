import unittest

from mss.lifecycle import Lifecycle, State, Transition


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


class TestPathGeneration(unittest.TestCase):

    def test01(self):
        """
        a -> b -> c -> d
        """
        class TestLifecycle(Lifecycle):
            transitions = [
                Transition(a(), b()),
                Transition(b(), c()),
                Transition(c(), d())
            ]

            def __init__(self):
                self.init(a(), {})

        lf = TestLifecycle()
        self.assertEqual(lf._get_from_state_paths(a(), d()),
                         [[(a(), 'leave'), (b(), 'entry'), (c(), 'entry'), (d(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(b(), c()),
                         [[(b(), 'leave'), (c(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(d(), a()),
                         [[(d(), 'leave'), (c(), 'leave'), (b(), 'leave'), (a(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(c(), a()),
                         [[(c(), 'leave'), (b(), 'leave'), (a(), 'entry')]])

    def test02(self):
        """
             b ------>
        a ->           e -> f
             c -> d ->
        """
        class TestLifecycle(Lifecycle):
            transitions = [
                Transition(a(), b()),
                Transition(a(), c()),
                Transition(b(), e()),
                Transition(c(), d()),
                Transition(d(), e()),
                Transition(e(), f())
            ]

            def __init__(self):
                self.init(a(), {})

        lf = TestLifecycle()
        self.assertEqual(lf._get_from_state_paths(a(), f()),
                         [[(a(), 'leave'), (b(), 'entry'), (e(), 'entry'), (f(), 'entry')],
                          [(a(), 'leave'), (c(), 'entry'), (d(), 'entry'), (e(), 'entry'), (f(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(a(), d()),
                         [[(a(), 'leave'), (c(), 'entry'), (d(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(e(), a()),
                         [[(e(), 'leave'), (b(), 'leave'), (a(), 'entry')],
                          [(e(), 'leave'), (d(), 'leave'), (c(), 'leave'), (a(), 'entry')]])

    def test03(self):
        """
        a -> b ->        -> f
                  d -> e
             c ->        -> g
        """
        class TestLifecycle(Lifecycle):
            transitions = [
                Transition(a(), b()),
                Transition(c(), d()),
                Transition(b(), d()),
                Transition(d(), e()),
                Transition(e(), f()),
                Transition(e(), g())
            ]

            def __init__(self):
                self.init(a(), {})

        lf = TestLifecycle()
        self.assertEqual(lf._get_from_state_paths(a(), f()),
                         [[(a(), 'leave'), (b(), 'entry'), (d(), 'entry'), (e(), 'entry'), (f(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(c(), g()),
                         [[(c(), 'leave'), (d(), 'entry'), (e(), 'entry'), (g(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(g(), a()),
                         [[(g(), 'leave'), (e(), 'leave'), (d(), 'leave'), (b(), 'leave'), (a(), 'entry')]])

if __name__ == '__main__':
    unittest.main()
