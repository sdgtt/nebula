import shutil
import subprocess

import yaml


class tftpboot:
    """ TFTP Boot Module """

    def __init__(
        self,
        boot_files_share="/var/lib/tftpboot/",
        default_target="zynq-zed-adv7511-ad9361-fmcomms2-3",
        reference_files="/var/lib/tftpboot/SDCARD/",
        yamlfilename=None,
    ):
        self.boot_files_share = boot_files_share
        self.default_target = default_target
        self.reference_files = reference_files

        if yamlfilename:
            self.update_defaults_from_yaml(yamlfilename)

        if not self.check_service("tftpd-hpa"):
            self.start_service("tftpd-hpa")
            if not self.check_service("tftpd-hpa"):
                raise Exception("tftpd service is not active and/or failed to start")

    def update_defaults_from_yaml(self, filename):
        stream = open(filename, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        if "pdu-config" not in configs:
            raise Exception("pdu-config field not in yaml config file")
        configsList = configs["pdu-config"]
        for config in configsList:
            for k in config:
                if not hasattr(self, k):
                    raise Exception("Unknown field in pdu yaml " + k)
                setattr(self, k, config[k])

    def start_service(self, service):
        p = subprocess.Popen(["systemctl", "start", service], stdout=subprocess.PIPE)
        (output, err) = p.communicate()

    def check_service(self, service):
        p = subprocess.Popen(
            ["systemctl", "is-active", service], stdout=subprocess.PIPE
        )
        (output, err) = p.communicate()
        output = output.decode("utf-8")
        return "inactive" not in output

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
