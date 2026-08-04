from pydantic import BaseModel


class CurrencyOut(BaseModel):
    alpha_code: str
    name: str
    minor_unit: int | None
    symbol: str | None
