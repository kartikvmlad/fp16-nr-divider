# SPDX-FileCopyrightText: © 2026 Vikas, Shreekara, SreeHarsha, Girish, Kartik, Tharun
# SPDX-License-Identifier: Apache-2.0
#
# cocotb tests for the FP16 Newton-Raphson divider. Drives the Tiny Tapeout byte protocol
# (address {uio[4], uio[1:0]}, write strobe uio[2], start uio[3]) and checks results and flags
# against model/fp16_div_model.py (itself proven against exact rational arithmetic).
# The tests only use pins, so they run unchanged on the gate-level netlist (make GATES=yes).

import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "model"))
from fp16_div_model import fp16_div  # noqa: E402

WR, START = 0x04, 0x08
TIMEOUT = 200          # clocks; a divide takes 7 with K=8 (20 with K=2); worst case 42


def pins(addr):
    """uio_in value for a 3-bit register address: {uio[4], uio[1:0]}."""
    return ((addr & 4) << 2) | (addr & 3)


async def reset(dut):
    clock = Clock(dut.clk, 30, unit="ns")       # 33.3 MHz
    cocotb.start_soon(clock.start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def write_byte(dut, addr, data):
    dut.ui_in.value = data
    dut.uio_in.value = WR | pins(addr)
    await ClockCycles(dut.clk, 3)
    dut.uio_in.value = pins(addr)
    await ClockCycles(dut.clk, 1)


async def read_byte(dut, addr):
    dut.uio_in.value = pins(addr)
    await ClockCycles(dut.clk, 1)
    return int(dut.uo_out.value)


async def write_operands(dut, a, b):
    await write_byte(dut, 0, a & 0xFF)
    await write_byte(dut, 1, a >> 8)
    await write_byte(dut, 2, b & 0xFF)
    await write_byte(dut, 3, b >> 8)


async def pulse_start(dut):
    dut.uio_in.value = START
    await ClockCycles(dut.clk, 3)
    dut.uio_in.value = 0


async def wait_done(dut, what=""):
    for _ in range(TIMEOUT):
        await ClockCycles(dut.clk, 1)
        if int(dut.uio_out.value) & 0x80:
            return
    raise AssertionError(f"timeout {what}")


async def read_result(dut):
    q = await read_byte(dut, 0)
    q |= (await read_byte(dut, 1)) << 8
    flags = await read_byte(dut, 4)
    return q, flags


async def divide(dut, a, b):
    await write_operands(dut, a, b)
    await pulse_start(dut)
    await wait_done(dut, f"a={a:04X} b={b:04X}")
    return await read_result(dut)


async def check(dut, a, b):
    q, flags = await divide(dut, a, b)
    er, ef = fp16_div(a, b)
    er, ef = int(er), int(ef)
    # flags byte = {fault, corrected, 0, invalid, divzero, overflow, underflow, inexact}
    assert (q, flags) == (er, ef), \
        f"{a:04X}/{b:04X}: got {q:04X} flags {flags:08b}, expected {er:04X} flags {ef:05b}"


CORNERS = [0x0000, 0x8000, 0x0001, 0x03FF, 0x0400, 0x3C00, 0xBC00, 0x4000, 0x3555, 0x7BFF, 0xFBFF,
           0x7C00, 0xFC00, 0x7E00, 0x7D00, 0x0200, 0x0401, 0x3BFF, 0x3C01, 0x5640]


@cocotb.test()
async def test_basic(dut):
    await reset(dut)
    dut._log.info("1.0 / 2.0 = 0.5")
    q, flags = await divide(dut, 0x3C00, 0x4000)
    assert q == 0x3800 and flags == 0
    dut._log.info("1.0 / 3.0 = 0x3555, inexact")
    q, flags = await divide(dut, 0x3C00, 0x4200)
    assert q == 0x3555 and flags == 0b00001


@cocotb.test()
async def test_corners(dut):
    await reset(dut)
    for a in CORNERS:
        for b in CORNERS:
            await check(dut, a, b)
    dut._log.info(f"{len(CORNERS) ** 2} corner-case pairs passed")


@cocotb.test()
async def test_random(dut):
    await reset(dut)
    rng = random.Random(2026)
    n = int(os.environ.get("N_RANDOM", "1000"))
    for _ in range(n):
        await check(dut, rng.getrandbits(16), rng.getrandbits(16))
    dut._log.info(f"{n} random pairs passed")


@cocotb.test()
async def test_cycle_count(dut):
    """Two normal operands: busy is high for exactly (multiply steps + 1) clocks.

    K = multiplier digit width of the build (-DFP16_K, default 8; set FP16_K in the environment to match).
    With K = 8 a divide takes 7 clocks from the start edge to done, with K = 4 it takes 11, with K = 2 it takes 20."""
    await reset(dut)
    k = int(os.environ.get("FP16_K", "8"))
    ceil = lambda a, b: -(-a // b)
    steps = 2 * ceil(7, k) + ceil(8, k) + ceil(11, k)
    await write_operands(dut, 0x4900, 0x3E00)        # 10.0 / 1.5, both normal
    dut.uio_in.value = START
    n_busy = 0
    seen_busy = False
    for _ in range(TIMEOUT):
        await ClockCycles(dut.clk, 1)
        busy = bool(int(dut.uio_out.value) & 0x40)
        if busy:
            n_busy += 1
            seen_busy = True
        elif seen_busy:
            break
    dut.uio_in.value = 0
    dut._log.info(f"K={k}: busy for {n_busy} clocks (steps {steps} + FIN 1); divide = {n_busy + 1} clocks from the start edge")
    assert n_busy == steps + 1
    q, flags = await read_result(dut)
    er, ef = fp16_div(0x4900, 0x3E00)
    assert (q, flags) == (int(er), int(ef))


@cocotb.test()
async def test_write_while_busy(dut):
    """Operands are frozen during a divide; a strobe held across it lands afterwards."""
    await reset(dut)
    a, b, a2 = 0x4567, 0x3A31, 0x12
    await write_operands(dut, a, b)
    dut.uio_in.value = START
    await ClockCycles(dut.clk, 3)
    # divide is running: present a new A low byte and hold the strobe until well after done
    dut.ui_in.value = a2
    dut.uio_in.value = WR | pins(0)
    await wait_done(dut)
    await ClockCycles(dut.clk, 3)
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 1)
    q, flags = await read_result(dut)
    er, ef = fp16_div(a, b)
    assert (q, flags) == (int(er), int(ef)), "operands changed during the divide"
    # the held write must have landed once the divide finished
    await pulse_start(dut)
    await wait_done(dut)
    q, _ = await read_result(dut)
    er, _ = fp16_div((a & 0xFF00) | a2, b)
    assert q == int(er), "write held across a divide was lost"


@cocotb.test()
async def test_start_while_busy(dut):
    """A start pulse during a divide is ignored and does not disturb it."""
    await reset(dut)
    a, b = 0x5A5A, 0x2B17
    await write_operands(dut, a, b)
    await pulse_start(dut)
    await ClockCycles(dut.clk, 4)
    await pulse_start(dut)                      # second start, mid-divide
    # the stray start clears the sticky done flag, so wait on busy (uio_out[6]) instead
    for _ in range(TIMEOUT):
        await ClockCycles(dut.clk, 1)
        if not int(dut.uio_out.value) & 0x40:
            break
    await ClockCycles(dut.clk, 2)
    q, flags = await read_result(dut)
    er, ef = fp16_div(a, b)
    assert (q, flags) == (int(er), int(ef))


@cocotb.test()
async def test_back_to_back(dut):
    """Many divides in a row; result and flags always belong to the latest divide."""
    await reset(dut)
    rng = random.Random(7)
    prev = None
    for _ in range(100):
        a, b = rng.getrandbits(16), rng.getrandbits(16)
        await check(dut, a, b)
        prev = (a, b)
    # restart with unchanged operands: same answer
    await pulse_start(dut)
    await wait_done(dut)
    q, flags = await read_result(dut)
    er, ef = fp16_div(*prev)
    assert (q, flags) == (int(er), int(ef))


@cocotb.test()
async def test_reset_mid_divide(dut):
    """Reset in the middle of a divide aborts it; the next divide is correct."""
    await reset(dut)
    await write_operands(dut, 0x4900, 0x3E00)
    await pulse_start(dut)
    await ClockCycles(dut.clk, 2)
    assert int(dut.uio_out.value) & 0x40, "core should be busy"
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 3)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)
    assert int(dut.uio_out.value) & 0xC0 == 0, "busy / done must clear on reset"
    for a, b in ((0x3C00, 0x4200), (0x0001, 0x7BFF), (0x7BFF, 0x0400)):
        await check(dut, a, b)


