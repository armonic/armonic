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
                         [[(b(), 'entry'), (c(), 'entry'), (d(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(b(), c()),
                         [[(c(), 'entry')]])
        lf.state_goto(d(), {})
        self.assertEqual(lf._get_from_state_paths(d(), a()),
                         [[(d(), 'leave'), (c(), 'leave'), (b(), 'leave')]])
        lf.state_goto(c(), {})
        self.assertEqual(lf._get_from_state_paths(c(), a()),
                         [[(c(), 'leave'), (b(), 'leave')]])
        self.assertEqual(lf._get_from_state_paths(a(), a()),
                         [])

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
                         [[(b(), 'entry'), (e(), 'entry'), (f(), 'entry')],
                          [(c(), 'entry'), (d(), 'entry'), (e(), 'entry'), (f(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(a(), d()),
                         [[(c(), 'entry'), (d(), 'entry')]])
        lf.state_goto(f(), {}, 1)
        self.assertEqual(lf._get_from_state_paths(f(), a()),
                         [[(f(), 'leave'), (e(), 'leave'), (d(), 'leave'), (c(), 'leave')]])
        lf.state_goto(a(), {})
        lf.state_goto(f(), {}, 0)
        self.assertEqual(lf._get_from_state_paths(f(), a()),
                         [[(f(), 'leave'), (e(), 'leave'), (b(), 'leave')]])

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
                         [[(b(), 'entry'), (d(), 'entry'), (e(), 'entry'), (f(), 'entry')]])
        self.assertEqual(lf._get_from_state_paths(c(), g()),
                         [[(d(), 'entry'), (e(), 'entry'), (g(), 'entry')]])
        lf.state_goto(g(), {})
        self.assertEqual(lf._get_from_state_paths(g(), a()),
                         [[(g(), 'leave'), (e(), 'leave'), (d(), 'leave'), (b(), 'leave')]])
        # NOT SUPPORTED
        #lf.state_goto(g(), {})
        #self.assertEqual(lf._get_from_state_paths(g(), c()),
                         #[[(g(), 'leave'), (e(), 'leave'), (d(), 'leave')]])

if __name__ == '__main__':
    unittest.main()
