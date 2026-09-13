import numpy as np
import pandas as pd

TRUTH_TABLE_CSV   = "Magnitude_comparator.csv"
DELAY_CSV         = "Less.csv"
STIMULUS_OUT_FILE = "Less_bitstream.txt"
FINAL_OUT_FILE    = "Less_delay.csv"

num_input_bits = 4
output_col = 5
select_bits = [1,2,3,4]
time_step = 5e-9
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
    input_pattern = [''.join(map(str,row)) for row in p_matrix.T]
    with open(STIMULUS_OUT_FILE,"w") as f:
        for i, s in enumerate(input_pattern):
            line = f"input_pattern[{i}] = {s}"
            print(line)
            f.write(line + "\n")
    print(len(p_matrix))
    return input_pattern,p_matrix
    

def analyze_delay(p_matrix):
    df_2 = pd.read_csv(DELAY_CSV)
    #df_2 = df_2.iloc[:,1::2]
    df_2 = df_2.apply(pd.to_numeric, errors='coerce').fillna(0)
    data = df_2.to_numpy()

    num_rows = int(round(data[-1,-1] / time_step))
    num_cols = data.shape[1] -1
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
