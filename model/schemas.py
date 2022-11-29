from pydantic import BaseModel, BaseSettings, validator, root_validator
from typing import Literal
import os
from pathlib import Path

current_file_direcotry = os.path.dirname(os.path.realpath(__file__))
parent_directory = Path(current_file_direcotry).parent
env = "dev" if os.path.exists(f"{parent_directory}/dev.env") else "prod"

crypto = ("BINANCE", "BITGET", "BYBIT", "UPBIT")
stock = ("KRX", "NASDAQ", "NYSE", "AMEX")
crypto_futures_code = ("PERP", ".P")


class Settings(BaseSettings):
    PASSWORD: str
    WHITELIST: list[str] | None = None
    PORT: int | None = None
    DISCORD_WEBHOOK_URL: str | None = None
    UPBIT_KEY: str | None = None
    UPBIT_SECRET: str | None = None
    BINANCE_KEY: str | None = None
    BINANCE_SECRET: str | None = None
    BYBIT_KEY: str | None = None
    BYBIT_SECRET: str | None = None
    BITGET_KEY: str | None = None
    BITGET_SECRET: str | None = None
    BITGET_PASSPHRASE: str | None = None
    KIS1_ACCOUNT_NUMBER: str | None = None
    KIS1_ACCOUNT_CODE: str | None = None
    KIS1_KEY: str | None = None
    KIS1_SECRET: str | None = None
    KIS2_ACCOUNT_NUMBER: str | None = None
    KIS2_ACCOUNT_CODE: str | None = None
    KIS2_KEY: str | None = None
    KIS2_SECRET: str | None = None
    KIS3_ACCOUNT_NUMBER: str | None = None
    KIS3_ACCOUNT_CODE: str | None = None
    KIS3_KEY: str | None = None
    KIS3_SECRET: str | None = None
    KIS4_ACCOUNT_NUMBER: str | None = None
    KIS4_ACCOUNT_CODE: str | None = None
    KIS4_KEY: str | None = None
    KIS4_SECRET: str | None = None

    class Config:
        env_file = f'{parent_directory}/.env' if env == "prod" else f'{parent_directory}/dev.env'
        env_file_encoding = "utf-8"


class OrderBase(BaseModel):
    password: str
    exchange: Literal["UPBIT", "BINANCE", "BYBIT", "BITGET", "KRX", "NASDAQ", "NYSE", "AMEX"]
    base: str
    quote: Literal["KRW", "USDT", "USDTPERP", "BUSD", "BUSDPERP", "USDT.P", "USD"]
    type: Literal["market", "limit"]
    side: Literal["buy", "sell", "entry/buy", "entry/sell", "close/buy", "close/sell"]
    amount: float | None = None
    price: float
    cost: float | None = None
    percent: float | None = None
    leverage: int | None = None
    stop_price: float | None = None
    profit_price: float | None = None
    order_name: str = "주문"
    kis_number: int | None = 1
    is_crypto: bool | None = None
    is_stock: bool | None = None
    is_futures: bool | None = None

    @ validator("password")
    def password_validate(cls, v):
        setting = Settings()
        if v != setting.PASSWORD:
            raise ValueError("비밀번호가 틀렸습니다")
        return v

    @ root_validator(pre=True)
    def root_validate(cls, values):
        # "NaN" to None
        for key, value in values.items():
            if value in ("NaN", ""):
                values[key] = None
        if values["exchange"] in crypto:
            values["is_crypto"] = True
            if any([values["quote"].endswith(code) for code in crypto_futures_code]):
                values["is_futures"] = True
        elif values["exchange"] in stock:
            values["is_stock"] = True

        return values


class MarketOrder(OrderBase):
    price: float | None = None
    type: Literal["market"] = "market"


class PriceRequest(BaseModel):
    exchange: Literal["UPBIT", "BINANCE", "BYBIT", "BITGET"]
    base: str
    quote: Literal["KRW", "USDT", "USDTPERP", "BUSD", "BUSDPERP", "USDT.P", "USD"]
