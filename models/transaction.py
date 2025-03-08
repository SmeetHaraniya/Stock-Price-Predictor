from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Transaction(BaseModel):
    user_id: str
    symbol: str
    shares: int
    price: float
    transaction_type: str
    profit_loss: Optional[float]
    timestamp: datetime = datetime.now()