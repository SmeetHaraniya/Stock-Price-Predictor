from pydantic import BaseModel
from typing import List

class StockHolding(BaseModel):
    user_id: str
    company_symbol: str
    number_of_shares: int = 0
    investment_amount: float = 0.0
    buying_value: List[str] = []