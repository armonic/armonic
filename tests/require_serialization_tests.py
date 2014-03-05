import unittest
import logging

from mss.require import Require, RequireLocal, RequireExternal
from mss.variable import VString


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


class TestSerialization(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_require(self):
        r = Require('require1', [v])
        rs = {
            'xpath': None,
            'type': 'simple',
            'name': 'require1',
            'nargs': '1',
            'nargs_max': 1,
            'nargs_min': 1,
            'variables': [
                [vs]
            ],
            'variables_skel': [vs]
        }
        self.assertEqual(r.to_primitive(), rs)

    def test_require_nargs_fixed(self):
        r = Require('require1', [v], nargs='3')
        rs = {
            'xpath': None,
            'type': 'simple',
            'name': 'require1',
            'nargs': '3',
            'nargs_max': 3,
            'nargs_min': 3,
            'variables': [
                [vs], [vs], [vs]
            ],
            'variables_skel': [vs]
        }
        self.assertEqual(r.to_primitive(), rs)

    def test_require_nargs_unlimited(self):
        r = Require('require1', [v, v], nargs='*')
        rs = {
            'xpath': None,
            'type': 'simple',
            'name': 'require1',
            'nargs': '*',
            'nargs_max': 99999,
            'nargs_min': 0,
            'variables': [],
            'variables_skel': [vs, vs]
        }
        self.assertEqual(r.to_primitive(), rs)

    def test_require_local(self):
        r = RequireLocal('require2', '//Lifecycle//provide')
        rs = {
            'xpath': None,
            'type': 'local',
            'name': 'require2',
            'lf_name': None,
            'nargs': '1',
            'nargs_min': 1,
            'nargs_max': 1,
            'provide_xpath': '//Lifecycle//provide',
            'provide_ret': [],
            'provide_args': [],
            'variables': [],
            'variables_skel': []
        }
        self.assertEqual(r.to_primitive(), rs)

    def test_require_local_arg(self):
        r = RequireLocal('require2', '//Lifecycle//provide', provide_args=[v])
        rs = {
            'xpath': None,
            'type': 'local',
            'name': 'require2',
            'lf_name': None,
            'nargs': '1',
            'nargs_min': 1,
            'nargs_max': 1,
            'provide_xpath': '//Lifecycle//provide',
            'provide_ret': [],
            'provide_args': [
                vs
            ],
            'variables': [
                [vs]
            ],
            'variables_skel': [vs]
        }
        self.assertEqual(r.to_primitive(), rs)

    def test_require_external(self):
        r = RequireExternal('require3', '//Lifecycle//provide')
        rs = {
            'xpath': None,
            'type': 'external',
            'name': 'require3',
            'lf_name': None,
            'nargs': '1',
            'nargs_min': 1,
            'nargs_max': 1,
            'provide_xpath': '//Lifecycle//provide',
            'provide_ret': [],
            'provide_args': [
                {
                    'name': 'host',
                    'type': 'str',
                    'required': True,
                    'xpath': None,
                    'from_xpath': None,
                    'error': None,
                    'value': None,
                    'default': None
                }
            ],
            'variables': [[
                {
                    'name': 'host',
                    'type': 'str',
                    'required': True,
                    'xpath': None,
                    'from_xpath': None,
                    'error': None,
                    'value': None,
                    'default': None
                }
            ]],
            'variables_skel': [
                {
                    'name': 'host',
                    'type': 'str',
                    'required': True,
                    'xpath': None,
                    'from_xpath': None,
                    'error': None,
                    'value': None,
                    'default': None
                }
            ]
        }
        self.assertEqual(r.to_primitive(), rs)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
