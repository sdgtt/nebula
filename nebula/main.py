from invoke import Collection, Program

import nebula
from nebula import tasks

program = Program(namespace=Collection.from_module(tasks), version=nebula.__version__)
