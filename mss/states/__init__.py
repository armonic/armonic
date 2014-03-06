import mss.utils
from mss.lifecycle import State

from packages import InstallPackagesUrpm, InstallPackagesApt
from run import RunScript
from active import ActiveWithSystemV, ActiveWithSystemd
from templates import CopyTemplates


class InitialState(State):
    supported_os_type = [mss.utils.OsTypeAll()]
