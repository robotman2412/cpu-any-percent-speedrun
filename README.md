
# CPU any% speedrun (real)

Imma call this one "Stovepipe"

This was a one-night "CPU" "speedrun" where I go at very high speeds to make CPU... It took me a total of merely 4 hours to design the hardware!


# How to play with stovepipe
1. Use logisim (the original version) to open `stovepipe.circ`
2. Use the `asm.py` python script to assemble programs (e.g. `fibonacci.stp`)
3. Load the output file (e.g. `out.lhf`) into the RAM in logisim
4. Start the clock and see the magic happening


# Architecture overview

Stovepipe is an 8-bit von Neumann CPU with an 8-bit accumulator and an 8-bit data/address bus.

## Register overview
| Width | Name | Description
| :---- | :--- | :----------
| 8     | A    | Accumulator and general-purpose register
| 8     | B    | Right-hand side of ALU operations
| 1     | CF   | ALU carry out flag
| 1     | ZF   | ALU result zero flag
| 2     | IC   | Instruction stage counter
| 8     | IR   | Instruction register
| 8     | PC   | Program counter

## Instruction-set specification
### Overview
| Format      | Description
| :---------- | :----------
| `nop`       | Does nothing
| `shr`       | Arithmetic shift right
| `shl`       | Arithmetic shift left
| `add imm`   | Add immediate value to accumulator
| `sub imm`   | Subtract immediate value from accumulator
| `xor imm`   | Bitwise-XOR immediate value and accumulator
| `and imm`   | Bitwise-AND immediate value and accumulator
| `or  imm`   | Bitwise-OR immediate value and accumulator
| `li  imm`   | Load immediate value into accumulator
| `add [mem]` | Add memory byte to accumulator
| `sub [mem]` | Subtract memory byte from accumulator
| `xor [mem]` | Bitwise-XOR memory byte and accumulator
| `and [mem]` | Bitwise-AND memory byte and accumulator
| `or  [mem]` | Bitwise-OR memory byte and accumulator
| `lb  [mem]` | Load accumulator from memory
| `cmp imm`   | Compare accumulator to immediate value
| `cmp [mem]` | Compare accumulator to memory byte
| `sb  [mem]` | Store accumulator to memory
| `j   addr`  | Jump to address
| `bcs addr`  | Jump to address if carry flag set
| `beq addr`  | Jump to address if zero flag set
| `bgt addr`  | Jump to address if greater than
| `blt addr`  | Jump to address if less than
| `bcc addr`  | Jump to address if carry flag clear
| `bne addr`  | Jump to address if zero flag clear
| `ble addr`  | Jump to address if less or equal
| `bge addr`  | Jump to address if greater or equal
