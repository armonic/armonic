import unittest
import mss.common
mss.common.log_disable_stdout()

import mss.lifecycle
import mss.require


class S1(mss.lifecycle.State):
    pass


class S2(mss.lifecycle.State):
    @mss.lifecycle.provide()
    def p1_s2(self):
        return "ret_p1_s2"


class S3(mss.lifecycle.State):
    pass


class S4(mss.lifecycle.State):
    pass


class S5(mss.lifecycle.State):
    pass


class Simple(mss.lifecycle.Lifecycle):
    transitions = [
        mss.lifecycle.Transition(S1(), S2()),
        mss.lifecycle.Transition(S2(), S3()),
        mss.lifecycle.Transition(S3(), S4()),
        ]

    def __init__(self):
        self.init(S1(), {})


class Teststate_goto(unittest.TestCase):
    def setUp(self):
        self.lf = Simple()

    def test_state_goto_path(self):
        lf = Simple()
        path = lf.state_goto_path("S4")
        self.assertEqual(path, [(S2(), "entry"),
                                (S3(), "entry"),
                                (S4(), "entry")])
        lf.state_goto(S4, {})
        self.assertEqual(lf.state_goto_path(S1),
                         [(S4(), "leave"),
                          (S3(), "leave"),
                          (S2(), "leave")])
        self.assertEqual(lf.state_goto_path(S1, go_back=False), [])

    def test_state_goto(self):
        lf = Simple()
        lf.state_goto(S4, {})
        path = lf.state_goto_path(S1)
        self.assertEqual(path, [(S4(), "leave"),
                                (S3(), "leave"),
                                (S2(), "leave")])

    def test_idempotence(self):
        lf = Simple()
        lf.state_goto(S4, {})
        self.assertEqual(lf.state_goto_path(S4), [])

    def test_state_goto_pathBack(self):
        self.lf.state_goto(S4, {"r1_s2": "value_r1_s2"})
        self.assertEqual(self.lf.state_current(), S4())
        self.lf.state_goto(S3, {})
        self.assertEqual(self.lf.state_current(), S3())


class C1(mss.lifecycle.State):
    pass


class C2(mss.lifecycle.State):
    requires = [mss.require.Require([mss.require.VString("r1_s2")])]

    @mss.lifecycle.provide()
    def p1_s2(self):
        return "ret_p1_s2"


class C3(mss.lifecycle.State):
    @mss.lifecycle.provide()
    def p_ambigous(self):
        return "p_ambigous_s3"


class C4(mss.lifecycle.State):
    @mss.lifecycle.provide()
    def p_ambigous(self):
        return "p_ambigous_s4"


class C5(mss.lifecycle.State):
    pass


class Complex(mss.lifecycle.Lifecycle):
    transitions = [
        mss.lifecycle.Transition(C1(), C2()),
        mss.lifecycle.Transition(C2(), C3()),
        mss.lifecycle.Transition(C3(), C4()),
        mss.lifecycle.Transition(C3(), C5()),
        ]

    def __init__(self):
        self.init(C1(), {})


class TestComplex(unittest.TestCase):
    def setUp(self):
        self.lf = Complex()

    def test_state_goto_path(self):
        path = self.lf.state_goto_path("C3")
        self.assertEqual(path, [(C2(), "entry"), (C3(), "entry")])

    def test_missing_require(self):
        with self.assertRaises(mss.require.MissingRequire):
            self.lf.state_goto(C4, {})
        self.assertEqual(self.lf.state_current(), C1())

    def test_list_provide(self):
        self.assertEqual(self.lf.provide_list()[0][1][0].name, "p1_s2")

    def test_state_goto_pathBack(self):
        self.lf.state_goto(C4, {'r1_s2': [{'r1_s2': "test"}]})
        path = self.lf.state_goto_path(C1)
        self.assertEqual(path, [(C4(), "leave"),
                                (C3(), "leave"),
                                (C2(), "leave")])
        path = self.lf.state_goto_path(C5)
        self.assertEqual(path, [(C4(), "leave"), (C5(), "entry")])
        self.lf.state_goto(C5, {})

    def test_provide_call(self):
        self.assertEqual(self.lf.provide_list()[0][1][0].name, "p1_s2")
        self.assertDictContainsSubset(
                    self.lf.provide_call_requires("p1_s2")[0].to_primitive(),
                    {'name': 'r1_s2',
                     'type': 'simple',
                     'args': [{'type': 'str', 'name': 'r1_s2'}]})

        self.assertEqual(self.lf.provide_call("p1_s2",
                                              {'r1_s2': [{'r1_s2': "test"}]},
                                              {}), "ret_p1_s2")
        self.assertEqual(self.lf.state_current(), C2())
        self.lf.state_goto(C4, {})
        self.assertEqual(self.lf.provide_call("p1_s2",
                                              {'r1_s2': [{'r1_s2': "test"}]},
                                              {}), "ret_p1_s2")
        self.assertEqual(self.lf.state_current(), C4())

    def test_provide_state_goto_path(self):
        self.assertEqual(self.lf.provide_call_path("p1_s2"), [(C2(), 'entry')])
        self.lf.state_goto(C3, {'r1_s2': [{'r1_s2': "test"}]})
        self.assertEqual(self.lf.provide_call_path("p1_s2"), [])

    def test_ambigous(self):
        with self.assertRaises(mss.lifecycle.ProvideAmbigous):
            self.lf.provide_call("p_ambigous", {"r1_s2": "value_r1_s2"}, {})
        self.assertEqual(self.lf.provide_call("C4.p_ambigous",
                                              {'r1_s2': [{'r1_s2':"test"}]},
                                              {}), "p_ambigous_s4")
        self.assertEqual(self.lf.state_current(), C4())


