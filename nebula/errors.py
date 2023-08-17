class Error(Exception):
    """Base class for other exceptions"""

    def __init__(self):
        Exception.__init__(self, self.__doc__)


class NetworkNotFunctional(Error):
    """Linux is functional but Ethernet is broken (Cable disconnected?)"""

    pass


class NetworkNotFunctionalAfterBootFileUpdate(Error):
    """Linux is functional but Ethernet is broken after updating boot files"""

    pass


class LinuxNotFunctionalAfterBootFileUpdate(Error):
    """Linux did not boot correctly after updating boot files"""

    pass


class SSHNotFunctionalAfterBootFileUpdate(Error):
    """SSH not working but ping does after updating boot files"""

    pass


class LinuxNotReached(Error):
    """Linux is inaccessible (likely previous bad BOOT.BIN or kernel crash)"""

    pass

class UbootNotReached(Error):
    """U-boot menu not reachable"""

    pass


class PingFailedAfterReboot(Error):
    """After boot file update ping failed"""

    pass


class MultiDevFound(Error):
    """Multi-device config found. Board name must be specified"""

    pass


class SSHError(Error):
    """SSH transaction failed"""

    pass
