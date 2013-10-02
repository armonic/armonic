import unittest
from mss.require import Requires, Require
from mss.variable import VInt
from mss.common import ValidationError


R1=Requires([Require([VInt("arg1")],name="r1")])
R2=Requires([Require([VInt("arg1"), VInt("arg2")],name="r1")])

class TestRequires(unittest.TestCase):
    def test_has_variable(self):
        self.assertTrue(R1.has_variable("arg1"))
        self.assertFalse(R1.has_variable("arg2"))

        self.assertTrue(R2.has_variable("arg2"))
        self.assertTrue(R2.has_variable("arg1"))

if __name__ == '__main__':
    unittest.main()
