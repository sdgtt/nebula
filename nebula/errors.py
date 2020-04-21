class Error(Exception):
   """Base class for other exceptions"""
   pass

class NetworkNotFunctional(Error):
    """Linux is functional but Ethernet is broken (Cable disconnected?)"""
    pass

class NetworkNotFunctionalAfterBootFileUpdate(Error):
    """Linux is functional but Ethernet is broken after updating boot files """
    pass

class LinuxNotFunctionalAfterBootFileUpdate(Error):
    """ Linux did not boot correctly after updating boot files """
    pass

class SSHNotFunctionalAfterBootFileUpdate(Error):
    """ SSH not working but ping does after updating boot files """
    pass

class LinuxNotReached(Error):
    """Linux is accessible (likely previous bad BOOT.BIN or kernel crash)"""
    pass

class PingFailedAfterReboot(Error):
    """ After boot file update ping failed """
    pass
