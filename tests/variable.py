import unittest

from mss.variable import VList, VString, VInt, VBool, VFloat, Port, Hostname
from mss.common import ValidationError


class TestVariable(unittest.TestCase):

    def test_VString(self):
        t = VString("str1", default="default1")
        self.assertEqual(t.value, "default1")
        self.assertEqual(str(t), "default1")
        t.value = 1
        self.assertEqual(t.value, "1")
        t.fill(45)
        self.assertEqual(t.value, "45")
        t.value = "default2"
        self.assertEqual(t.value, "default2")
        t.fill("default3")
        self.assertEqual(t.value, "default3")

    def test_VInt(self):
        t = VInt("int", default=10)
        self.assertEqual(t.value, 10)
        self.assertEqual(int(t), 10)
        with self.assertRaises(ValidationError):
            t.value = "foo"
        with self.assertRaises(ValidationError):
            t.fill("foo")
        t.value = 20
        self.assertEqual(t.value, 20)
        t.fill(30)
        self.assertEqual(t.value, 30)

    def test_VFloat(self):
        t = VFloat("float", default=10.2)
        self.assertEqual(t.value, 10.2)
        self.assertEqual(float(t), 10.2)
        with self.assertRaises(ValidationError):
            t.value = "foo"
        with self.assertRaises(ValidationError):
            t.fill("foo")
        t.value = 20.4500
        self.assertEqual(t.value, 20.45)
        t.fill(30.4)
        self.assertEqual(t.value, 30.4)

    def test_VBool(self):
        t = VBool("bool1", default=False)
        with self.assertRaises(ValidationError):
            t.value = "foo"
        with self.assertRaises(ValidationError):
            t.value = 10
        t.value = True
        self.assertTrue(t.value)
        t.value = False
        self.assertFalse(t.value)
        t.fill(True)
        self.assertTrue(t.value)
        t.fill(False)
        self.assertFalse(t.value)

    def test_VList(self):
        t = VList("list1", inner=VString)
        t.value = [1]
        self.assertEqual(t.value[0].value, "1")
        t.fill([2])
        self.assertEqual(t.value[0].value, "2")
        # A correct data type can be set
        t.value = ["default1"]
        self.assertEqual(t.value[0].value, "default1")
        t.value[0].value = "default2"
        self.assertEqual(t.value[0].value, "default2")
        t.fill(["foo", "bar"])
        self.assertEqual(t.value[0].value, "foo")
        self.assertEqual(t.value[1].value, "bar")

    def test_VList_of_VList(self):
        t = VList("Vlist", inner=VList("innerVList", inner=VString))
        t.value = [["foo", "bar"], ["test", "str"]]
        t.value[0].value = ["v1", "v2"]
        self.assertEqual(t.value[0].value[0].value, "v1")
        self.assertEqual(t.value[0].value[1].value, "v2")
        self.assertEqual(t.value[1].value[0].value, "test")
        self.assertEqual(t.value[1].value[1].value, "str")
        t.fill([["str1"], ["str2", "str3"], ["str4"]])
        self.assertEqual(t.value[0].value[0].value, "str1")
        self.assertEqual(t.value[1].value[0].value, "str2")
        self.assertEqual(t.value[1].value[1].value, "str3")
        self.assertEqual(t.value[2].value[0].value, "str4")

    def test_required(self):
        t = VString("str")
        with self.assertRaises(ValidationError):
            t._validate()

    def test_max_min(self):
        t = Port("port")
        t.value = 300000
        with self.assertRaises(ValidationError):
            t._validate()
        t.value = -20
        with self.assertRaises(ValidationError):
            t._validate()

    def test_pattern(self):
        t = Hostname("host")
        t.value = "45"
        with self.assertRaises(ValidationError):
            t._validate()
        t.value = "test45"
        self.assertTrue(t._validate())


if __name__ == '__main__':
    unittest.main()
