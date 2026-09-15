# Automated-Test-Vector-Generation-for-Propagation-Delay-Measurement

A Python-based workflow to automatically generate test vectors for digital circuits and measure propagation delay.

---



Measuring propagation delay reliably requires two things from the test sequence:

1. **One input bit changes at a time.** With multiple bits changing together, you can't tell which bit actually caused the output to switch.
2. **The output must actually transition (0→1 or 1→0).** If the output stays constant, there's nothing to measure — no rising/falling edge exists to time.

So every test case needs a **0→1→0** or **1→0→1** pattern on the output, which lets a single test case capture both a rising and a falling delay.

Gray code doesn't work here, it guarantees single-bit input changes, but not that the output changes on every step. A dedicated selection process is needed to build a sequence that satisfies both conditions simultaneously.

---

## Method, illustrated on a 2-bit magnitude comparator

<details>
<summary><b>Truth table</b> (click to expand)</summary>

| A1 | A0 | B1 | B0 | L | E | G |
|----|----|----|----|----|----|----|
| 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| 0 | 0 | 1 | 1 | 1 | 0 | 0 |
| 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| 0 | 1 | 1 | 0 | 1 | 0 | 0 |
| 0 | 1 | 1 | 1 | 1 | 0 | 0 |
| 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| 1 | 0 | 0 | 1 | 0 | 0 | 1 |
| 1 | 0 | 1 | 0 | 0 | 1 | 0 |
| 1 | 0 | 1 | 1 | 1 | 0 | 0 |
| 1 | 1 | 0 | 0 | 0 | 0 | 1 |
| 1 | 1 | 0 | 1 | 0 | 0 | 1 |
| 1 | 1 | 1 | 0 | 0 | 0 | 1 |
| 1 | 1 | 1 | 1 | 0 | 1 | 0 |

</details>

**Step 1 — Pick an output and find its 1-vectors.**
Take output `L` (Less-than). The input combinations giving `L = 1` are:
`0001, 0010, 0011, 0110, 0111, 1011`.
These become the **reference set**  any candidate vector is checked against this set to decide if it produces a 1 or 0.

**Step 2 — Flip one bit at a time and test validity.**
Starting from `0001`, flip bit 4 → `0000` (gives `L = 0`). Arranging `0000 → 0001 → 0000` gives the output sequence `0-1-0`  a valid pair.

Now flip bit 3 of `0001` instead → `0011`, which is *also* in the reference set (`L = 1`). That candidate is **rejected**, because the sequence would read `1-1-1`  no transition, nothing to measure.

**Step 3 — Repeat for every bit, every reference vector, and both outputs (`L=1` and `L=0` cases).**
The `L=0` case follows the mirror logic and produces `1-0-1` sequences instead.

This flip-and-check process is exactly what the script below automates it's impractical to do by hand once input width grows past a couple of bits.

---

## Vector generation

<details>
<summary><b>Code</b> : <code>generate_bitstream()</code></summary>

```python
import numpy as np
import pandas as pd

TRUTH_TABLE_CSV   = "Magnitude_comparator.csv"
DELAY_CSV         = "Less.csv"
STIMULUS_OUT_FILE = "Less_bitstream.txt"
FINAL_OUT_FILE    = "Less_delay.csv"

num_input_bits = 4
output_col     = 5          # column index of the output being tested (1-based)
select_bits    = [1,2,3,4]  # which input bits to flip
time_step      = 5e-9
min_pulse_width = 500e-12

def generate_bitstream():
    df_1 = pd.read_csv(TRUTH_TABLE_CSV)
    data = df_1.to_numpy()

    P_list = [x[:num_input_bits] for x in data if x[output_col - 1] == 1]
    P_set = {tuple(r.tolist()) for r in P_list}

    P_out = []
    for j in select_bits:
        for row in P_list:
            original = row.copy()
            converted = row.copy()
            converted[j-1] ^= 1

            if tuple(converted.tolist()) not in P_set:
                P_out.append(converted.copy())
                P_out.append(original.copy())
                P_out.append(converted.copy())

    p_matrix = np.array(P_out)
    streams = [''.join(map(str,row)) for row in p_matrix.T]

    with open(STIMULUS_OUT_FILE, "w") as f:
        for i, s in enumerate(streams):
            line = f"streams[{i}] = {s}"
            print(line)
            f.write(line + "\n")

    print(len(p_matrix))
    return streams, p_matrix
```

