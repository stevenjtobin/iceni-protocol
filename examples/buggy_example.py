def transfer(accounts, src, dst, amount):
    # demo input for `iceni run review examples/buggy_example.py`
    accounts[src] -= amount          # no balance check
    accounts[dst] += amount          # no validation that dst exists
    return accounts[src]
