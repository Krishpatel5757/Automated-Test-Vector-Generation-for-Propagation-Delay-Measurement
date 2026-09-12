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

TRUTH_TABLE_CSV   = "Magnitude_comparitor.csv"
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
    print("Apply this stimulus in the external simulator (Cadence),")
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

*(full export: [`Less.csv`](./Less.csv))*

**Final computed delay table** (`Less_delay.csv`), first few rows:

| time | output_transition | max_input_transition | delay | input_combination |
|---|---|---|---|---|
| 5.00E-09 | 5.06E-09 | 5.05E-09 | 1.37E-11 | '1001 |
| 1.00E-08 | 1.01E-08 | 1.01E-08 | 1.33E-11 | '0001 |
| 1.50E-08 | 0 | 1.51E-08 | 0 | '1001 |
| 2.00E-08 | 2.01E-08 | 2.01E-08 | 1.34E-11 | '1010 |
| 2.50E-08 | 2.51E-08 | 2.51E-08 | 1.41E-11 | '0010 |

*(full result: [`Less_delay.csv`](./Less_delay.csv))*

**Reading a row:** the transition into input combination `1001` at t = 5.00ns produces a delay of **13.7 ps**; the following transition into `0001` produces **13.3 ps**. Rows with `delay = 0` mark input transitions that didn't cause an output edge (part of the 0-1-0 bracketing sequence, not a measurement itself) these are expected and simply skipped when reporting the maximum.

The maximum value across the `delay` column is the worst-case propagation delay for this output, printed directly to the console when the script runs.
