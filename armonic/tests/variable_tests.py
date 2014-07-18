import unittest

from armonic.variable import VList, VString, VInt, VBool, VFloat, Port, Hostname
from armonic.common import ValidationError


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
        t.value = 20
        self.assertEqual(t.value, 20)
        t.fill(30)
        self.assertEqual(t.value, 30)
        with self.assertRaises(ValidationError):
            t.value = "foo"
            t.validate()
        with self.assertRaises(ValidationError):
            t.validate("bar")

    def test_VFloat(self):
        t = VFloat("float", default=10.2)
        self.assertEqual(t.value, 10.2)
        self.assertEqual(float(t), 10.2)
        t.value = 20.4500
        self.assertEqual(t.value, 20.45)
        t.fill(30.4)
        self.assertEqual(t.value, 30.4)
        with self.assertRaises(ValidationError):
            t.value = "foo"
            t.validate()
        with self.assertRaises(ValidationError):
            t.validate("bar")

    def test_VBool(self):
        t = VBool("bool1", default=False)
        for v in ('True', 'y', 'Y'):
            t.value = v
            self.assertTrue(t.value)
        for v in ('False', 'n', 'N'):
            t.value = v
            self.assertFalse(t.value)
        with self.assertRaises(ValidationError):
            t.value = "foo"
            t.validate()
        with self.assertRaises(ValidationError):
            t.validate(34)

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

    def test_VList_validation(self):
        class VIntMax(VInt):
            max_val = 5
        t = VList("list1", inner=VIntMax)

        with self.assertRaises(ValidationError):
            t.fill(["foo", "bar"])
            t.validate()

        t.fill([1, 2, 3])
        t.validate()
        t.validate([1, 2, 3])

        with self.assertRaises(ValidationError):
            t.fill([1, 22, 35])
            t.validate()

        with self.assertRaises(ValidationError):
            t.validate([1, 22, 35])

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
            t.validate()

    def test_max_min(self):
        t = Port("port")
        with self.assertRaises(ValidationError):
            t.value = 300000
            t.validate()

        with self.assertRaises(ValidationError):
            t.value = -20
            t.validate()

    def test_pattern(self):
        t = Hostname("host")

        with self.assertRaises(ValidationError):
            t.value = "45"
            t.validate()

        t.value = "test45"
        self.assertTrue(t.validate())

    def test_custom_validation(self):
        class Custom(VString):
            def validation(self, value):
                if not value == "foo":
                    raise ValidationError("Is not foo")

        t = Custom("custom")
        with self.assertRaises(ValidationError):
            t.validate("bar")
        with self.assertRaises(ValidationError):
            t.value = "bar"
            t.validate()
        t.value = "foo"
        self.assertTrue(t.validate())

        class Custom(VInt):
            def validation(self, value):
                if not value == 5:
                    raise ValidationError("Is not 5")

        t = Custom("custom")
        with self.assertRaises(ValidationError):
            t.validate(2)
        with self.assertRaises(ValidationError):
            t.value = 3
            t.validate()
        self.assertTrue(t.validate(5))
        t.value = 5
        self.assertTrue(t.validate())


if __name__ == '__main__':
    unittest.main()
