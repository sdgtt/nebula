import shutil


class tftpboot:
    """ TFTP Boot Module """

    def __init__(self):
        self.boot_files_share = "/var/lib/tftpboot/"
        self.default_target = "zynq-zed-adv7511-ad9361-fmcomms2-3"

    def update_boot_files(self, dir=False):
        if not dir:
            dir = self.default_target
        print("Updating boot files for: " + dir)
        src = self.boot_files_share + dir + "/BOOT.BIN"
        shutil.copyfile(src, self.boot_files_share)
        src = self.boot_files_share + dir + "/devicetree.dtb"
        shutil.copyfile(src, self.boot_files_share)
        src = self.boot_files_share + "zynq-common/uImage"
        shutil.copyfile(src, self.boot_files_share)
