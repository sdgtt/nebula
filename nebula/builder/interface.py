"""This is the interface class for builder to help manage configurations and input overrides."""
import os
import yaml
import shutil

from .core import BuilderCore


class BuilderInterface(BuilderCore):
    def _check_supported(self, resource, possible: list):
        if resource not in possible:
            raise Exception(f"Resource not found. Supported resources: {possible}")

    # Clone
    def analog_clone(self, repo, branch=None, url=None):
        """Clone a repository.

        Args:
            repo (str): The repository to clone.
            branch (str, optional): The branch to clone. Defaults to None.
            url (str, optional): The URL to clone from. Defaults to None.

        Returns:
            str: The path to the cloned repository.
        """
        self._check_supported(repo, ["hdl", "uboot", "linux"])
        cfg = getattr(self, f"cfg_{repo}")

        if repo == "uboot":
            vendor = cfg["boards"][self.board]["vendor"]
            _branch = cfg["source"][vendor]["branch"]
            _url = cfg["source"][vendor]["url"]
        else:
            _branch = cfg["source"]["branch"]
            _url = cfg["source"]["url"]

        if branch is None:
            branch = _branch
        if url is None:
            url = _url

        folder = repo

        cmd = f"git clone -b {branch} {url}"
        if repo in ["linux", "uboot"]:
            cmd += " --depth=1"

        if os.path.isdir(folder):
            print(f"Folder {folder} already exists, skipping clone")
            return folder
        else:
            cmd += f" {folder}"

        self.shell_out(cmd)

        return folder

    # Build
    def analog_build(self, repo, dir, board=None, project=None, def_config=None):
        """Build code from a cloned repo.

        Args:
            repo (str): The repository to build.
            dir (str): The directory where the repo is located.
            board (str, optional): The board to build for. Defaults to None.
            project (str, optional): The project to build for. Defaults to None.
            def_config (str, optional): The default configuration to use. Defaults to None.

        Returns:
            list[str]: The path to the artifacts.
        """
        self._check_supported(
            repo,
            [
                "hdl",
                "uboot",
                "linux",
                "libiio",
                "gr-iio",
                "libad9361",
                "iio-oscilloscope",
            ],
        )

        # Override config
        if board is not None:
            self.board = board
        if project is not None:
            self.project = project
        if def_config is not None:
            self.def_config = def_config

        artifact = None
        pwd = os.getcwd()
        if repo in ["libiio", "gr-iio", "libad9361", "iio-oscilloscope"]:
            raise Exception("Not implemented yet")
            self.cmake_build(repo, dir)
        elif repo == "hdl":
            artifact = self.hdl_build(dir)
        elif repo == "uboot":
            artifact = self.uboot_build(dir)
        elif repo == "linux":
            artifact = self.linux_build(dir)
        else:
            print("Unknown ADI repo, not building")
        os.chdir(pwd)

        if artifact is not None:
            if artifact is not list:
                artifact = [artifact]
            for i in range(len(artifact)):
                artifact[i] = os.path.join(dir, artifact[i])
                artifact[i] = os.path.abspath(artifact[i])
        else:
            return None

        if len(artifact) == 1:
            artifact = artifact[0]

        return artifact

    # Clone and build
    def analog_clone_build(
        self, repo, branch=None, url=None, board=None, project=None, def_config=None
    ):
        folder = self.analog_clone(repo, branch, url)
        return self.analog_build(repo, folder, board, project, def_config)

    def analog_clone_and_build_bootbin(
        self,
        hdl_branch=None,
        hdf_file=None,
        uboot_branch=None,
        ubootbin_file=None,
        board=None,
        project=None,
        def_config=None,
    ):
        """Clone and build the bootbin for the current board.

        Args:
            hdl_branch (str, optional): The HDL branch to clone. Defaults to None.
            uboot_branch (str, optional): The U-Boot branch to clone. Defaults to None.
            board (str, optional): The board to build for. Defaults to None.
            project (str, optional): The project to build for. Defaults to None.
            def_config (str, optional): The default configuration to use. Defaults to None.

        Returns:
            str: The path to the bootbin.
        """
        if board is not None:
            self.board = board
        if project is not None:
            self.project = project
        if def_config is not None:
            self.def_config = def_config

        arch, cc, def_config = self.get_compiler_args("uboot")

        # Verify tools are installed

        # Setup directories
        output_dir = "bootbin_output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_dir = os.path.abspath(output_dir)

        build_dir = "build_bootbin"
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        build_dir = os.path.abspath(build_dir)

        # Build u-boot
        if ubootbin_file is None:
            ubootbin_file = self.analog_clone_build("uboot", uboot_branch)
        shutil.copy(ubootbin_file, output_dir)
        ubootbin_file = os.path.join(output_dir, os.path.basename(ubootbin_file))

        # Build hdf/xsa
        if hdf_file is None:
            hdf_file = self.analog_clone_build("hdl", hdl_branch)
        shutil.copy(hdf_file, output_dir)
        hdf_file = os.path.join(output_dir, os.path.basename(hdf_file))

        dest = output_dir

        # Build FSBL (fsbl.elf)

        # Build PMUFW (pmufw.elf)

        # Build ATF (bl31.elf)

        # Build boot.bin
        return

        if arch == "arm":
            # Build fsbl
            self.create_fsbl_project(os.path.basename(hdf_file), dest)
            self.build_fsbl(dest)
            shutil.copyfile(
                dest + "/build/sdk/fsbl/Release/fsbl.elf", dest + "/fsbl.elf"
            )
            # Build bif
            # self.create_zynq_bif(hdf_file, dest)

            archbg = "zynq"

        elif arch == "arm64":
            pwd = os.getcwd()
            self.create_pmufw_project(os.path.basename(hdf_file), dest)
            self.build_pmufw(dest, hdl_branch, board)
            shutil.copyfile(dest + "/pmufw/executable.elf", dest + "/pmufw.elf")

            self.build_atf(pwd, hdl_branch, board)
            shutil.copyfile(
                pwd + "/arm-trusted-firmware/build/fvp/release/bl31/bl31.elf",
                dest + "/bl31.elf",
            )

            self.create_zmp_fsbl_project(os.path.basename(hdf_file), dest)
            self.build_zmp_fsbl(dest, hdl_branch, board)

            shutil.copyfile(
                dest + "/build/sdk/fsbl/Release/fsbl.elf", dest + "/fsbl.elf"
            )
            # Build bif
            self.create_zynqmp_bif(hdf_file, dest)

            archbg = "zynqmp"

        # Build BOOT.BIN
        # self.build_bootbin(dest, hdl_branch, board, archbg=archbg)

    def analog_generate_configs(self, output_dir="configs"):
        """Generate single config files for HDL, U-Boot and Linux.

        This function will remove include statements from the config files and generate
        single config files for each of the resources.

        Args:
            output_dir (str, optional): The directory where the configs will be generated. Defaults to "configs".

        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for resource in ["hdl", "uboot", "linux"]:
            cfg = getattr(self, f"cfg_{resource}")
            output_file = os.path.join(output_dir, f"{resource}.yaml")
            with open(output_file, "w") as f:
                yaml.dump(cfg, f)
            print(f"Generated {output_file}")
