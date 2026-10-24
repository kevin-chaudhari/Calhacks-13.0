"""Create testnet-only wallets for the x402 demo and print the .env lines.

    python scripts/x402_wallets.py            # new wallets for the demo personas + Rally's receiver

Then fund each PAYER address with Base Sepolia test USDC (https://faucet.circle.com, network
"Base Sepolia"). With the exact scheme the facilitator pays gas, so payers need USDC only.
These keys are for testnet play money: never put real funds in them, never commit them.
"""
import json
import sys

try:
    from eth_account import Account
except ImportError:
    sys.exit("pip install 'x402[evm]==2.24.0' first")

PAYERS = ["u_kevin", "u_ana", "u_ravi", "u_maya", "u_kai", "u_eli", "u_jordan", "u_mei", "u_tomas", "u_hana", "u_felix"]

receiver = Account.create()
payers = {u: Account.create() for u in PAYERS}
print("# --- paste into .env (server only; never commit) ---")
print("PAYMENTS=x402_testnet")
print("X402_NETWORK=base-sepolia")
print(f"X402_PAY_TO={receiver.address}")
print(f"X402_PAYER_KEYS='{json.dumps({u: a.key.hex() for u, a in payers.items()})}'")
print(f"# Rally receiver private key (keep it to send refunds): {receiver.key.hex()}")
print("\n# --- fund these with Base Sepolia test USDC at https://faucet.circle.com ---")
for u, a in payers.items():
    print(f"{u:10s} {a.address}")