</details>

**Config, briefly:**

| Parameter | Meaning |
|---|---|
| `TRUTH_TABLE_CSV` | Truth table input: input columns first, output columns last |
| `num_input_bits` | Number of input bits in the truth table |
| `output_col` | Which output column to test (e.g. 5 = `L`, 6 = `E`) |
| `select_bits` | Which input bit positions to flip during generation |
| `time_step` | Simulation frequency (5 ns per test case here) |
| `min_pulse_width` | Pulses shorter than this are treated as spikes/glitches, not real transitions |

**Output** : one bit stream per input line, ready to paste directly into Cadence's `Vbit` component:

```
input_pattern[0] = 101101101101000111000000000111000111
input_pattern[1] = 000000111111101101000111111000000000
input_pattern[2] = 000111111111000111010010010010000111
input_pattern[3] = 111000000111111111000000111111010010
```

---

## The delay-measurement problem

Cadence's built-in `delay()` function works per-measurement: you supply a signal name, edge type, edge number, and threshold, and it returns one number. It doesn't scale to hundreds of auto-generated test vectors and it isn't robust on its own, since switching noise can produce small spikes that the tool counts as valid edges, breaking the intended 0-1-0 sequence.

**Approach:** use Cadence's `cross()` function to export the time at which each signal crosses 50% VDD, for both inputs and output, as a CSV. A second script then reconstructs delay from that raw crossing-time data filtering spikes by pulse width, matching each output transition to its corresponding input transition, and subtracting.

<details>
<summary><b>Code</b> : <code>analyze_delay()</code></summary>

```python
def analyze_delay(p_matrix):
    df_2 = pd.read_csv(DELAY_CSV)
    df_2 = df_2.apply(pd.to_numeric, errors='coerce').fillna(0)
    data = df_2.to_numpy()

    num_rows = int(round(data[-1,-1] / time_step))
    num_cols = data.shape[1] - 1
    calc = np.zeros((num_rows, num_cols))
    final = np.zeros((num_rows, 4))
    final[:, 0] = np.arange(1, num_rows + 1) * time_step

    last_col_data = data[:, num_cols]
    i = 0
    while i < len(last_col_data) - 1:
        t_rise = last_col_data[i]
        t_fall = last_col_data[i + 1]
        pulse_width = t_fall - t_rise
        if pulse_width >= min_pulse_width:
            row_index_rise = int(round((t_rise - time_step) / time_step))
            if 0 <= row_index_rise < num_rows:
                final[row_index_rise, 1] = t_rise
            row_index_fall = int(round((t_fall - time_step) / time_step))
            if 0 <= row_index_fall < num_rows:
                final[row_index_fall, 1] = t_fall
        i += 2

    for col_j in range(num_input_bits):
        for val in data[:, col_j]:
            row_index = int(round((val - time_step) / time_step))
            if 0 <= row_index < num_rows:
                calc[row_index, col_j] = val

    for r in range(len(calc)):
        final[r, 2] = np.max(calc[r])

    mask = (final[:, 1] != 0) & (final[:, 2] != 0)
    final[mask, 3] = final[mask, 1] - final[mask, 2]
    final_max = np.max(final[:, 3])
    print("final max delay:", final_max)

    final_df = pd.DataFrame(
        final,
        columns=["time", "output_transition", "max_input_transition", "delay"]
    )

    if p_matrix is not None:
        input_combos = [''.join(map(str, row)) for row in p_matrix]
        input_combos += [""] * (num_rows - len(input_combos))
        final_df["input_combination"] = ["'" + c for c in input_combos[:num_rows]]

    final_df.to_csv(FINAL_OUT_FILE, index=False)
    return final_max


if __name__ == "__main__":
    _, p_matrix = generate_bitstream()
    print(f"\nStimulus written to '{STIMULUS_OUT_FILE}'.")
    print("Apply this stimulus in the external simulator ,")
    print(f"then place the resulting CSV as '{DELAY_CSV}' in this folder.")
    input("\nPress Enter once the simulation is done and the CSV is ready...")
    analyze_delay(p_matrix)
    print(f"'final' array written to '{FINAL_OUT_FILE}'.")
```

