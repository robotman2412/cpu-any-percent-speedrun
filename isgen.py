#!/usr/bin/env python3

import json, argparse
from isatool import *



def gen_isa(data):
    spec = ISA.parse(data)
    return spec.gen_ucode_rom()

def write_lhf(fd, data: list|bytes):
    fd.write("v2.0 raw\n")
    for x in data:
        fd.write(f"{x:x} ")
    fd.flush()



parser = argparse.ArgumentParser(description="Instruction set generator for the Stovepipe CPU")
parser.add_argument("infile", action="store")
parser.add_argument("outfile", action="store")
args = parser.parse_args()

with open(args.infile, "r") as infd:
    with open(args.outfile, "w") as outfd:
        data = json.load(infd)
        isa  = gen_isa(data)
        write_lhf(outfd, isa)
