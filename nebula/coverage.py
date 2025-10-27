import os
import random
import string

from fabric import Connection


class coverage:
    """Test coverage management"""

    def __init__(self, address="192.168.86.33", username="root", password="analog"):
        self.address = address
        self.conn = Connection(
            "{username}@{ip}".format(
                username=username,
                ip=address,
            ),
            connect_kwargs={"password": password},
        )
        self.unpacked = None

    def _crun(self, cmd):
        print(cmd)
        result = self.conn.run(cmd)
        print(result)
        print(result.stdout)

    def _lrun(self, cmd):
        print(cmd)
        result = self.conn.local(cmd)
        print(result)
        print(result.stdout)

    def collect_gcov_trackers(self):
        """Collect gcov traces from remote board"""
        tmp_folder = "".join(random.choice(string.ascii_lowercase) for i in range(16))
        tmp_folder = "/tmp/" + tmp_folder
        GCDA = "/sys/kernel/debug/gcov"
        cmd = (
            "find "
            + GCDA
            + " -type d -exec mkdir -p "
            + tmp_folder
            + r"/\{\} \;"
        )
        self._crun(cmd)
        cmd = (
            "find "
            + GCDA
            + " -name '*.gcda' -exec sh -c 'cat < $0 > '"
            + tmp_folder
            + r"'/$0' {} \;"
        )
        self._crun(cmd)
        cmd = (
            "find "
            + GCDA
            + " -name '*.gcno' -exec sh -c 'cp -d $0 '"
            + tmp_folder
            + r"'/$0' {} \;"
        )
        self._crun(cmd)
        dest = (
            "".join(random.choice(string.ascii_lowercase) for i in range(16))
            + ".tar.gz"
        )
        cmd = "tar czf " + dest + " -C " + tmp_folder + " sys"
        self._crun(cmd)
        self.conn.get(dest)
        # Unpack
        self.unpacked = os.getcwd() + "/out"
        self._lrun("mkdir " + self.unpacked)
        self._lrun("tar xvf " + dest + " -C " + self.unpacked + "/")
        self._lrun("rm " + dest)

    def gen_lcov_html_report(self, linux_build_dir):
        """Generate lcov report from linux build dir and gcov traces"""
        report = os.getcwd() + "/report"
        cmd = "lcov -b " + linux_build_dir + " -c -d " + self.unpacked + " > " + report
        self._lrun(cmd)
        html = self.unpacked = os.getcwd() + "/html/"
        cmd = "genhtml -o " + html + " " + report
        self._lrun(cmd)
        print("Generated HTML is located here", html)


if __name__ == "__main__":
    r = coverage()
    r.collect_gcov_trackers()
    r.gen_lcov_html_report("linux")
