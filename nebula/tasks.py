from invoke import task
import nebula


@task(
    help={
        "ip": "IP address of board",
        "user": "Board username. Default: root",
        "password": "Password for board. Default: analog",
    }
)
def restart_board(c, ip, user="root", password="analog"):
    """ Reboot development system over IP """
    n = nebula.network(dutip=ip, dutusername=user, dutpassword=password)
    n.reboot_board(bypass_sleep=True)