</details>

**What it does, in short:** reads the crossing-time CSV, identifies genuine output pulses by width (rejecting spikes), matches each surviving output transition to the latest input transition before it, and writes the subtraction as delay alongside the exact input combination that produced it.

---

## Result

**Simulator export** (`cross()` output crossing times for A1, A0, B1, B0, and `Less`), first few rows:

| A1 | A0 | B1 | B0 | Less |
|---|---|---|---|---|
| 5.05E-09 | 3.01E-08 | 1.51E-08 | 1.51E-08 | 5.06E-09 |
| 1.01E-08 | 6.51E-08 | 6.01E-08 | 4.51E-08 | 1.01E-08 |
| 2.01E-08 | 7.01E-08 | 7.51E-08 | 9.01E-08 | 2.01E-08 |
| 2.51E-08 | 8.01E-08 | 9.01E-08 | 1.20E-07 | 2.51E-08 |

*(full export: [`DELAY_CSV.csv`](./DELAY_CSV.csv))*

**Final computed delay table** (`Less_delay.csv`), first few rows:

| time | output_transition | max_input_transition | delay | input_combination |
|---|---|---|---|---|
| 5.00E-09 | 5.06E-09 | 5.05E-09 | 1.37E-11 | '1001 |
| 1.00E-08 | 1.01E-08 | 1.01E-08 | 1.33E-11 | '0001 |
| 1.50E-08 | 0 | 1.51E-08 | 0 | '1001 |
| 2.00E-08 | 2.01E-08 | 2.01E-08 | 1.34E-11 | '1010 |
| 2.50E-08 | 2.51E-08 | 2.51E-08 | 1.41E-11 | '0010 |

*(full result: [`FINAL_OUT_FILE.csv`](./FINAL_OUT_FILE.csv))*

**Reading a row:** the transition into input combination `1001` at t = 5.00ns produces a delay of **13.7 ps**; the following transition into `0001` produces **13.3 ps**. Rows with `delay = 0` mark input transitions that didn't cause an output edge (part of the 0-1-0 bracketing sequence, not a measurement itself) these are expected and simply skipped when reporting the maximum.

The maximum value across the `delay` column is the worst-case propagation delay for this output, printed directly to the console when the script runs.

---

## Scaling to larger circuits

The exhaustive method above works fine at small scale the 2-bit comparator's 3 outputs need only 120 vectors total. It doesn't stay that cheap: a 4-bit multiplier has 8 outputs across 256 input combinations, which the same method turns into ~7260 vectors.

### Critical path analysis

Not every output needs testing. In a 4-bit Vedic multiplier, the low-order product bits pass through only a few gates and structurally can't produce the worst-case delay, so they're excluded outright. The MSB (P7) passes through the most gates and is the primary candidate; P6 was tested too as a safety check, but it consistently showed a lower delay, so only P7 was kept for further analysis.

| Stage | Outputs tested | Vectors |
|---|---|---|
| All outputs (naive) | 8 | ~7260 |
| Critical-path candidates (P7 + P6 safety check) | 2 | 1164 |
| Final (P7 only, once P6 confirmed non-critical) | 1 | 360 |

