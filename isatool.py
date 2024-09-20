
type Sigval  = dict[str,str|bool]
type Argspec = int
type Token = str|int



def tokenize(raw: str) -> list[Token]:
    ls   = []
    long = ['<<', '>>', '<=', '>=', '==', '!=', '&&', '||']
    while raw:
        # Labels and keywords.
        if is_sym_char(raw[0], False):
            tmp, raw = raw[0], raw[1:]
            while is_sym_char(raw[0]):
                tmp, raw = tmp+raw[0], raw[1:]
            if tmp[0] in '0123456789':
                ls.append(int(tmp, 0))
            else:
                ls.append(tmp)
        # Operators composed of two symbols.
        elif len(raw) >= 2 and raw[0:1] in long:
            ls.append(raw[0:1])
            raw = raw[2:]
        # Other symbols.
        elif ord(raw) > 0x20:
            ls.append(raw[0])
            raw = raw[1:]
    return ls


def is_sym_char(char: str, allow_numeric = True) -> bool:
    n = ord(char)
    if ord('a') <= n <= ord('z'):
        return True
    elif allow_numeric and ord('0') <= n <= ord('9'):
        return True
    else:
        return char in ['.', '_', '$']


def is_sym_str(sym: str) -> bool:
    if not is_sym_char(sym[0], False): return False
    for char in sym[1:]:
        if not is_sym_char(char): return False
    return True


def insert_val(val: int, pos: tuple[int,int], insert: int) -> int:
    assert len(pos) == 2 and pos[0] >= pos[1] and pos[1] >= 0
    mask = (2 << pos[0]) - (1 << pos[1])
    val  = (val & ~mask) | ((insert << pos[1]) & mask)
    return val



class Signal:
    def __init__(self):
        self.type  = None
        self.range = None
        self.enum  = None
    
    @staticmethod
    def parse(data: dict):
        sig = Signal()
        sig.type = data['type']
        if sig.type == "encoder":
            sig.range = tuple(data['range'])
            sig.enum  = data['enum']
        elif sig.type == "flag":
            sig.range = (data['bit'], data['bit'])
        else:
            raise ValueError(f"Unknown signal type {sig.type}")
        return sig


class Insn:
    def __init__(self):
        self.format: list[str|Argspec] = []
        self.sigval: Sigval            = {}
        self.desc:   str               = None
    
    @staticmethod
    def parse(format: str, data: dict):
        insn = Insn()
        insn.format = tokenize(format)
        insn.desc   = data['desc'] if 'desc' in data else None
        insn.sigval = data['insn']
        return insn


class Opcode:
    def __init__(self):
        self.id:        int             = 0
        self.ucode:     list[Sigval]    = []
        self.variants:  dict[str, Insn] = {}
        self.no_prefix: bool            = False
        self.no_suffix: bool            = False
    
    @staticmethod
    def parse(id: int, data: dict):
        op = Opcode()
        op.id       = id
        op.ucode    = data['ucode']
        op.variants = {k: Insn.parse(k, data['variants'][k]) for k in data['variants']}
        if 'no_prefix' in data:
            op.no_prefix = data['no_prefix']
        if 'no_suffix' in data:
            op.no_suffix = data['no_suffix']
        return op


class UcodeRom:
    def __init__(self):
        self.alen:        int             = 0
        self.dlen:        int             = 0
        self.prefix:      list[Sigval]    = []
        self.suffix:      list[Sigval]    = []
        self.opcode_addr: tuple[int, int] = (0, 0)
        self.cycle_addr:  tuple[int, int] = (0, 0)

    @staticmethod
    def parse(data: dict):
        ucr = UcodeRom()
        ucr.alen        = data['rom_alen']
        ucr.dlen        = data['rom_dlen']
        ucr.prefix      = data['prefix']
        ucr.suffix      = data['suffix']
        ucr.opcode_addr = data['opcode_addr']
        ucr.cycle_addr  = data['cycle_addr']
        return ucr


class ISA:
    def __init__(self):
        self.ucode_signals: dict[str,Signal] = {}
        self.insn_signals:  dict[str,Signal] = {}
        self.opcodes:       dict[int,Opcode] = {}
        self.opcode_range:  tuple[int,int]   = (0, 0)
        self.ucode_rom:     UcodeRom         = None
    
    @staticmethod
    def parse(data: dict):
        isa = ISA()
        isa.ucode_signals = {k: Signal.parse(data['ucode_signals'][k]) for k in data['ucode_signals']}
        isa.insn_signals  = {k: Signal.parse(data['insn_signals'][k]) for k in data['insn_signals']}
        isa.opcodes       = {int(k, 0): Opcode.parse(int(k, 0), data['opcodes'][k]) for k in data['opcodes']}
        isa.opcode_range  = tuple(data['opcode_range'])
        isa.ucode_rom     = UcodeRom.parse(data['ucode'])
        return isa
    
    @staticmethod
    def gen_signals(siglist: dict[str,Signal], sigval: Sigval) -> int:
        val = 0
        for k in sigval:
            if k not in siglist:
                raise ValueError(f"Unknown signal '{k}'")
            sigdef = siglist[k]
            if sigdef.type == "flag":
                val = insert_val(val, sigdef.range, int(sigval[k]))
            elif sigdef.type == "encoder":
                val = insert_val(val, sigdef.range, sigdef.enum[sigval[k]])
        return val
    
    def gen_ucode(self, op: Opcode) -> list[int]:
        ucode = []
        if not op.no_prefix:
            ucode.extend(self.ucode_rom.prefix)
        ucode.extend(op.ucode)
        if not op.no_suffix:
            ucode.extend(self.ucode_rom.suffix)
        ls    = []
        if len(ucode) > 2 << (self.ucode_rom.cycle_addr[0] - self.ucode_rom.cycle_addr[1]):
            raise ValueError("Opcode has too many cycles")
        for raw in ucode:
            ls.append(ISA.gen_signals(self.ucode_signals, raw))
        return ls
    
    def gen_ucode_rom(self) -> list[int]:
        ls = [0 for _ in range(1 << self.ucode_rom.alen)]
        for op in self.opcodes.values():
            addr  = insert_val(0, self.ucode_rom.opcode_addr, op.id)
            ucode = self.gen_ucode(op)
            for i in range(len(ucode)):
                ls[insert_val(addr, self.ucode_rom.cycle_addr, i)] = ucode[i]
        return ls
