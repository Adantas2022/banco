from decimal import Decimal
from dataclasses import dataclass
from typing import Union
import re


@dataclass(frozen=True)
class Money:
    amount: Decimal
    
    @classmethod
    def from_brazilian_currency(cls, value: str) -> "Money":
        if not value:
            return cls(Decimal("0"))
        
        cleaned = re.sub(r"[^\d,.-]", "", str(value))
        cleaned = cleaned.replace(".", "").replace(",", ".")
        
        try:
            return cls(Decimal(cleaned))
        except Exception:
            return cls(Decimal("0"))
    
    @classmethod
    def zero(cls) -> "Money":
        return cls(Decimal("0"))
    
    @classmethod
    def from_number(cls, value: Union[int, float, Decimal]) -> "Money":
        if value is None:
            return cls(Decimal("0"))
        return cls(Decimal(str(value)))
    
    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount + other.amount)
    
    def __radd__(self, other: Union[int, "Money"]) -> "Money":
        if other == 0:
            return self
        if isinstance(other, Money):
            return Money(self.amount + other.amount)
        return NotImplemented
    
    def __sub__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount - other.amount)
    
    def __mul__(self, factor: Union[int, float, Decimal]) -> "Money":
        return Money(self.amount * Decimal(str(factor)))
    
    def to_int(self) -> int:
        return int(self.amount)
    
    def to_float(self) -> float:
        return float(self.amount)
    
    def to_cents(self) -> int:
        return int(self.amount * 100)
    
    def __repr__(self) -> str:
        return f"Money({self.amount})"
