from pydantic import BaseModel

class Stocks(BaseModel):
    symbol: str
    name: str
    exchange: str
    shortable: bool