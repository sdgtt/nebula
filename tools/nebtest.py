#  type: ignore
import argparse

import nebula

parser = argparse.ArgumentParser(description="Nebula test runner cli")
parser.add_argument(
    "-c",
    action="store",
    dest="configfilename",
    required=True,
    help="Configuration filename",
)

args = parser.parse_args()

m = nebula.manager(configfilename=args.configfilename)
m.run_test()
