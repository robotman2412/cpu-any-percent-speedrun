#!/usr/bin/env python3

import json, argparse
from isatool import *



def write_lhf(fd, data: list[int]):
    fd.write("v2.0 raw\n")
    for x in data:
        fd.write(f"{x:x} ")

def write_bin(fd, data: list[int], dlen: int):
    byte_count = (dlen + 7) // 8
    for word in data:
        for i in range(byte_count):
            fd.write((word >> (i*8)) & 255)


parser = argparse.ArgumentParser(description="Instruction set generator for the Stovepipe CPU")
parser.add_argument("--infile", "-i",  help="ISA definition JSON file",           action="store", default="isa.json")
parser.add_argument("--outfile", "-o", help="Microcode ROM output file",          action="store", default="isa.lhf")
parser.add_argument("--type", "-O",    help="Specify output file type [logisim]", action="store", default="logisim", choices=["logisim", "binary"])
parser.add_argument("--word-size",     help="Override ISA's microcode ROM size",  action="store", default=None)
args = parser.parse_args()

with open(args.infile, "r") as infd:
    data = json.load(infd)
    spec = ISA.parse(data)
    rom  = spec.gen_ucode_rom()
    if args.type == "logisim":
        with open(args.outfile, "w") as outfd:
            write_lhf(outfd, rom)
    elif args.type == "binary":
        with open(args.outfile, "wb") as outfd:
            write_bin(outfd, rom, args.word_size or spec.ucode_rom.dlen)
