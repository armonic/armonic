import os
import json
import logging

from armonic.utils import Singleton


logger = logging.getLogger(__name__)


class Persist(object):
    __metaclass__ = Singleton

    def __init__(self, load_state=False, save_state=False, state_path="/tmp/armonic_%s%s_state"):
        self.load_state = load_state
        self.save_state = save_state
        self.state_path = state_path
        self.ressources = []
        logger.info("Persist configuration: load_state=%s, save_state=%s" % (load_state, save_state))

    def register(self, ressource):
        if ressource not in self.ressources:
            self.ressources.append(ressource)
            logger.debug("Registered %s for persistance" % ressource)

    def save(self):
        for ressource in self.ressources:
            ressource._persist_save()


class PersistRessource(object):
    _persist = False
    """Define if the ressource can be persistant or not"""

    @property
    def _persist_file(self):
        return Persist().state_path % (self._xml_ressource_name(),
                                       self.get_xpath().replace('/', '_'))

    def _persist_register(self):
        if self._persist and (Persist().save_state or Persist().load_state):
            Persist().register(self)
            self._persist_load()

    def _persist_save(self, *args, **kwargs):
        if Persist().save_state:
            logger.debug("Saving %s state in %s..." % (self.name, self._persist_file))
            with open(self._persist_file, 'w') as f:
                json.dump(self._persist_primitive(), f)
        elif os.path.exists(self._persist_file):
            logger.debug("Removing %s state file %s..." % (self.name, self._persist_file))
            os.unlink(self._persist_file)
        return True

    def _persist_primitive(self):
        """Must return a primitive that can be serialized.

        Must be implemented in subclass.
        """
        raise NotImplementedError()

    def _persist_load(self):
        if Persist().load_state and os.path.exists(self._persist_file):
            logger.debug("Loading %s state from %s..." % (self, self._persist_file))
            with open(self._persist_file) as f:
                state = json.load(f)
            return self._persist_load_primitive(state)
        else:
            return None

    def _persist_load_primitive(self, state):
        """Restore ressource state from state primitive.

        Must be implemented in subclass.
        """
        raise NotImplementedError()