@cocotb.test()
async def test_register_map(dut):
    """Address map: Q bytes, flags, status."""
    await reset(dut)
    await check(dut, 0x3C00, 0x0000)             # 1/0: inf, divzero
    q, flags = await read_result(dut)
    assert q == 0x7C00 and flags == 0b01000
    assert (await read_byte(dut, 2)) == 0 and (await read_byte(dut, 3)) == 0
    status = await read_byte(dut, 5)
    assert status & 0x3 == 0x1, f"status {status:08b}: done must be set, busy clear"
    assert (await read_byte(dut, 6)) == status and (await read_byte(dut, 7)) == status


@cocotb.test()
async def test_watchdog(dut):
    """A divide that stops without finishing ends with DONE and the fault flag (RTL only: pokes an internal flop)."""
    try:
        core = dut.user_project.u_core          # exists in RTL only
        core.run
    except AttributeError:
        dut._log.info("skipped at gate level (needs an RTL signal)")
        return
    await reset(dut)
    await write_operands(dut, 0x4900, 0x3E00)
    await pulse_start(dut)
    await ClockCycles(dut.clk, 4)
    assert int(dut.uio_out.value) & 0x40, "core should be busy"
    core.run.value = 0                      # the core silently stops: busy would drop, done never comes
    await wait_done(dut, "watchdog")
    flags = await read_byte(dut, 4)
    assert flags & 0x80, f"fault flag must be set, flags={flags:08b}"
    # and the divider recovers: the next divide is correct and fault-free
    await check(dut, 0x3C00, 0x4200)
