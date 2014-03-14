import os
import inspect
import logging

from armonic.lifecycle import State
from armonic import process


logger = logging.getLogger(__name__)


class RunScript(State):
    """This state permit to run a shell script. To convert require to
    shell script args, redefine :py:meth:`requireToScriptArgs`."""
    script_name = ""

    def require_to_script_args(self):
        """Return []. Redefine it if your script needs arguments.
        This must return a list of arguements.
        """
        return []

    def enter(self):
        script_path = os.path.join(os.path.dirname(
            inspect.getfile(self.__class__)),
            self.script_name)
        script_dir = os.path.dirname(script_path)
        script_args = self.require_to_script_args()
        logger.info("Running script '%s' with args '%s' ..." % (
            self.script_name,
            script_args))
        thread = process.ProcessThread("/bin/bash", None, "test",
                                       ["/bin/bash",
                                        script_path] + script_args,
                                       script_dir, None, None, None)
        thread.start()
        thread.join()
        if thread.code == 0:
            logger.info("Running script '%s': done." % script_path)
        else:
            logger.info("Running script '%s': failed!" % script_path)
            logger.debug("%s", thread.output)
