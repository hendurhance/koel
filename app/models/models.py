from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declared_attr
from app.db.database import Base


class Currency(Base):
    __tablename__ = "currencies"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    name_plural = Column(String(100), nullable=True)
    code = Column(String(3), nullable=False)
    symbol = Column(String(10), nullable=False)
    decimal_digits = Column(Integer, nullable=False)
    icon = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships pointing to ExchangeRate
    base_rates = relationship(
        "ExchangeRate",
        back_populates="base_currency",
        foreign_keys="ExchangeRate.base_currency_id",
    )
    target_rates = relationship(
        "ExchangeRate",
        back_populates="target_currency",
        foreign_keys="ExchangeRate.target_currency_id",
    )

    @declared_attr
    def __table_args__(cls):
        return (
            UniqueConstraint("code", name=f"unique_{cls.__tablename__}_code"),
            Index(f"{cls.__tablename__}_index", "code"),
        )


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True)
    base_currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    target_currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    rate = Column(Float, nullable=False)
    source = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    base_currency = relationship("Currency", foreign_keys=[base_currency_id])
    target_currency = relationship("Currency", foreign_keys=[target_currency_id])

    @declared_attr
    def __table_args__(cls):
        return (
            UniqueConstraint(
                "base_currency_id",
                "target_currency_id",
                "created_at",
                name=f"unique_{cls.__tablename__}",
            ),
            Index(
                f"{cls.__tablename__}_index",
                "base_currency_id",
                "target_currency_id",
                "created_at",
            ),
        )
