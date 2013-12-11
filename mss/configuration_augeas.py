""" 
This module defines base classes to use Augeas as a configuration
backend. The main idea is to map augeas configuration tree to python
tree. This python tree is described by :class:`Node` or :class:`Nodes`
classes.  :class:`Configuration` class manages augeas library
initialisation and write tree to configuration file via
:py:meth:`Configuration.save`.

Mapping is based on `xpath
<https://github.com/hercules-team/augeas/wiki/Path-expressions>`_
which are specified via :py:attr:`BaseNode.label` attribute.  When a node contains an
inner node, xpath of inner node should be specified as a relative
xpath, ie. xpath of inner node is the concatenation of xpath of outer
node and xpath of inner node.

There are two :class:`BaseNode` subclasses:

* :class:`Node` which represents normal node
* :class:`Nodes` which represents array of normal node

To create a new configuration mapping
-------------------------------------

1. define some new :class:`Node` or :class:`Nodes` by subclassing.  
2. :class:`Configuration` also has to be specialized.

Code documentation
------------------
"""
import augeas
import common
import logging
import os.path
import inspect

logger=logging.getLogger(__name__)

class VariableNotFound(Exception):pass

class XpathNotUnique(Exception):pass
class XpathNotExist(Exception):pass
class XpathNotInFile(Exception):pass
class XpathMatchNothing(Exception):pass
class AugeasLoadError(Exception):pass
class AugeasSaveError(Exception):pass
class AugeasSetError(Exception):pass


class BaseNode(object):
    """This is the base class for :class:`Node` and :class:`Nodes`.
    
    
    """
    baseXpath=None
    """It is the absolute xpath of this node without its label."""
    label=""
    """This attribute describes augeas variable xpath. To determine it, use augtool command."""

    def setAugeasParameters(self,augeas=None,baseXpath=None,label=None,index=None):
        if augeas != None:
            self.augeas=augeas
        if baseXpath != None:
            self.baseXpath=baseXpath
        if label != None:
            self.label=label
        if index != None:
            self.index=index


    def load(self):
        if self.baseXpath == None:
            raise AttributeError("%s.baseXpath can not be None" % self.__class__.__name__)
        if self.baseXpath.endswith("/"):
            raise AttributeError("%s.baseXpath '%s' must not be end with '/'" % (
                self.__class__.__name__,
                self.baseXpath))
        self._load(self.baseXpath,self.baseXpath)


