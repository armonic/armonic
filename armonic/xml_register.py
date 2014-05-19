from lxml.etree import Element, SubElement, tostring, ElementTree, XPathEvalError, _Element
import logging

from armonic.persist import PersistRessource


logger = logging.getLogger(__name__)
RESSOURCE_ATTR = "ressource"


class XpathNotMatch(Exception):
    pass


class XpathMultipleMatch(Exception):
    pass


class XpathHaveNotRessource(Exception):
    pass


class XpathInvalidExpression(Exception):
    pass


class XMLRessource(PersistRessource):
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

    def _xml_add_properties(self):
        """Redefine it to add property nodes to this node.

        :rtype: a list etree.Element"""
        return []

    def _xml_add_properties_tuple(self):
        """Redefine it to add property nodes to this node.

        :rtype: a list of tuple (property_name, value)"""
        return []

    def _xml_on_registration(self):
        """Method run when the ressource is registered in the XML;
        """
        PersistRessource._persist_register(self)

    def get_xpath(self):
        return self._xpath

    def get_xpath_relative(self):
        """Get a relatvie xpath, ie. without host.
        This can be useful when a client wants to mix hostname and ip addr."""
        return self._xpath_relative



class XMLRegistery(object):
    """Represent a LifecycleManager in XML.

    This is a singleton.
    """
    _instance = None
    _xml_root_tree = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(XMLRegistery, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def _xml_register(self, ressource, parent=None):
        """
        :type ressource: XMLRessource
        :type parent: lxml.Element
        """
        attributes = {RESSOURCE_ATTR: ressource._xml_ressource_name()}
        attributes.update(ressource._xml_attributes())

        if parent is None:
            xml_elt = Element(ressource._xml_tag(), attrib=attributes)
            self._xml_root_tree = ElementTree(xml_elt)
        else:
            xml_elt = SubElement(parent,
                                 ressource._xml_tag(),
                                 attrib=attributes)

        ressource._xpath = self._xml_root_tree.getpath(xml_elt)
        try:
            ressource._xpath_relative = ressource._xpath.split("/", 2)[2]
        except IndexError:
            ressource._xpath_relative = ressource._xpath

        if (ressource._xml_add_properties()
                or ressource._xml_add_properties_tuple()):

            properties_node = SubElement(xml_elt, "properties")

            for (prop, value) in ressource._xml_add_properties_tuple():
                logger.debug("Add property '%s:%s' on node with tag %s" % (
                             prop, value, ressource._xml_tag()))

                sub = SubElement(properties_node, prop)
                sub.text = value

            for elt in ressource._xml_add_properties():
                logger.debug("Add property '%s' on node with tag %s" % (
                             elt.tag, ressource._xml_tag()))

                properties_node.append(elt)

        self._xml_register_children(xml_elt, ressource)
        logger.debug("Registered %s in XML registery" % ressource.__repr__())
        ressource._xml_on_registration()

    def _xml_register_children(self, xml_elt, ressource):
        """Be careful, this removes children before adding them."""
        for c in xml_elt.iterchildren():
            xml_elt.remove(c)

        for c in ressource._xml_children():
            self._xml_register(c, parent=xml_elt)

    def to_string(self, xpath):
        return tostring(self._find_one(xpath), pretty_print=True)

    def xpath(self, xpath):
        """
        :rtype: [str]
        """
        acc = []
        try:
            request = self._xml_root_tree.xpath(xpath)
            if type(request) != list:
                return [str(request)]

            for e in request:
                if type(e) == _Element:
                    acc.append(tostring(e, pretty_print=True))
                else:
                    acc.append(str(e))
        except XPathEvalError:
            raise XpathInvalidExpression("xpath '%s' is not valid!" % xpath)
        return acc

    def find_all_elts(self, xpath):
        try:
            return [self._xml_root_tree.getpath(e) for e in
                    self._xml_root_tree.xpath(xpath)]
        except XPathEvalError:
            raise XpathInvalidExpression("xpath '%s' is not valid!" % xpath)

    def _find_one(self, xpath):
        """Return the ressource uri. Raise exception if multiple match
        or not match.

        :rtype: a xml element.
        """
        try:
            ressource = self._xml_root_tree.xpath(xpath)
        except XPathEvalError:
            raise XpathInvalidExpression("xpath '%s' is not valid!" % xpath)
        if len(ressource) == 0:
            raise XpathNotMatch("%s matches nothing!" % xpath)
        elif len(ressource) > 1:
            raise XpathMultipleMatch("%s matches several ressources: %s" % (xpath, ", ".join([self._xml_root_tree.getpath(r) for r in ressource])))
        return ressource[0]

    def is_ressource(self, xpath, ressource_name):
        """Return True if xpath element is a ressource_name."""
        return self._find_one(xpath).get(RESSOURCE_ATTR) == ressource_name

    def get_ressource(self, xpath, ressource_name):
        """Return the name of ressource_name in xpath if exist."""
        ressource = self._find_one(xpath)
        if ressource.get(RESSOURCE_ATTR) == ressource_name:
            return ressource.tag
        for e in ressource.iterancestors():
            if e.get(RESSOURCE_ATTR) == ressource_name:
                return e.tag
        raise XpathHaveNotRessource("%s have not ressource %s!" %
                                    (xpath, ressource_name))
