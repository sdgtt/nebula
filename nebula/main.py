from invoke import Collection, Program

from nebula import tasks

program = Program(namespace=Collection.from_module(tasks), version="v1.0.0")
