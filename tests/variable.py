import unittest
#import mss.common
#mss.common.log_disable_stdout()

from mss.variable import *

v1=VString("v1",default="value1")
v2=VString("v2",default="value2")

class TestVariable(unittest.TestCase):
    def test_VString(self):
        t=VString("str1",default="default1")
        self.assertEqual(t.value , "default1")
        with self.assertRaises(TypeError):
            t.value=1
        t.value="default2"
        self.assertEqual(t.value , "default2")

        t.fill("default3")

    def test_VList(self):
        t=VList("list1",inner=VString)
        # Type of a inner value is verified
        with self.assertRaises(TypeError):
            t.value=[1]
        # A correct data type can be set
        t.value=["default1"]
        self.assertEqual(t.value[0].value,"default1")
        t.value[0].value="default2"
        self.assertEqual(t.value[0].value,"default2")
        
    def test_VList_of_VList(self):
        t=VList("Vlist",inner=VList("innerVList",inner=VString))
        t.value=[["iop"]]
        t.value[0].value=["v1","v2"]
        print t.value[0].value
        self.assertEqual(t.value[0].value,["v1","v1"])

    def test_fill_VString(self):
        t=VString("str1")
        t.fill("iop")

    def test_fill_VList(self):
        t=VList("list1",inner=VString)
        t.fill(["iop1","iop2"])

    def test_required(self):
        t=VString("str")
        with self.assertRaises(ValidationError):
            t._validate()
        t=Port("port")
        with self.assertRaises(ValidationError):
            t._validate()
        
        


if __name__ == '__main__':
    unittest.main()

exit(1)
