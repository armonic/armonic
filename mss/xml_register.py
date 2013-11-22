from lxml.etree import Element, SubElement, Comment, tostring, ElementTree
from platform import uname

class XmlRegister(object):
    _xml_elt = None
    _xml_root = None
    _xml_root_tree = None

    def _xml_tag(self):
        raise NotImplementedError

    def _xml_attributes(self):
        return {}

    def _xml_ressource_name(self):
        raise NotImplementedError

    def _xml_children(self):
        return []

    def _xml_register(self, parent=None):
        if XmlRegister._xml_root == None:
            XmlRegister._xml_root = Element(uname()[1])
            XmlRegister._xml_root_tree = ElementTree(XmlRegister._xml_root)

        attributes = {"ressource" : self._xml_ressource_name()}
        attributes.update(self._xml_attributes())
        if parent == None:
            self._xml_elt = SubElement(XmlRegister._xml_root, 
                                       self._xml_tag(), 
                                       attrib = attributes)
        else:
            self._xml_elt = SubElement(parent._xml_elt, 
                                       self._xml_tag(),
                                       attrib = attributes)

        for c in self._xml_children():
            c._xml_register(self)
        

    @classmethod
    def _xml_tostring(cls):
        return tostring(cls._xml_root)

    def get_uri(self):
        return XmlRegister._xml_root_tree.getpath(self._xml_elt)

    @classmethod
    def find_all_elts(cls, xpath):
        return [XmlRegister._xml_root_tree.getpath(e) for e in cls._xml_root_tree.findall(xpath)]

