#!/usr/bin/env python3

import json, argparse
from isatool import *


def write_lhf(fd, data: list[int]):
    fd.write("v2.0 raw\n")
    for x in data:
        fd.write(f"{x:x} ")
    fd.flush()


class AsmError(Exception):
    def __init__(self, msg: str, line: int = None):
        Exception.__init__(self, msg)
        self.line = line


class Relocation:
    def __init__(self, offset=0, symbol=None):
        self.offset = offset
        self.symbol = symbol
    
    def assert_const(self):
        if self.symbol != None:
            raise AsmError("Expected constant, got symbol reference")
    
    def __repr__(self):
        return f"Relocation({self.offset}, {repr(self.symbol)})"
    
    def __str__(self):
        return f"{self.symbol} + {self.offset}" if self.symbol else f"{self.offset}"

def parse_expr(args: list[Token|Relocation], equ: dict[str,int] = {}) -> Relocation:
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
        elif args[i] in equ:
            args[i] = Relocation(equ[args[i]])
        elif type(args[i]) == int:
            args[i] = Relocation(args[i])
        elif is_sym_str(args[i]):
            args[i] = Relocation(0, args[i])
        elif args[i] not in valid_op and args[i] not in '()':
            raise AsmError(f"`{args[i]}` not expected here")
    
    # Pass 1: Recursively evaluate parenthesized exprs.
    i = 0
    while i < len(args):
        if args[i] == ')':
            raise AsmError("Unmatched closing parenthesis")
        if args[i] != '(':
            i += 1
            continue
        x     = i + 1
        depth = 1
        while depth:
            if x >= len(args):
                raise AsmError("Unmatched opening parenthesis")
            if args[x] == '(': depth += 1
            if args[x] == ')': depth -= 1
            x += 1
        args = args[:i] + [parse_expr(args[i+1:x-1])] + args[x:]
        i += 1
    
    # Pass 2: Collapse prefix operators.
    i = len(args)-1
    while i > 0:
        if type(args[i]) != str and args[i-1] in unary and (i == 1 or type(args[i-2]) == str):
            if args[i-1] != '+': args[i].assert_const()
            args = args[:i-1] + [Relocation(unary[args[i-1]](args[i].offset))] + args[i+1:]
        i -= 1
    
    # Pass 3: Binary operators.
    if type(args[0]) == str:
        raise AsmError(f"`{args[0]}` not expected here")
    for oper in binary:
        i = 0
        while i < len(args)-2:
            if type(args[i+1]) != str: raise AsmError(f"`{args[i+1]}` not expected here")
            if type(args[i+2]) == str: raise AsmError(f"`{args[i+2]}` not expected here")
            if args[i+1] in oper:
                # Enforce exprs to be additive w.r.t. symbols.
                if args[i+1] != '+':
                    args[i+2].assert_const()
                    if args[i+1] != '-':
                        args[i].assert_const()
                # Calculate the constant expr.
                if args[i].symbol and args[i+2].symbol:
                    raise AsmError("Can't add twp symbols to each other")
                symbol = args[i].symbol or args[i+2].symbol
                args = args[:i] + [Relocation(oper[args[i+1]](args[i].offset, args[i+2].offset), symbol)] + args[i+3:]
            else:
                i += 2
    
    if type(args[0]) != Relocation:
        raise AsmError(f"`{args[0]}` not expected here")
    return args[0]

def handle_label(label: str):
    global labels, addr
    if label in labels:
        print(f"Error: redefinition of {label}")
        exit(1)
    labels[label] = addr


def an(s):
    return f'an {s}' if s[0] in 'aeiou' else f'a {s}'

def expect(actual, expected):
    if actual != expected: raise AsmError(f"Expected `{actual}`, got `{expected}`")
    return actual

def exptype(obj, expected: type):
    if type(obj) != expected: raise AsmError(f"Expected {an(expected.__name__)}, got {an(type(obj).__name__)} `{obj}`")
    return obj

def explabel(obj: str):
    if not is_sym_str(obj): raise AsmError(f"Expected label, got `{obj}`")
    return obj

def listexpect(list, index, expected):
    try:
        return expect(list[index], expected)
    except IndexError:
        raise AsmError(f"Expected `{expected}`")

def listexptype(list, index, expected: type):
    try:
        return exptype(list[index], expected)
    except IndexError:
        raise AsmError(f"Expected {an(expected.__name__)}")

def listexplabel(list, index):
    try:
        return explabel(list[index])
    except IndexError:
        raise AsmError("Expected label")


def assemble(infd, isa: ISA) -> list[int]:
    labels: dict[str,Relocation] = {}
    equ:    dict[str,int]        = {}
    reloc:  list[tuple[str,int]] = []
    out:    list[int]            = []
    addr = 0
    
    def handle_directive(directive: str, args: list[str]):
        nonlocal equ, labels, addr
        if directive == 'equ':
            listexplabel(args, 0)
            listexpect(args, 1, ',')
            if len(args) < 3: raise AsmError("Expected an expression")
            if args[0] in labels: raise AsmError(f"Redefinition of `{args[0]}`")
            expr = parse_expr(args[2:], equ)
            if expr.symbol: labels[args[0]] = expr
            else:           equ[args[0]]    = expr.offset
        elif directive == 'org':
            pass
    
    lines: list[str] = infd.readlines()
    for i in range(len(lines)):
        tokens = tokenize(lines[i])
        try:
            if len(tokens) >= 2 and is_sym_str(tokens[0]) and tokens[1] == ':':
                handle_label(tokens[0])
                tokens = tokens[2:]
            if len(tokens) == 0: continue
            if tokens[0][0] == '.':
                handle_directive(tokens[0][1:], tokens[1:])
        except AsmError as e:
            raise AsmError(*e.args, i+1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assembler for the Stovepipe CPU")
    parser.add_argument("--isa",  action="store", default="isa.json")
    parser.add_argument("-o",     action="store", default="out.bin")
    parser.add_argument("infile", action="store")
    args = parser.parse_args()
    
    with open(args.isa, "r") as fd:
        spec = ISA.parse(json.load(fd))
    
    with open(args.infile, "r") as fd:
        try:
            out = assemble(fd, spec)
        except AsmError as e:
            print(f"{args.infile}:{e.line}: {e.args[0]}")
            exit(1)
