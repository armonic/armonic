from lxml.etree import Element, SubElement, Comment, tostring, ElementTree, XPathEvalError
from platform import uname

RESSOURCE_ATTR="ressource"

class XpathNotMatch(Exception):
    pass
class XpathMultipleMatch(Exception):
    pass
class XpathHaveNotRessource(Exception):
    pass
class XpathInvalidExpression(Exception):
    pass

class XmlRegister(object):
    """
    This add an xpath path to subclasses instance.

    If you use these objects via pickle, get_xpath() and get_xpath_relative() methods is the only
    one that is managed.
    """
    _xml_elt = None
    _xml_root = None
    _xml_root_tree = None

    _xpath = None
    _xpath_relative = None

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
            XmlRegister._xml_root = Element(uname()[1], attrib={"ressource":"location"})
            XmlRegister._xml_root_tree = ElementTree(XmlRegister._xml_root)

        attributes = {RESSOURCE_ATTR : self._xml_ressource_name()}
        attributes.update(self._xml_attributes())
        if parent == None:
            self._xml_elt = SubElement(XmlRegister._xml_root, 
                                       self._xml_tag(), 
                                       attrib = attributes)
        else:
            self._xml_elt = SubElement(parent._xml_elt, 
                                       self._xml_tag(),
                                       attrib = attributes)

        self._xpath = XmlRegister._xml_root_tree.getpath(self._xml_elt)
        self._xpath_relative = self._xpath.split("/",2)[2]

        for c in self._xml_children():
            c._xml_register(self)
        
    @classmethod
    def to_string(cls):
        return tostring(cls._xml_root)

    def get_xpath(self):
        return self._xpath 
    def get_xpath_relative(self):
        """Get a relatvie xpath, ie. without host.
        This can be useful when a client wants to mix hostname and ip addr."""
        return self._xpath_relative

    def __getstate__(self):
        dct = self.__dict__.copy()
        if "_xpath" not in self.__dict__:
            print self.__dict__
        try:
            dct.pop("_xml_elt")
        except KeyError:
            pass
        return dct

    @classmethod
    def find_all_elts(cls, xpath):
        try:
            return [XmlRegister._xml_root_tree.getpath(e) for e in cls._xml_root_tree.xpath(xpath)]
        except XPathEvalError:
            raise XpathInvalidExpression("xpath '%s' is not valid!" % xpath)

    @classmethod
    def _find_one(cls, xpath):
        """Return the ressource uri. Raise exception if multiple match
        or not match."""
        try:
            ressource = cls._xml_root_tree.xpath(xpath)
        except XPathEvalError:
            raise XpathInvalidExpression("xpath '%s' is not valid!" % xpath)
        if len(ressource) == 0:
            raise XpathNotMatch("%s matches nothing!" % xpath)
        elif len(ressource) > 1:
            raise XpathMultipleMatch("%s matches several ressource!" % xpath)
        return ressource[0]

    @classmethod
    def is_ressource(cls, xpath, ressource_name):
        """Return True if xpath element is a ressource_name."""
        return cls._find_one(xpath).get(RESSOURCE_ATTR) == ressource_name

    @classmethod
    def get_ressource(cls, xpath, ressource_name):
        """Return the name of ressource_name in xpath if exist."""
        ressource = cls._find_one(xpath)
        if ressource.get(RESSOURCE_ATTR) == ressource_name:
            return ressource.tag
        for e in ressource.iterancestors():
            if e.get(RESSOURCE_ATTR) == ressource_name:
                return e.tag
        raise XpathHaveNotRessource("%s have not ressource %s!" % (xpath, ressource_name))


