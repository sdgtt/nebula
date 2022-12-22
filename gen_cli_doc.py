# import os
#
# abspath = os.path.abspath(__file__)
# dname = os.path.dirname(abspath)
# s = os.path.split(dname)
# root = s[0]
# os.chdir(root)

import nebula.tasks as nt
from nebula import builder

cmd = "nebula --list > doc/source/cli/top.cli"
print(cmd)
b = builder()
b.shell_out2(cmd)

for tn in nt.ns.task_names:
    print(tn)
    cmd = "nebula --help {} > doc/source/cli/{}.cli".format(tn, tn)
    b.shell_out2(cmd)
    print(cmd)