###############################################################################
# TEST REQUIRES
###############################################################################
class S_R0(mss.lifecycle.State):
    pass


class S_R1(mss.lifecycle.State):
    requires = [mss.require.Require([mss.require.VString("var_S_R1_1")])]


class S_R2(mss.lifecycle.State):
    requires = [mss.require.RequireExternal("module_S_R2",
                                            "provide_S_R2",
                                            [mss.require.VString("var_S_R2_1"),
                                             mss.require.VString("var_S_R2_1")
                                             ])]


class S_R3(mss.lifecycle.State):
    requires = [mss.require.RequireLocal("module_S_R3",
                                         "provide_S_R3",
                                         [mss.require.VString("var_S_R3_1")])]


class LF_Require(mss.lifecycle.Lifecycle):
    transitions = [
        mss.lifecycle.Transition(S_R0(), S_R1()),
        mss.lifecycle.Transition(S_R0(), S_R2()),
        mss.lifecycle.Transition(S_R0(), S_R3())
        ]

    def __init__(self):
        self.init(S_R0(), {})


class TestRequires(unittest.TestCase):

    def setUp(self):
        self.lf = LF_Require()

    def test_require_simple(self):
        with self.assertRaises(mss.require.MissingRequire):
            self.lf.state_goto("S_R1", {})
        self.assertDictContainsSubset(
                        self.lf.state_goto_requires("S_R1")[0].to_primitive(),
                        {'args': [{'name': 'var_S_R1_1', 'type': 'str'}],
                         'name': 'var_S_R1_1',
                         'type': 'simple'})

        self.lf.state_goto("S_R1", {"var_S_R1_1": [{"var_S_R1_1": "test"}]})
        self.assertEqual(self.lf.state_current(), S_R1())

    def test_require_external(self):
        with self.assertRaises(mss.require.MissingRequire):
            self.lf.state_goto("S_R2", {})
        self.assertEqual(self.lf.state_goto_requires("S_R2")[0].to_primitive(),
                         {'args': [{'name': 'var_S_R2_1', 'type': 'str'},
                                   {'name': 'var_S_R2_1', 'type': 'str'},
                                   {'name': 'host', 'type': 'host'}],
                          'module': 'module_S_R2',
                          'name': 'module_S_R2.provide_S_R2',
                          'provide': 'provide_S_R2',
                          'type': 'external'})

        self.lf.state_goto("S_R2",
                           {"module_S_R2.provide_S_R2":
                            [{'var_S_R2_1': 'test',
                              'var_S_R2_1': 'test2',
                              'host': 'test_host'}]})
        self.assertEqual(self.lf.state_current(), S_R2())

    def test_require_local(self):
        with self.assertRaises(mss.require.MissingRequire):
            self.lf.state_goto("S_R3", {})
        self.assertEqual(self.lf.state_goto_requires("S_R3")[0].to_primitive(),
                         {'args': [{'name': 'var_S_R3_1', 'type': 'str'}],
                          'module': 'module_S_R3',
                          'name': 'module_S_R3.provide_S_R3',
                          'provide': 'provide_S_R3',
                          'type': 'local'})
        self.lf.state_goto("S_R3",
                           {"module_S_R3.provide_S_R3":
                            [{'var_S_R3_1': 'test'}]})
        self.assertEqual(self.lf.state_current(), S_R3())


if __name__ == '__main__':
    unittest.main()

exit(1)
