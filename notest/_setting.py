import getpass
import pathlib
import platform


class _Setting:
    SYS_ARCH = platform.machine().lower()
    HOME = str(pathlib.Path.home())
    USERNAME = getpass.getuser()


setting = _Setting()
