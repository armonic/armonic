import armonic.utils
from armonic.lifecycle import State

from packages import InstallPackages, InstallPackagesUrpm, InstallPackagesApt, RepositoriesApt
from run import RunScript
from active import ActiveWithSystemV, ActiveWithSystemd
from templates import CopyTemplates


class InitialState(State):
    supported_os_type = [armonic.utils.OsTypeAll()]
