
# CPU any% speedrun (real)

Imma call this one "Stovepipe"

This is a one-night "CPU" "speedrun" where I go at very high speeds to make CPU...



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
