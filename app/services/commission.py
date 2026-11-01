def calc_commission(deal_amount: int, commission_pct: float = 15.0) -> int:
    return int(round(deal_amount * commission_pct / 100))
