import unittest
from mss.lifecycle import provide, Provide, RequireNotMatchPrototype
from mss.require import Requires, Require
from mss.variable import VInt
from mss.common import ValidationError


@provide(Requires([Require([VInt("arg1")], name="r1")]))
def provide1(self, arg1):
    pass
P = Provide(provide1)


class TestProvide(unittest.TestCase):
    def test_require(self):
        with self.assertRaises(ValidationError):
            P.build_args_from_primitive({'r1': {'arg': 1}})
        self.assertEqual(P.build_args_from_primitive({'r1': {'arg1': 1}}),
                         {'arg1': 1})

    def test_provide_decorator(self):
        with self.assertRaises(RequireNotMatchPrototype):
            @provide(Requires([Require([VInt("arg1")], name="r1")]))
            def provide2(self, arg1, arg2):
                pass

        @provide(Requires([Require([VInt("arg2"), VInt("arg1")], name="r1")]))
        def provide2(self, arg1, arg2):
            pass


if __name__ == '__main__':
    unittest.main()
