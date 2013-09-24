import unittest

from mss.variable import VList, VString, VInt


class TestVariable(unittest.TestCase):

    def test_VString(self):
        t = VString("str1", default="default1")
        self.assertEqual(t.value, "default1")
        self.assertEqual(str(t), "default1")
        with self.assertRaises(TypeError):
            t.value = 1
        with self.assertRaises(TypeError):
            t.fill(1)
        t.value = "default2"
        self.assertEqual(t.value, "default2")
        t.fill("default3")
        self.assertEqual(t.value, "default3")

    def test_VInt(self):
        t = VInt("int&", default=10)
        self.assertEqual(t.value, 10)
        self.assertEqual(int(t), 10)
        with self.assertRaises(TypeError):
            t.value = "foo"
        with self.assertRaises(TypeError):
            t.fill("foo")
        t.value = 20
        self.assertEqual(t.value, 20)
        t.fill(30)
        self.assertEqual(t.value, 30)

    def test_VList(self):
        t=VList("list1", inner=VString)
        # Type of a inner value is verified
        with self.assertRaises(TypeError):
            t.value = [1]
        with self.assertRaises(TypeError):
            t.fill([1])
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
        t=VString("str")
        with self.assertRaises(ValidationError):
            t._validate()
        t=Port("port")
        with self.assertRaises(ValidationError):
            t._validate()
        
        


if __name__ == '__main__':
    unittest.main()
