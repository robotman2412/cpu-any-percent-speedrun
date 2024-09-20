#!/usr/bin/env python3

import json, argparse
from isatool import *


def write_lhf(fd, data: list[int]):
    fd.write("v2.0 raw\n")
    for x in data:
        fd.write(f"{x:x} ")
    fd.flush()


class Relocation:
    def __init__(self, offset=0, symbol=None):
        self.offset = offset
        self.symbol = symbol
    
    def assert_const(self):
        if self.symbol != None:
            raise ValueError("Expected constant, got symbol reference")
    
    def __repr__(self):
        return f"Relocation({self.offset}, {repr(self.symbol)})"
    
    def __str__(self):
        return f"{self.symbol} + {self.offset}" if self.symbol else f"{self.offset}"

def parse_expr(args: list[Token|Relocation]) -> Relocation:
    args = args.copy()
    # Define operators.
    unary = {
        '-': lambda a: -a,
        '+': lambda a: a,
        '!': lambda a: not a,
        '~': lambda a: ~a,
    }
    unary_only = ['!', '~']
    binary = [
        {
            '*':  lambda a, b: a * b,
            '/':  lambda a, b: a // b,
            '%':  lambda a, b: a % b
        }, {
            '-':  lambda a, b: a - b,
            '+':  lambda a, b: a + b
        }, {
            '<<': lambda a, b: a << b,
            '>>': lambda a, b: a >> b
        }, {
            '<=': lambda a, b: a <= b,
            '>=': lambda a, b: a >= b,
            '>':  lambda a, b: a > b,
            '<':  lambda a, b: a < b
        }, {
            '==': lambda a, b: a == b,
            '!=': lambda a, b: a != b
        }, {
            '&':  lambda a, b: a & b
        }, {
            '^':  lambda a, b: a ^ b
        }, {
            '|':  lambda a, b: a | b
        }, {
            '&&': lambda a, b: a and b
        }, {
            '||': lambda a, b: a or b
        }
    ]
    valid_op = unary_only.copy()
    for set in binary:
        valid_op.extend(set.keys())
    
    # Pass 0: Convert stuff to Relocation.
    for i in range(len(args)):
        if type(args[i]) == Relocation:
            pass
        elif type(args[i]) == int:
            args[i] = Relocation(args[i])
        elif is_sym_str(args[i]):
            args[i] = Relocation(0, args[i])
        elif args[i] not in valid_op and args[i] not in '()':
            raise ValueError(f"`{args[i]}` not expected here")
    
    # Pass 1: Recursively evaluate parenthesized exprs.
    i = 0
    while i < len(args):
        if args[i] == ')':
            raise ValueError("Unmatched closing parenthesis")
        if args[i] != '(':
            i += 1
            continue
        x     = i + 1
        depth = 1
        while depth:
            if x >= len(args):
                raise ValueError("Unmatched opening parenthesis")
            if args[x] == '(': depth += 1
            if args[x] == ')': depth += 1
            x += 1
        args = args[:i] + [parse_expr(args[i+1:x-1])] + args[x:]
        i += 1
    
    # Pass 2: Collapse prefix operators.
    i = len(args)-1
    while i > 0:
        if type(args[i]) == str:
            raise ValueError(f"`{args[i]}` not expected here")
        if args[i-1] in unary and (i == 1 or type(args[i-2]) == str):
            if args[i-1] != '+': args[i].assert_const()
            args = args[:i-1] + [Relocation(unary[args[i-1]](args[i].offset))] + args[i+1:]
        i -= 1
    
    # Pass 3: Binary operators.
    if type(args[0]) == str:
        raise ValueError(f"`{args[i]}` not expected here")
    for oper in binary:
        i = 0
    
    return args[0]

def handle_label(label: str):
    global labels, addr
    if label in labels:
        print(f"Error: redefinition of {label}")
        exit(1)
    labels[label] = addr

def handle_directive(directive: str, args: list[str]):
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assembler for the Stovepipe CPU")
    parser.add_argument("--isa",  action="store", default="isa.json")
    parser.add_argument("-o",     action="store", default="a.out")
    parser.add_argument("infile", action="store")
    args = parser.parse_args()
    
    with open(args.isa, "r") as fd:
        spec = ISA.parse(json.load(fd))
    
    labels: dict[str,int]        = {}
    equ:    dict[str,int]        = {}
    reloc:  list[tuple[str,int]] = []
    out:    list[int]            = []
    addr = 0
    
    with open(args.infile, "r") as fd:
        for line in fd.readlines():
            tokens = tokenize(line)
            if len(tokens) >=2 and is_sym_str(tokens[0]) and tokens[1] == ':':
                handle_label(tokens[0])
                tokens = tokens[2:]
            if len(tokens) == 0: continue
            if tokens[0][0] == '.':
                handle_directive(tokens[0], tokens[1:])
        