class Node(BaseNode):
    """This is a subclass of :class:`BaseNode`.
    Basically, a node is described by

    * :py:attr:`BaseNode.label` which corresponds to a relative xpath
    * :py:attr:`Node.value` which describes the value of this node

    Moreover, if :class:`BaseNode` are specified as :class:`Node`
    attributes, they are considered as children of this node.

    Children must be declared as class attribute and can then be
    easily accessed. To control their order, you can also redefine
    children() method.
    
    When a node is initialized, it initializes its children.
    To initialize augeas parameter, you need to call setAugeasParameters method.

    To map a Node with augeas, we need to:

    1. Build a Node()
    2. Call setAugeasParamater()
    3. Call load()

    """
    value=None
    """Permit to specify constant node value. See apache example for instance"""
    xpath="undefined"
    inFile=False
    def __init__(self,baseXpath=None,index=None,augeas=None,label=None):
        if label != None:
            self.label=label
        if baseXpath != None:
            self.baseXpath=baseXpath

        self.augeas=augeas
        self._children=[]
        self.index=index

        for a in dir(self):
            if a != '__class__':
                attr=self.__getattribute__(a)
                # We initialize all Node(s) fields
                if type(attr)==type:
                    if issubclass(attr,Node) or issubclass(attr,Nodes) :
                        aObj=attr()
                        setattr(self,a,aObj)
                        self._children.append(getattr(self,a))
                        logging.debug("%s is a child of %s "%(a,self.__class__))

        if self.children() != None:
            self._children=self.children()
        

    def _load(self,baseXpath="",createXpath=""):
        """The load method 
        - builds xpath for all children 
        - if value is None, gets the value
        - if child augeas is None, sets child augeas field
        """
        logging.debug("load node '%s'"%(self.__class__))
        self.baseXpath=baseXpath
        xpath="%s/%s" %(baseXpath,self.xpath_access())
        # We check that xpath exists and is unique
        logging.debug("match %s" % xpath)
        xpaths=self.augeas.match(xpath)
        if len(xpaths) == 0:
            logging.debug("Not in configuration file  %s"%xpath)
            self.xpath=xpath
        elif len(xpaths) != 1:
            raise XpathNotUnique(xpath)
        else: 
            self.inFile=True
            self.xpath=xpaths[0]
            if self.value == None:
                self.value=self.get()

        self.xpathCreate="%s/%s" %(createXpath,self.xpath_create())
        logger.debug("(%s) xpathCreate : %s" % (self.label,self.xpathCreate))

        # We build xpath for all children
        for c in self._children:
            if c.augeas==None:
                c.augeas=self.augeas
            logger.debug("%s calls load for %s with baseXpath '%s'" % (
                self.__class__, c.__class__, self.xpath))
            c._load(baseXpath=self.xpath,createXpath=self.xpathCreate)
            
        


    def xpath_access(self):
        """ This method generates the xpath of current node."""
        if self.index != None:
            return "%s[%d]" % (self.label,self.index)
        else: return self.label

    def xpath_create(self):
        """ This method generates the xpath when a new node is created."""
        return self.xpath_access()

    def children(self):
        """ Redefine it to control children order.
        This must be an array of Node class.
        """
        return None

    def create(self):
        """This method is used to create new element in configuration files."""
        logger.debug("Create element %s in tree" % self.xpathCreate)
        if self.value != None:
            logger.debug("augtool set %s %s" % (self.xpathCreate,self.value))
            self.augeas.set(self.xpathCreate,self.value)
        for n in self._children:
            n.create()
        

    def walk(self,fct):
        fct(self)
        for n in self._children:
            n.walk(fct)

    def get(self):
        if not self.inFile:raise XpathNotInFile()
        logger.debug("augtool get %s"%(self.xpath))
        return self.augeas.get(self.xpath)

    def rm(self):
        """Remove the tree. This is really shity because we should del
        object as same time ... maybe ot not.
        FIXME
        """
        if not self.inFile:raise XpathNotInFile()
        logger.debug("augtool rm %s"%(self.xpath))
        return self.augeas.remove(self.xpath)



    def set(self,value):
        if value != None:
            self.value=value
            logger.debug("augtool set %s %s"%(self.xpath,value))
            try:
                return  self.augeas.set(self.xpath,self.value)
            except ValueError:
                logger.warning("xpath %s is not valid"%self.xpath)
                raise AugeasSetError("xpath %s is not valid"%self.xpath)
        return None

    def __repr__(self):
        if self.inFile:
            value=self.value
        else:
            value="not in file and not set"
        return "%s = %s" % (self.xpath , value)



class Nodes(BaseNode,list):
    """This class permits to described an array of nodes with same label.
    Basically, this is a list of :class:`Node`. To specialize the inner type, redefine cls attribute.

    baseXpath is the absolute xpath without the label.

    The initialisation of a node consists on create the python
    tree.

    The load methods consists on create the mapping between python
    tree and augeas tree depending on the considered configuration
    file.

    """
    cls=Node
    """This attribute permits to specialize inner type."""
    xpath="undefined"
    def __init__(self,augeas=None,baseXpath=None):
        self.augeas=augeas
        if baseXpath != None:
            self.baseXpath = baseXpath

    def walk(self,fct):
        for n in self:
            n.walk(fct)

    def create(self):
        for n in self:
            n.create()

    def _load(self,baseXpath="",createXpath=""):
        logging.debug("load node '%s'"%(self.__class__))
        acc=[]
        xpath="%s/%s" % (baseXpath,self.label)
        self.xpath=xpath
        self.createXpath=createXpath+"/"+self.label

        if self.baseXpath == None:
             self.baseXpath = baseXpath
        
        m=self.augeas.match(xpath)
        if m == []:
            logging.debug("%s match nothing" % xpath)
        acc=[]
        i=1
        for j in m:
            n=self.cls(baseXpath=baseXpath,augeas=self.augeas,label=self.label,index=i)
            i+=1
            n._load(baseXpath,createXpath)
            list.append(self,n)
    

    def append(self,elt):
        """To append a elt of type Node to this :py:class:`Nodes`. :py:class:`Node` elt must be """
        elt.setAugeasParameters(augeas=self.augeas,
                                baseXpath=self.baseXpath,
                                index=len(self)+1,
                                label=self.label)
        logging.debug("Append %s to %s" % (
            elt.__class__.__name__,
            self.__class__.__name__))
        elt.load()
        elt.create()
        list.append(self,elt)

