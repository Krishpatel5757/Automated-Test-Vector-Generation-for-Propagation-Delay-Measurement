
N_ADD = 8
N_MUL = 4


def to_bits(value, width):
    return [(value >> i) & 1 for i in range(width - 1, -1, -1)]


critical_adder_cases = []
critical_adder_operands = set()

for A in range(2 ** N_ADD):
    for B in range(2 ** N_ADD):

        total = A + B

        lsb_generate = (A & 1) == 1 and (B & 1) == 1

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