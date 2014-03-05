import unittest
import logging

from mss.variable import VString


class TestVariableSerialization(unittest.TestCase):

    def test_variable_serialization(self):
        v = VString('var1')
        vs = {
            'xpath': None,
            'from_xpath': None,
            'name': 'var1',
            'error': None,
            'default': None,
            'required': True,
            'type': 'str',
            'value': None
        }
        self.assertEqual(v.to_primitive(), vs)

    def test_variable_default_required(self):
        v = VString('var1', default="test", required=False)
        vs = {
            'xpath': None,
            'from_xpath': None,
            'name': 'var1',
            'error': None,
            'default': "test",
            'required': False,
            'type': 'str',
            'value': "test"
        }
        self.assertEqual(v.to_primitive(), vs)

    def test_variable_error(self):
        v = VString('var1')
        try:
            v._validate()
        except:
            pass
        vs = {
            'xpath': None,
            'from_xpath': None,
            'name': 'var1',
            'error': 'var1 is required',
            'default': None,
            'required': True,
            'type': 'str',
            'value': None
        }
        self.assertEqual(v.to_primitive(), vs)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
