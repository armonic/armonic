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
        return {'xpath': xpath, 'requires': [p.to_primitive() for p in provides]}

    @expose
    def state_goto(self, xpath, requires={}):
        return self.lf_manager.state_goto(xpath, requires)

    @expose
    def provide(self, provide_xpath):
        """Return provides that match provide_xpath.

        :rtype: [Provide_primitive]
        """
        return [p.to_primitive() for p in self.lf_manager.provide(provide_xpath)]

    @expose
    def provide_call_path(self, provide_xpath):
        """Paths for provides that match provide_xpath
        """
        provides_paths = self.lf_manager.provide_call_path(provide_xpath)
        acc = []
        for provide, paths in provides_paths:
            acc.append({
                'xpath': provide.get_xpath(),
                'paths': [[(s.name, m) for s, m in path] for path in paths]
            })
        return acc

    @expose
    def provide_call_requires(self, provide_xpath_uri, path_idx=0):
        """Return Provide required to go to the provide state AND the provide.

        :rtype: [Provide_primitive]
        """
        provide_requires = self.lf_manager.provide_call_requires(
            provide_xpath_uri,
            path_idx)
        try:
            provide_args = self.lf_manager.provide(provide_xpath_uri)[0]
            provide_requires.append(provide_args)
        except IndexError:
            pass
        return [p.to_primitive() for p in provide_requires]

    @expose
    def provide_call_validate(self, provide_xpath_uri, requires=[], path_idx=0):
        result = self.lf_manager.provide_call_validate(provide_xpath_uri, requires, path_idx)
        result['requires'] = [p.to_primitive() for p in result['requires']]
        return result

    @expose
    def provide_call(self, xpath, requires=[], path_idx=0):
        return self.lf_manager.provide_call(xpath, requires, path_idx)

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
