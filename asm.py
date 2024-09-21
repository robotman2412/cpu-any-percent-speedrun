#!/usr/bin/env python3

import json, argparse
from isatool import *


def write_lhf(fd, data: list[int]):
    fd.write("v2.0 raw\n")
    for x in data:
        fd.write(f"{x:x} ")
    fd.flush()

def write_bin(fd, data: list[int], dlen: int):
    byte_count = (dlen + 7) // 8
    for word in data:
        for i in range(byte_count):
            fd.write((word >> (i*8)) & 255)


class AsmError(Exception):
    def __init__(self, msg: str, line: int = None):
        Exception.__init__(self, msg)
        self.line = line


class SymRef:
    def __init__(self, offset=0, symbol=None):
        self.offset = offset
        self.symbol = symbol
    
    def assert_const(self):
        if self.symbol != None:
            raise AsmError("Expected constant, got symbol reference")
    
    def __repr__(self):
        return f"SymRef({self.offset}, {repr(self.symbol)})"
    
    def __str__(self):
        return f"{self.symbol} + {self.offset}" if self.symbol else f"{self.offset}"

def parse_expr(args: list[Token|SymRef], equ: dict[str,int] = {}) -> SymRef:
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
        if type(args[i]) == SymRef:
            pass
        elif args[i] in equ:
            args[i] = SymRef(equ[args[i]])
        elif type(args[i]) == int:
            args[i] = SymRef(args[i])
        elif is_sym_str(args[i]):
            args[i] = SymRef(0, args[i])
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
            args = args[:i-1] + [SymRef(unary[args[i-1]](args[i].offset))] + args[i+1:]
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
                args = args[:i] + [SymRef(oper[args[i+1]](args[i].offset, args[i+2].offset), symbol)] + args[i+3:]
            else:
                i += 2
    
    if type(args[0]) != SymRef:
        raise AsmError(f"`{args[0]}` not expected here")
    return args[0]


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


def assemble(infd, isa: ISA) -> tuple[list[int], dict[int, int], dict[str,int]]:
    symbols: dict[str,int]           = {}
    equ:     dict[str,int]           = {}
    reloc:   list[tuple[int,SymRef]] = []
    out:     list[int]               = []
    a2l:     dict[int, int]          = {}
    addr = 0
    
    
    def write_byte(value: int):
        nonlocal out, addr, a2l, i
        a2l[addr] = i + 1
        out.append(value)
        addr += 1
    
    def write_symref(ref: SymRef):
        nonlocal out, reloc, addr, a2l, i
        a2l[addr] = i + 1
        reloc.append((addr, ref))
        out.append(0)
        addr += 1
    
    def handle_label(label: str):
        nonlocal symbols, equ, addr
        if label in equ:
            raise AsmError(f"Label redefines equation `{label}`")
        if label in symbols:
            raise AsmError(f"Redefinition of {label}")
        symbols[label] = addr
    
    def handle_directive(directive: str, args: list[Token]):
        nonlocal equ, symbols, addr
        if directive == 'equ':
            listexplabel(args, 0)
            listexpect(args, 1, ',')
            if len(args) < 3: raise AsmError("Expected an expression")
            if args[0] in symbols: raise AsmError(f"Equation redefines label `{args[0]}`")
            expr = parse_expr(args[2:], equ)
            expr.assert_const()
            equ[args[0]] = expr.offset
            
        elif directive == 'org':
            if len(args) < 1: raise AsmError("Expected an expression")
            expr = parse_expr(args[1:], equ)
            expr.assert_const()
            if expr.offset < addr: raise AsmError(f".{directive} directive goes backwards")
            addr = expr.offset
            
        elif directive == 'byte':
            if len(args) < 1: raise AsmError("Expected an expression")
            while args:
                if ',' in args:
                    comma = args.index(',')
                    expr, args = parse_expr(args[:comma]), args[comma+1:]
                else:
                    expr, args = parse_expr(args), []
                write_symref(expr)
            
        else:
            raise AsmError(f"Uknown directive `{directive}`")
    
    def match_insn(args: list[Token], opcode: Opcode, insn: Insn) -> bool:
        nonlocal equ, isa
        
        # Parse and match instruction.
        args = args.copy()
        idef = insn.format.copy()
        refs = []
        while args or idef:
            if not (args and idef):
                return False
            elif type(idef[0]) == int:
                end  = args.index(idef[1]) if len(idef) > 1 and idef[1] in args else len(args)
                for x in args[:end]:
                    if x in [',', '[', ']']:
                        return False
                refs.append(parse_expr(args[:end], equ))
                args = args[end+1:]
                idef = idef[2:]
            elif args[0].lower() == idef[0].lower():
                args = args[1:]
                idef = idef[1:]
            else:
                return False
        
        # Write opcode and refs.
        for idat in insn.code:
            write_byte(idat)
        for ref in refs:
            write_symref(ref)
        
        return True
    
    def handle_insn(args: list[Token]):
        nonlocal isa
        for opcode in isa.opcodes.values():
            for insn in opcode.variants.values():
                if match_insn(args, opcode, insn): return
        raise AsmError("Unknown instruction")
    
    
    # Pass 1: Write data and reloc entries, find labels.
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
            else:
                handle_insn(tokens)
        except AsmError as e:
            raise AsmError(*e.args, i+1)
    
    # Pass 2: Apply relocations.
    for reladdr, symref in reloc:
        if symref.symbol:
            if symref.symbol not in symbols:
                raise AsmError
            out[reladdr] = symbols[symref.symbol] + symref.offset
        else:
            out[reladdr] = symref.offset
    
    return out, a2l, symbols


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assembler for the Stovepipe CPU")
    parser.add_argument("--isa",           action="store", default="isa.json")
    parser.add_argument("-o", "--outfile", action="store", default="out.lhf")
    parser.add_argument("--format",        action="store", choices=["binary", "logisim"], default="logisim")
    parser.add_argument("infile",          action="store")
    args = parser.parse_args()
    
    with open(args.isa, "r") as fd:
        spec = ISA.parse(json.load(fd))
    
    with open(args.infile, "r") as fd:
        try:
            out, a2l, symbols = assemble(fd, spec)
        except AsmError as e:
            print(f"{args.infile}:{e.line}: {e.args[0]}")
            exit(1)
    
    if args.format == "logisim":
        with open(args.outfile, "w") as fd:
            write_lhf(fd, out)
    else:
        with open(args.outfile, "wb") as fd:
            write_bin(fd, out, spec.byte_size)
    
    if len(symbols):
        print("Symbols:")
        for symname in symbols:
            print(f"  {symname:10} = 0x{symbols[symname]:x}")
    else:
        print("No symbols defined")
