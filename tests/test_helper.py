import pytest
from nebula import helper as helper


@pytest.mark.parametrize(
    "project, bootfiles",
    [
        (
            "socfpga_arria10_socdk_daq2",
            [
                "/boot/socfpga_arria10_common/zImage",
                "/boot/socfpga_arria10_socdk_daq2/u-boot-splx4.sfp",
                "/boot/socfpga_arria10_socdk_daq2/fit_spl_fpga.itb",
                "/boot/socfpga_arria10_socdk_daq2/socfpga_arria10_socdk_sdmmc.dtb",
                "/boot/socfpga_arria10_socdk_daq2/u-boot.img",
            ],
        ),
        (
            "socfpga_arria10_socdk_ad9081-vnp12",
            [
                "/boot/socfpga_arria10_common/zImage",
                "/boot/socfpga_arria10_socdk_ad9081/np12/u-boot-splx4.sfp",
                "/boot/socfpga_arria10_socdk_ad9081/np12/fit_spl_fpga.itb",
                "/boot/socfpga_arria10_socdk_ad9081/np12/socfpga_arria10_socdk_sdmmc.dtb",
                "/boot/socfpga_arria10_socdk_ad9081/np12/u-boot.img",
            ],
        ),
        (
            "zynqmp-zcu102-rev10-adrv9002-rx2tx2-vcmos",
            [
                "/boot/zynqmp-common/Image",
                "/boot/zynqmp-zcu102-rev10-adrv9002/boot_bin_CMOS/BOOT.BIN",
                "/boot/zynqmp-zcu102-rev10-adrv9002/zynqmp-zcu102-rev10-adrv9002-rx2tx2/system.dtb",
            ],
        ),
        (
            "zynq-adrv9361-z7035-bob-vcmos",
            [
                "/boot/zynq-common/uImage",
                "/boot/zynq-adrv9361-z7035-bob/cmos/BOOT.BIN",
                "/boot/zynq-adrv9361-z7035-bob/cmos/devicetree.dtb",
            ],
        ),
    ],
)
def test_get_boot_files_from_descriptor(project, bootfiles):
    h = helper()
    descriptor_file = "nebula/resources/kuiper.json"
    bts = [bt[1] for bt in h.get_boot_files_from_descriptor(descriptor_file, project)]
    assert len(bootfiles) == len(bts)
    for bootfile in bootfiles:
        assert bootfile in bts
