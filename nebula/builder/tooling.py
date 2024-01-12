import os

from .configs import BuilderConfig

class Tooling(BuilderConfig):
    def get_tooling_setup_prefix(self, resource):

        if resource not in ["linux", "hdl", "uboot"]:
            raise Exception("Resource not found")
    
        cfg = getattr(self, f"cfg_{resource}")
        if resource != "hdl":
            is_xilinx = cfg['boards'][self.board]['vendor'] == 'xilinx'
        else:
            is_xilinx = True # FIXME


        if is_xilinx:
            vivado_version = cfg['tools']['xilinx']['vivado']
            # If windows os
            if os.name == 'nt':
                raise Exception("Windows not supported yet")

            return ". /opt/Xilinx/Vivado/" + str(vivado_version) + "/settings64.sh"
        else:
            raise Exception("Unsupported vendor")

    def get_compiler_args(self, resource):

        if resource not in ["linux", "hdl", "uboot"]:
            raise Exception("Resource not found")
        
        cfg = getattr(self, f"cfg_{resource}")

        if resource in ["uboot", "linux"]:
            cc = cfg['boards'][self.board]['cross_compile']
            arch = cfg['boards'][self.board]['arch']
            def_config = cfg['boards'][self.board]['defconfig']
            return arch, cc, def_config
        else:
            raise Exception(f"Unsupported resource: {resource}")
        