import os
import select
import threading
import logging
from subprocess import Popen, PIPE, STDOUT

logger = logging.getLogger(__name__)


class ProcessThread(threading.Thread):
    """ Base class for running tasks """

    def __init__(self,
                 type,
                 status,
                 module,
                 command,
                 cwd=None,
                 callback=None,
                 shell=None,
                 env=None):
        self.process = None
        self._code = 2000
        self._output = ""
        self.lock = threading.RLock()
        # thread type (config, install...)
        self.type = type
        self.status = status
        self.module = module
        self.command = command
        self.cwd = cwd
        self.callback = callback
        self.shell = shell
        self.env = os.environ.copy()
        if env:
            self.env.update(env)
        threading.Thread.__init__(self)

    def __enter__(self):
        self.start()
        return self

    def __exit(self):
        self.stop()

    def __repr__(self):
        return "<%s(%s, %s)>" % (self.__class__.__name__,
                                 self.module,
                                 self.command)

    def launch(self):
        """Thread is started and joined. This is a blocking method.

        :rtype: True if process execution success
        """
        self.start()
        self.join()
        return self.code == 0

    @property
    def output(self):
        try:
            return self._output.decode('utf-8')
        except:
            return self._output.decode('latin-1')

    @property
    def code(self):
        return self._code

    def run(self):
        """ run command """
        logger.debug("Running `%s` command" % " ".join(self.command))
        self.process = Popen(self.command, stdout=PIPE, stderr=STDOUT,
            bufsize=1, cwd=self.cwd, shell=self.shell, env=self.env)
        self.catch_output()
        return 0

    def stop(self):
        """ stop current process if exists"""
        try:
            self.process.terminate()
            self.join()
        except OSError:
            pass
        except AttributeError:
            pass

    def catch_output(self):
        """ get command context """
        while self.isAlive():
            # get the file descriptor of the process stdout pipe
            # for reading
            try:
                fd = select.select([self.process.stdout.fileno()],
                    [], [], 5)[0][0]
            # raise an exception when the process doesn't make output
            # for long time
            except IndexError:
                fd = None
                pass

            self.process.poll()
            if self.process.returncode == None:
                # get bytes one by one
                if fd:
                    self.lock.acquire()
                    self._output += os.read(fd, 1)
                    if self._output != "":
                        logger.process(self._output[-1])
                    self.lock.release()
            else:
                # get last bytes from output
                if fd:
                    self.lock.acquire()
                    while True:
                        output = os.read(fd, 4096)
                        if output == None or output == "":
                            break
                        logger.process(output)
                        self._output += output
                    self.lock.release()
                self._code = self.process.returncode
                if self.callback:
                    self.callback(self.module, self._code, self._output)
                logger.process("Finished `%s` command\n" %
                               " ".join(self.command))
                logger.debug("Finished `%s` command" % " ".join(self.command))
                break