def BuildTree(cls,**kwargs):
    return type(str(cls),(cls,),kwargs)

def BuildNode(cls,label):
    """This is a helper to build simple :class:`Node` by just redefining label attribute."""
    if type(cls) == str:
        return type(cls,(Node,),{'label':label})
    else:
        return type(str(cls),(cls,),{'label':label})


def Child(cls,**kwargs):
    if type(cls) == str:
        return type(cls,(Node,),kwargs)
    else:
        return type(str(cls),(cls,),kwargs)

class Configuration(object):
    """This class manages configuration elements (nodes) via augeas.

    To create a new :class:`Configuration`, lenses attributes must
    be specified. lenses attribute is a dict composed by a lensName
    and configuration files which has to be parsed by this lens.
    [{lensName : [lensFile,...]},
    {lensName : [lensFiles,...]}, ...  ]
    
    """
    _nodes=[]
    _augeasInstance=None

    def __init__(self,augeas_root="/",autoload=False):
        """augeas_root parameter permits to specify the root of configuration
        files (a kind of chroot).  

        If autoload is set to True, all nodes are loaded, otherwise,
        you have to load them manually.
        """
        self.__initAugeas__(augeas_root)
        for a in dir(self):
            attr=self.__getattribute__(a)
            if type(attr)==type:
                if issubclass(attr,Node) or issubclass(attr,Nodes) :
                    setattr(self,a,attr(augeas=self._augeasInstance))
                    if autoload:
                        logging.debug("autoload node named '%s' %s"%(a, getattr(self,a).__class__))
                        getattr(self,a).load()
                    self._nodes.append(getattr(self,a))
                    logging.debug("%s is a Node(s) "%a)

    def __initAugeas__(self,augeas_root):
        """Initialization of Augeas object.
        Call _loadAugeas method.
        Return an augeas object.
        """
        if not self._augeasInstance:
#            loadpath="augeas_lenses" # FIXME
            loadpath="/".join([os.path.dirname(inspect.getfile(self.__class__)),"augeas_lenses"])
            logging.debug("augtool -r %s -I %s -A -L"%(augeas_root,loadpath))
            self._augeasInstance = augeas.Augeas(root=augeas_root,
                                                 loadpath=loadpath,
                                                 flags=augeas.Augeas.NO_LOAD + augeas.Augeas.NO_MODL_AUTOLOAD)
            self._loadAugeas()
        return self._augeasInstance
            

    def _loadAugeas(self):
        """ Load files in augeas."""
        for (k,f) in self.lenses.items():
            lensName = k
            lensFile = k.lower() + ".lns"
            a="/augeas/load/%s/lens" % lensName
            logging.debug("augtool set %s %s" % (a,lensFile))
            self._augeasInstance.set(a,lensFile)
            lensIncls=f
            for i in range(0,len(lensIncls)):
                a="/augeas/load/%s/incl[%d]" % (lensName,i+1)
                logging.debug("augtool set %s %s" % (a,lensIncls[i]))
                self._augeasInstance.set(a,lensIncls[i])

        logging.debug("augtool load")
        self._augeasInstance.load()
        errors=self._augeasInstance.match("/augeas/load/*/error")
        if errors != []:
            acc=[]
            for i in errors:
                acc.append(self._augeasInstance.get(i))
            raise AugeasLoadError(acc)

    def save(self):
        """Write configuration tree to files."""
        try:
            logger.debug("augtool save")
            self._augeasInstance.save()
        except IOError:
            errors=self._augeasInstance.match("/augeas//error/*")
            acc=[]
            for e in errors:
                acc.append(self._augeasInstance.get(e))
            logger.warning("Error augeas save :"+str(acc))
            raise AugeasSaveError(acc)

    def listNodes(self):
        """Return the list of nodes"""
        return self._nodes



