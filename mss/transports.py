import mss.lifecycle
from mss.common import expose, is_exposed


class Transport(object):
    def __init__(self, *args, **kwargs):
        self.lf_manager = mss.lifecycle.LifecycleManager(self, *args, **kwargs)

    def _dispatch(self, method, *args, **kwargs):
        """Method used by the agent to query :py:class:`LifecycleManager`
        methods.
        Only exposed methods are available through the agent.
        """
        func = getattr(self, method)
        if not is_exposed(func):
            raise Exception('Method "%s" is not supported' % method)
        return func(*args, **kwargs)

    @expose
    def info(self):
        return self.lf_manager.info()

    @expose
    def lifecycle(self, xpath, doc=False):
        lfs = self.lf_manager.lifecycle(xpath)
        return [l.name for l in lfs]

    @expose
    def state(self, xpath, doc=False):
        states = self.lf_manager.state(xpath)
        if doc:
            return [s.to_primitive() for s in states]
        else:
            return [s.get_xpath() for s in states]

    @expose
    def state_current(self, xpath):
        states = self.lf_manager.state_current(xpath)
        return [{"xpath": s.get_xpath(), "state": s.name}
                for s in states]

    @expose
    def state_goto_path(self, xpath):
        ret = self.lf_manager.state_goto_path(xpath)
        acc = []
        for state, path in ret:
            acc.append({'xpath': state.get_xpath(),
                        'actions': [(i[0].name, i[1]) for i in path]})
        return acc

    @expose
    def state_goto_requires(self, xpath):
        provides = self.lf_manager.state_goto_requires(xpath)
        requires = []
        for p in provides:
            requires += p
        return [{'xpath': xpath,
                 'requires': requires}]

    @expose
    def state_goto(self, xpath, requires={}):
        return self.lf_manager.state_goto(xpath, requires)

    @expose
    def provide(self, provide_xpath):
        return self.lf_manager.provide(provide_xpath)

    @expose
    def provide_call_path(self, provide_xpath):
        ret = self.lf_manager.provide_call_path(provide_xpath)
        acc = []
        for provide, path in ret:
            acc.append({"xpath": provide.get_xpath(),
                        'actions': [(i[0].name, i[1]) for i in path]})
        return acc

    @expose
    def provide_call_requires(self, xpath, path_idx=0):
        provides = self.lf_manager.provide_call_requires(xpath, path_idx)
        ret = []
        for p in provides:
            ret += p
        return ret

    @expose
    def provide_call_args(self, xpath):
        return self.lf_manager.provide(xpath)

    @expose
    def provide_call(self,
                     provide_xpath_uri,
                     requires={},
                     provide_args={},
                     path_idx=0):
        return self.lf_manager.provide_call(provide_xpath_uri,
                                            requires,
                                            provide_args)

    @expose
    def to_dot(self, lf_name, reachable=False):
        return self.lf_manager.to_dot(lf_name, reachable)

    @expose
    def uri(self, xpath="//"):
        return self.lf_manager.uri(xpath)

    @expose
    def xpath(self, xpath):
        return self.lf_manager.xpath(xpath)

    @expose
    def to_xml(self, xpath=None):
        """Return the xml representation of agent."""
        return self.lf_manager.to_xml(xpath)
