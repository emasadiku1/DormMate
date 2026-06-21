"""
services/debt_calculator.py

Example:
    Alice owes Bob $10, Alice owes Carol $5, Dave owes Bob $8.
    Raw balances: {Alice: -15, Bob: +18, Carol: +5, Dave: -8}
    Simplified:
        Dave  → Bob   $8
        Alice → Bob   $10
        Alice → Carol $5
    (3 transactions, same as naive — but in larger graphs the savings are real)
"""

from decimal import Decimal
from typing import NamedTuple


class Transaction(NamedTuple):
    debtor_id: int
    creditor_id: int
    amount: Decimal   # always positive — "debtor pays creditor this much"


def simplify_debts(net_balances: dict[int, Decimal]) -> list[Transaction]:
    """
    Reduce a net-balance map to the minimum number of transactions.

    Args:
        net_balances: {user_id: Decimal} where positive = owed money,
                      negative = owes money.  Values should sum to ~0.

    Returns:
        List of Transaction(debtor_id, creditor_id, amount) sorted by
        amount descending (largest settlement first — nicer UX).
    """
    ZERO = Decimal("0.00")
    EPSILON = Decimal("0.01")   # ignore sub-cent rounding noise

    # Work on a mutable copy; filter out anyone already balanced.
    balances = {uid: Decimal(str(bal)) for uid, bal in net_balances.items()
                if abs(Decimal(str(bal))) >= EPSILON}

    transactions: list[Transaction] = []

    while True:
        # Split into creditors (balance > 0) and debtors (balance < 0).
        creditors = {uid: bal for uid, bal in balances.items() if bal > ZERO}
        debtors   = {uid: bal for uid, bal in balances.items() if bal < ZERO}

        if not creditors or not debtors:
            break

        # Greedy: pair the largest creditor with the largest debtor.
        max_creditor = max(creditors, key=lambda uid: creditors[uid])
        max_debtor   = min(debtors,   key=lambda uid: debtors[uid])   # most negative

        credit = balances[max_creditor]
        debt   = abs(balances[max_debtor])
        amount = min(credit, debt)

        transactions.append(Transaction(
            debtor_id=max_debtor,
            creditor_id=max_creditor,
            amount=amount.quantize(Decimal("0.01")),
        ))

        # Update balances; remove anyone who's been zeroed out.
        balances[max_creditor] -= amount
        balances[max_debtor]   += amount

        if abs(balances[max_creditor]) < EPSILON:
            del balances[max_creditor]
        if abs(balances[max_debtor]) < EPSILON:
            del balances[max_debtor]

    return sorted(transactions, key=lambda t: t.amount, reverse=True)


def compute_net_balances(splits) -> dict[int, Decimal]:
    """
    Helper: derive net balances from a list of ExpenseSplit ORM objects.

    For each unsettled split:
      - the payer is owed  split.amount_owed  (positive)
      - the owing user owes split.amount_owed (negative)

    Splits where the payer IS the owing user are skipped (you don't owe yourself).
    """
    balances: dict[int, Decimal] = {}

    for split in splits:
        if split.is_settled:
            continue

        payer_id = split.expense.payer_id
        ower_id  = split.user_id
        amount   = Decimal(str(split.amount_owed))

        if payer_id == ower_id:
            continue  # person paid their own share — nothing to settle

        balances[payer_id] = balances.get(payer_id, Decimal("0")) + amount
        balances[ower_id]  = balances.get(ower_id,  Decimal("0")) - amount

    return balances