That's roughly a 7× reduction, and once confirmed, only P7's 360 vectors are needed for any further analysis on this circuit.

### Logic optimization

Some single outputs still generate too many vectors on their own. An 8-bit ripple-carry adder has 9 outputs across 65,536 input combinations; critical-path analysis narrows this to two outputs S7 and Cout, since the carry chain guarantees the worst-case delay lands at the final stage. (Whether S7 or Cout is worse depends on whether the adder uses standard logic or pass-transistor logic.)

Even narrowed to two outputs, exhaustively flipping every bit still produces a large number of vectors:

| Stage | S7 vectors | Cout vectors | Total |
|---|---|---|---|
| Critical-path outputs, full flip | 391,680 | 195,072 | 586,752 |
| Logic-optimized (flip A0/B0 only) | 1,536 | 768 | 2,304 |

Since the carry chain is longest only when it has to propagate all the way from LSB to MSB, flipping just the LSB input bits (A0, B0) is enough to generate that worst-case chain no other bit pair produces a longer path. Restricting the flip set this way gives the ~256× reduction above. It could likely be pushed further, but that needs simulation to confirm rather than being assumed from the logic alone.

> **Note:** both optimizations above are structure-specific, not general rules they depend on the topology and technology (CMOS, FinFET, CNFET) in use:
> - Some multiplier designs have their critical path in the middle rather than at the MSB — don't assume the MSB is always worst-case.
> - Carry-look-ahead adders don't have a serial carry chain, so the "flip only the LSB" trick above doesn't apply — it's specific to ripple-carry structures.
> - Some adder architectures generate sum before carry, or vice versa, at the transistor level — don't assume the generation order.
>
> Always verify with one or two manual test cases whenever the circuit, topology, or code/conditions change.

## Cascading multiple modules (MAC: multiplier + adder)

Why cascading breaks the single-module assumption

A cascaded module (e.g. a MAC's combinational path 4-bit multiplier feeding into an 8-bit RCA) doesn't follow one shared truth table, and the critical path shifts: it now has to pass through both modules at once, not just one.

The easy fallback is to measure each module's delay separately and add them this gives a valid upper bound, since the true cascaded delay can't exceed it. But it isn't tight: the RCA starts consuming the multiplier's output bits (LSB first) as soon as they're produced, so by the time the multiplier's MSB (P7) finally resolves, most of the adder chain has already settled. The actual worst-case delay is smaller than the naive sum.

Vector generation strategy

The same single-bit-flip, 0-1-0/1-0-1 patterning rule still applies, but now a candidate vector has to satisfy the critical condition of both modules at once, not just one.

Approach:

Build the adder's critical-case set first (LSB carry-generate + full propagate through the rest of the chain).
Build the multiplier's critical-case set, keeping only cases whose product lands in the adder's critical-operand set from step 1.
Derive the adder's second operand arithmetically instead of searching for it: target sum = 256, so the second leg = 256 − multiplier_output.

The key simplification: the multiplier's critical case (worst-case delay) almost always drives P7 (its MSB) to 1, i.e. product > 128. Rather than separately hunting for a transition that produces the adder's critical sum pattern and its critical carry pattern, forcing P7's transition to 1 → 0 turns out to generate the needed 1-0-1 pattern for both the sum and carry critical cases simultaneously, so one vector set serves both, instead of building two.

The adder's held-input value (before/after the multiplier's own transition) is set to either 0 or 128 depending on whether that intermediate multiplier output crosses 128, again derived directly rather than searched for.


<details> <summary><b>Code</b> — critical-vector generation for cascaded MAC (multiplier + adder)</summary>
python
    
