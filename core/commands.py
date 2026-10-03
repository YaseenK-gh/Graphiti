import re

from core.accessories import Wallet

GIVE_LIMIT = 1_000_000_000
USAGE = "Usage: /give @s points <amount>"
GIVE = re.compile(r"^/?give\s+@s\s+points\s+(\S+)$", re.IGNORECASE)


def run_command(text: str, wallet: Wallet) -> str:
    line = " ".join((text or "").split())
    if not line:
        return ""
    match = GIVE.match(line)
    if match is None:
        return f"Unknown command. {USAGE}"
    amount = match.group(1).replace(",", "").replace("_", "")
    if not amount.isdigit() or int(amount) <= 0:
        return f"The amount must be a whole number above 0. {USAGE}"
    points = int(amount)
    if points > GIVE_LIMIT:
        return f"You can give at most {GIVE_LIMIT:,} points at a time."
    wallet.add(points)
    return f"Gave {points:,} points. Balance: {wallet.balance:,}"
