import logging
import jinja2
import os
from shutil import copyfile

from armonic.lifecycle import State


logger = logging.getLogger(__name__)


class CopyTemplates(State):
    src_files = []
    dst_files = []

    def enter(self):
        for src, dst in zip(self.src_files, self.dst_files):
            logger.info("Copying template file from '%s' to '%s' ..." % (src, dst))
            copyfile(src, dst)
            logger.info("Copying template file from '%s' to '%s': done." % (src, dst))


class JinjaTemplate:
    tmp_files = []
    out_files = []
    name_variable = []
    """
    # name_variable list of dictionary
    # : Specify any input variables
    # to the template as a dictionary.
    """
    rootfile = "/"

    def proced(self):
        self.setRootfile(self.rootfile)
        self.templateLoader = jinja2.FileSystemLoader(searchpath=self.rootfile)
        for tmpl_file, out_file, name_variable in zip(self.tmp_files,
                                                      self.out_files,
                                                      self.name_variable):
            templateEnv = jinja2.Environment(loader=self.templateLoader)
            template = templateEnv.get_template(tmpl_file)
            response = template.render(name_variable)
            fileout = os.path.join(self.rootfile, out_file)
            # save the results
            with open(fileout, "w") as f:
                f.write(response)

    def setRootfile(self, rootfile):
        self.rootfile = rootfile
        self.templateLoader = jinja2.FileSystemLoader(searchpath=self.rootfile)

    def getRootfile(self):
        return self.rootfile

    def getTmp_files(self):
        return self.tmp_files

    def getOut_files(self):
        return self.out_files

    def getName_variable(self):
        return self.name_variable

    def setVariable(self, tmp_files, out_files, name_variable, rootfile="/"):
        self.tmp_files = tmp_files
        self.out_files = out_files
        self.name_variable = name_variable
        self.rootfile = rootfile
        self.setRootfile(rootfile)


class TemplateJinja(State, JinjaTemplate):
    pass