```

N_ADD = 8
N_MUL = 4


def to_bits(value, width):
    return [(value >> i) & 1 for i in range(width - 1, -1, -1)]


critical_adder_cases = []
critical_adder_operands = set()

for A in range(2 ** N_ADD):
    for B in range(2 ** N_ADD):

        total = A + B


        # LSB carry generation
        lsb_generate = (A & 1) == 1 and (B & 1) == 1

        # Carry propagation through bits 1..6
        propagate = all(
            ((A >> i) & 1) ^ ((B >> i) & 1)
            for i in range(1, N_ADD)
        )

        if lsb_generate and propagate:

            A_bits = to_bits(A, N_ADD)
            B_bits = to_bits(B, N_ADD)

            S_bits = to_bits(total, N_ADD)

            critical_adder_cases.append({
                "A": A,
                "B": B,
                "sum": total,
                "A_bits": A_bits,
                "B_bits": B_bits,
                "S_bits": S_bits
            })
            critical_adder_operands.add(B)


critical_multiplier_cases = []

for A in range(2 ** N_MUL):
    for B in range(2 ** N_MUL):

        product = A * B
        p_bits = to_bits(product,(2*N_MUL))
        
        if p_bits[0] == 1 and product in critical_adder_operands:
        # Toggle multiplier LSB
            A_prev = A ^ 1
            B_prev = B ^ 1
       
            critical_multiplier_cases.append({
                "A": A,
                "B": B,
                "product": product,
                "A_prev": A_prev,
                "B_prev": B_prev,
                "adder_value": (2 ** N_ADD) - product
            })



data_mul = []
data_adder = []

for case in critical_multiplier_cases:

    A = case["A"]
    B = case["B"]

    A_prev = case["A_prev"]
    B_prev = case["B_prev"]

    product = case["product"]
    adder_value = case["adder_value"]

    # Convert multiplier inputs to bits
    A_bits = to_bits(A, N_MUL)
    B_bits = to_bits(B, N_MUL)

    A_prev_bits = to_bits(A_prev, N_MUL)
    B_prev_bits = to_bits(B_prev, N_MUL)

    data_mul.append(A_prev_bits + B_bits)
    data_mul.append(A_bits + B_bits)
    data_mul.append(A_prev_bits + B_bits)

    data_mul.append(A_bits + B_prev_bits)
    data_mul.append(A_bits + B_bits)
    data_mul.append(A_bits + B_prev_bits)

    adder_bits = to_bits(adder_value, N_ADD)

    # A0 changed
    product_A0 = A_prev * B

    if product_A0 > 128:
        previous_adder = [0] * (2 * N_MUL)
    else:
        previous_adder = [1, 0, 0, 0, 0, 0, 0, 0]

    data_adder.append(previous_adder)
    data_adder.append(adder_bits)
    data_adder.append(previous_adder)

    # B0 changed
    product_B0 = A * B_prev

    if product_B0 > 128:
        next_adder = [0] * (2 * N_MUL)
    else:
        next_adder = [1, 0, 0, 0, 0, 0, 0, 0]

    data_adder.append(next_adder)
    data_adder.append(adder_bits)
    data_adder.append(next_adder)

def print_vectors(data, name="list"):

    columns = list(zip(*data))

    for i, column in enumerate(columns):
        pattern = ''.join(map(str, column))
        print(f"{name}_{i} = {pattern}")


print("\nCritical multiplier cases:")
for case in critical_multiplier_cases:
    print(
        f"A={case['A']:2d}, "
        f"B={case['B']:2d}, "
        f"P={case['product']:3d}, "
        f"Q={case['adder_value']:3d}"
    )

print("\nNumber of critical multiplier cases:",
      len(critical_multiplier_cases))

print("\nNumber of generated vectors:",
      len(data_mul))

print("\nMultiplier input vectors:")
print_vectors(data_mul)

print("\nAdder input vectors:")
print_vectors(data_adder)
```

</details>


The reduction comes from two things stacking: only keeping multiplier cases whose product already matches one of the adder's critical operands, and deriving the adder's second leg arithmetically instead of generating it separately, so the module boundary is handled without a combinatorial blow-up.
