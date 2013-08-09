import unittest 
import mss.configuration_augeas

import mss.modules.mysql.configuration


class TestAugeas(unittest.TestCase):

    def setUp(self):
        self.conf=mss.modules.mysql.configuration.Mysql(autoload=True)
        
    def test_listNodes(self):
        ns=self.conf.listNodes()
        self.assertEqual(ns,[self.conf.port])

    def test_save(self):
        self.conf.port.set("14")
        self.conf.save()

if __name__ == '__main__':
    unittest.main()
