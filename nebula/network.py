import logging
import os
import pathlib
import random
import re
import string
import subprocess
import time

import fabric
import nebula.errors as ne
from fabric import Connection
from nebula.common import utils

log = logging.getLogger(__name__)


class network(utils):
    def __init__(
        self,
        dutip=None,
        dutusername=None,
        dutpassword=None,
        dhcp=None,
        nic=None,
        nicip=None,
        yamlfilename=None,
        board_name=None,
    ):
        props = ["dutip", "dutusername", "dutpassword", "dhcp", "nic", "nicip"]
        for prop in props:
            setattr(self, prop, None)
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )
        props = ["dutip", "dutusername", "dutpassword", "dhcp", "nic", "nicip"]
        for prop in props:
            if eval(prop) is not None:
                setattr(self, prop, eval(prop))
        # Set sane defaults if everything still blank
        if not self.dutusername:
            self.dutusername = "root"
        if not self.dutpassword:
            self.dutpassword = "analog"
        if not self.dhcp:
            self.dhcp = False
        self.ssh_timeout = 30
        self.board_name = board_name
        self.rpi_bkup_directory = "rpi_bkup"

    def ping_board(self, tries=10):
        """Ping board and check if any received

        return: True non-zero received, False zero received
        """
        log.info("Checking for board through ping")
        out = ""
        pinged = False
        for p in range(tries):
            try:
                ping = subprocess.Popen(
                    ["ping", "-c", "4", self.dutip],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                out, error = ping.communicate()
                if "0 received" in str(out):
                    raise Exception("Ping failed")
                pinged = True
                break
            except Exception:
                log.warn("Retrying ping")
                time.sleep(3)
        
        return pinged


    def check_ssh(self):
        """SSH to board board and check if its possible to run any command

        return: True working ssh, False non-working ssh
        """
        retries = 3
        for t in range(retries):
            try:
                log.info("Checking for board through SSH")
                result = fabric.Connection(
                    self.dutusername + "@" + self.dutip,
                    connect_kwargs={"password": self.dutpassword},
                ).run("uname -a", hide=True, timeout=self.ssh_timeout)
                break
            except Exception as ex:
                log.warning("Exception raised: " + str(ex))
                time.sleep(3)
                if t >= (retries - 1):
                    raise Exception("SSH Failed")
        return result.failed

    def check_board_booted(self):
        """Check if board has network activity with ping, then check SSH working
        This function raises exceptions on failures
        """
        if not self.ping_board():
            raise Exception("Board not booted")
        else:
            logging.info("PING PASSED")

        if self.check_ssh():
            raise Exception("SSH failing")
        else:
            logging.info("SSH PASSED")

    def reboot_board(self, bypass_sleep=False):
        """Reboot board over SSH, otherwise raise exception"""
        log.info("Rebooting board over SSH")
        # Try to reboot board with SSH if possible
        retries = 3
        for t in range(retries):
            try:
                result = fabric.Connection(
                    self.dutusername + "@" + self.dutip,
                    connect_kwargs={"password": self.dutpassword},
                ).run("/sbin/reboot", hide=False)
                if result.ok:
                    print("Rebooting board with SSH")
                    if not bypass_sleep:
                        time.sleep(30)
                    break
                else:
                    # Use PDU
                    raise Exception("PDU reset not implemented yet")

            except Exception as ex:
                log.warning("Exception raised: " + str(ex))
                time.sleep(3)
                if t >= (retries - 1):
                    raise Exception("Exception occurred during SSH Reboot", str(ex))

    def run_ssh_command(
        self, command, ignore_exceptions=False, retries=3, show_log=True
    ):
        result = None
        for t in range(retries):
            log.info(
                "ssh command:" + command + " to " + self.dutusername + "@" + self.dutip
            )
            try:
                result = fabric.Connection(
                    self.dutusername + "@" + self.dutip,
                    connect_kwargs={"password": self.dutpassword},
                ).run(command, hide=True, timeout=self.ssh_timeout)
                if result.failed:
                    raise Exception("Failed to run command:", command)

                if show_log and result.stdout:
                    log.info("result stdout begin -------------------------------")
                    log.info(f"{result.stdout}")
                    log.info("result stdout end -------------------------------")

                if show_log and result.stderr:
                    log.info("result stderr begin -------------------------------")
                    log.info(f"{result.stderr}")
                    log.info("result stderr end -------------------------------")

                break
            except Exception as ex:
                log.warning("Exception raised: " + str(ex))
                if not ignore_exceptions:
                    time.sleep(3)
                    if t >= (retries - 1):
                        raise Exception("SSH Failed: " + str(ex))

        return result

    def copy_file_to_remote(self, src, dest):
        retries = 3
        log.info("Copying file to remote: " + src)
        for t in range(retries):
            try:
                Connection(
                    self.dutusername + "@" + self.dutip,
                    connect_kwargs={"password": self.dutpassword},
                ).put(src, remote=dest)
            except Exception as ex:
                log.warning("Exception raised: " + str(ex))
                time.sleep(3)
                if t >= (retries - 1):
                    raise ne.SSHError

    def update_boot_partition(
        self, bootbinpath=None, uimagepath=None, devtreepath=None
    ):
        """update_boot_partition:
        Update boot files on existing card which from remote files
        """
        log.info("Updating boot files over SSH")
        try:
            self.run_ssh_command("ls /tmp/sdcard")
            dir_exists = True
        except Exception:
            log.info("Existing /tmp/sdcard directory not found. Will need to create it")
            dir_exists = False
        if dir_exists:
            try:
                log.info("Trying to unmounting directory")
                self.run_ssh_command("umount /tmp/sdcard")
            except Exception:
                log.info("Unmount failed... Likely not mounted")
                pass
        else:
            self.run_ssh_command("mkdir /tmp/sdcard")
        self.run_ssh_command("mount /dev/mmcblk0p1 /tmp/sdcard")
        if bootbinpath:
            self.copy_file_to_remote(bootbinpath, "/tmp/sdcard/")
        if uimagepath:
            self.copy_file_to_remote(uimagepath, "/tmp/sdcard/")
        if devtreepath:
            self.copy_file_to_remote(devtreepath, "/tmp/sdcard/")
        self.run_ssh_command("sudo reboot", ignore_exceptions=True)

    def update_kernel_overlay(
        self, kernelpath, devtreepath, dtparam, unload=False
    ):
        """ update_boot_partition:
                Update boot files on existing card which from remote files
        """
        undo = False
        log.info("Updating boot files over SSH")
        try:
            self.run_ssh_command("ls /tmp/sdcard")
            dir_exists = True
        except:
            log.info("Existing /tmp/sdcard directory not found. Will need to create it")
            dir_exists = False
        if dir_exists:
            try:
                log.info("Trying to unmounting directory")
                self.run_ssh_command("umount /tmp/sdcard")
            except:
                log.info("Unmount failed... Likely not mounted")
                pass
        else:
            self.run_ssh_command("mkdir /tmp/sdcard")
        self.run_ssh_command("mount /dev/mmcblk0p1 /tmp/sdcard")

        #create backup dir      
        try:
            log.info("Creating backup directory {}".format(self.rpi_bkup_directory))
            self.run_ssh_command(
                            "mkdir /tmp/sdcard/{}".\
                                format(self.rpi_bkup_directory)
                        )
        except:
            log.warn("Backup directory creation failed. Probably already existed!")
            undo = True

        # unload kernel or device tree
        if unload or undo:
            # restore backup
            try:
                self.run_ssh_command(
                    "cp -r /tmp/sdcard/{}/* /tmp/sdcard/. && rm -rf /tmp/sdcard/{}".\
                        format(self.rpi_bkup_directory, self.rpi_bkup_directory)
                )
            except:
                log.warn("Restoring backup failed!")

            #remove dtoverlay and dtparam from config.txt
            try:
                if devtreepath:
                    dev_overlay_name = os.path.basename(devtreepath)
                    dev_overlay_name=os.path.splitext(dev_overlay_name)[0]
                    log.info("Unappending {}".format(dev_overlay_name))
                    self.run_ssh_command(
                        "sed -i -e '/dtoverlay={}/,+2d' /tmp/sdcard/config.txt".\
                            format(dev_overlay_name)
                    )
            except:
                log.warn("config.txt update failed!")
            
            # remove backup directory if in unload mode
            if unload:
                # self.run_ssh_command(
                #     "rm -rf /tmp/sdcard/{}".\
                #         format(self.rpi_bkup_directory)
                # )
                self.run_ssh_command("sudo reboot", ignore_exceptions=True, retries=1)
                return

            if undo:
                #attempt to create backup directory again   
                try:
                    log.info("Creating backup directory {}".format(self.rpi_bkup_directory))
                    self.run_ssh_command(
                                    "mkdir /tmp/sdcard/{}".\
                                        format(self.rpi_bkup_directory)
                                )
                except:
                    log.warn("Backup directory creation failed")
                    raise Exception("Fail to update kernel/overlay.")


        # copy over files
        if kernelpath:
            self.run_ssh_command(
                        "mv -f /tmp/sdcard/*.img /tmp/sdcard/{}/.".\
                            format(self.rpi_bkup_directory)
                    )
            log.info("Copying kernel image {}".format(kernelpath))
            self.copy_file_to_remote(kernelpath, "/tmp/sdcard/")

        if devtreepath:
            dev_overlay_name = os.path.basename(devtreepath)
            dev_overlay_name = os.path.splitext(dev_overlay_name)[0]
            self.run_ssh_command(
                        "mv -f /tmp/sdcard/overlays /tmp/sdcard/{}/.".\
                            format(self.rpi_bkup_directory)
                    )
            self.run_ssh_command("mkdir -p /tmp/sdcard/overlays")
            log.info("Copying device tree overlay {}".format(devtreepath))
            self.copy_file_to_remote(devtreepath, "/tmp/sdcard/overlays/")
            self.run_ssh_command(
                        "echo dtoverlay={} >> /tmp/sdcard/config.txt".format(dev_overlay_name)
                    )
            if dtparam:
                self.run_ssh_command(
                            "echo dtparam={} >> /tmp/sdcard/config.txt".format(dtparam)
                        )

        self.run_ssh_command("sudo reboot", ignore_exceptions=True, retries=1)

         # wait for successful reboot
        retry = 0
        while(1):
            try:
                self.check_board_booted()
                break
            except:
                if retry == 3:
                    raise Exception("Board failed to boot")
                log.info("Waiting for board to boot...")
                retry+=1
                time.sleep(60)
        

        # verify if device tree was loaded
        if devtreepath:
            vcdbglog_path = "/tmp/vcdbglog.txt"
            dev_overlay_name = os.path.basename(devtreepath)
            dev_overlay_name = os.path.splitext(dev_overlay_name)[0]
            log.info("Verifying if overlay was loaded...")
            self.run_ssh_command(
                            "vcdbg log msg 2> {} && cat {} | grep {}".\
                                format(vcdbglog_path, vcdbglog_path, dev_overlay_name)
                        )
            self._dl_file(vcdbglog_path)
            log.info("vcdbg log msg collected")

    def update_boot_partition_existing_files(self, subfolder=None):
        """update_boot_partition_existing_files:
        Update boot files on existing card which contains reference
        files in the BOOT partition

        You must specify the subfolder with the BOOT partition to use.
        For example: zynq-zc706-adv7511-fmcdaq2
        """
        log.info("Updating boot files over SSH from SD card itself")
        if not subfolder:
            raise Exception("Must provide a subfolder")
        self.run_ssh_command("mkdir /tmp/sdcard")
        self.run_ssh_command("mount /dev/mmcblk0p1 /tmp/sdcard")
        self.run_ssh_command("cp /tmp/sdcard/" + subfolder + "/BOOT.BIN /tmp/sdcard/")
        if "zynqmp" in subfolder:
            self.run_ssh_command("cp /tmp/sdcard/zynqmp-common/Image /tmp/sdcard/")
            self.run_ssh_command(
                "cp /tmp/sdcard/" + subfolder + "/system.dtb /tmp/sdcard/"
            )
        else:
            self.run_ssh_command("cp /tmp/sdcard/zynq-common/uImage /tmp/sdcard/")
            self.run_ssh_command(
                "cp /tmp/sdcard/" + subfolder + "/devicetree.dtb /tmp/sdcard/"
            )
        self.run_ssh_command("sudo reboot")

    def _dl_file(self, filename):
        fabric.Connection(
            self.dutusername + "@" + self.dutip,
            connect_kwargs={"password": self.dutpassword},
        ).get(filename)

    def check_dmesg(self, error_on_warnings=False):
        """check_dmesg:
        Download and parse remote board's dmesg log

        return:
            dmesg_log string of dmesg log
            status: 0 if no errors found, 1 otherwise
        """
        tmp_filename_root = "".join(
            random.choice(string.ascii_lowercase) for i in range(16)
        )
        tmp_filename = "/tmp/" + tmp_filename_root
        tmp_filename_err = "/tmp/" + tmp_filename_root + "_err"
        tmp_filename_war = "/tmp/" + tmp_filename_root + "_warn"

        if self.board_name == "pluto":
            with open(tmp_filename_root, "w") as outfile:
                outfile.write(self.run_ssh_command("dmesg").stdout)
            with open(tmp_filename_root + "_warn", "w") as outfile:
                outfile.write(
                    self.run_ssh_command('dmesg -r | { grep "^.4" || true; }').stdout
                )
            with open(tmp_filename_root + "_err", "w") as outfile:
                outfile.write(
                    self.run_ssh_command('dmesg -r | { grep "^.3" || true; }').stdout
                )
        else:
            self.run_ssh_command("dmesg > " + tmp_filename)
            self.run_ssh_command("dmesg -l warn > " + tmp_filename_war)
            self.run_ssh_command("dmesg -l err > " + tmp_filename_err)
            self._dl_file(tmp_filename)
            self._dl_file(tmp_filename_war)
            self._dl_file(tmp_filename_err)

        os.rename(tmp_filename_root, "dmesg.log")
        os.rename(tmp_filename_root + "_warn", "dmesg_warn.log")
        os.rename(tmp_filename_root + "_err", "dmesg_err.log")
        logging.info("dmesg logs collected")

        # Process
        with open("dmesg.log", "r") as f:
            all_log = f.readlines()
        with open("dmesg_warn.log", "r") as f:
            warn_log = f.readlines()
        with open("dmesg_err.log", "r") as f:
            error_log = f.readlines()

        path = pathlib.Path(__file__).parent.absolute()
        res = os.path.join(path, "resources", "err_rejects.txt")
        with open(res) as f:
            error_rejects = f.readlines()

        error_log_filetered = [
            i
            for i in error_log
            if re.sub(r"^\[[\s\.\d]*\] ", "", i) not in error_rejects
        ]

        with open("dmesg_err_filtered.log", "w") as outfile:
            if error_log_filetered:
                for line in error_log_filetered:
                    outfile.write(line)

        if len(error_log_filetered) > 0:
            log.info("Errors found in dmesg logs")

        logs = {"log": all_log, "warn": warn_log, "error": error_log_filetered}
        return len(error_log_filetered) > 0, logs

    def run_diagnostics(self):
        """run_diagnostics:
        execute and download adi_diagnostic report

        return:
            status: 0 if no errors found, 1 otherwise
        """
        # check if can connect to board
        self.check_board_booted()
        report_file_name = self.board_name + "_diag_report.tar.bz2"
        # execute adi_diagnostic_report
        result = self.run_ssh_command(
            "adi_diagnostic_report --file-name {}".format(report_file_name)
        )
        if not result.ok:
            raise Exception("Running diagnostics failed")

        # fetch file
        self._dl_file(report_file_name)
        log.info("Diagnostic report {} collected".format(report_file_name))
