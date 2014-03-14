import logging
from shutil import copyfile

from armonic.lifecycle import State


logger = logging.getLogger(__name__)


class CopyTemplates(State):
    src_files = []
    dst_files = []

    def enter(self):
        for src, dst in zip(self.src_files, self.dst_files):
            logger.info("Copying template file from '%s' to '%s' ..." % src, dst)
            copyfile(src, dst)
            logger.info("Copying template file from '%s' to '%s': done." % src, dst)
