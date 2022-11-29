import ccxt
import ccxt.async_support as ccxt_async
import httpx
from fastapi import HTTPException
from pprint import pprint
from pydantic import BaseModel
from .binance import Binance
from .upbit import Upbit
from .bybit import Bybit
from .bitget import Bitget
from .stock import KoreaInvestment
from utility import settings, log_message
from .database import db


class Exchange(BaseModel):
    UPBIT: Upbit | None = None
    BINANCE: Binance | None = None
    BYBIT: Bybit | None = None
    BITGET: Bitget | None = None
    KIS1: KoreaInvestment | None = None
    KIS2: KoreaInvestment | None = None
    KIS3: KoreaInvestment | None = None
    KIS4: KoreaInvestment | None = None

    class Config:
        arbitrary_types_allowed = True


payload = {}


def get_exchange(exchange_name, kis_number=None):
    global payload
    if exchange_name in ("UPBIT", "BINANCE", "BYBIT", "BITGET"):
        KEY, SECRET, PASSPHRASE = check_key(exchange_name)
        if exchange_name == "BITGET":
            payload |= {exchange_name: globals()[exchange_name.title()](KEY, SECRET, PASSPHRASE)}
        else:
            payload |= {exchange_name: globals()[exchange_name.title()](KEY, SECRET)}
        # print(payload, exchange_name, id(payload[exchange_name]))

        return Exchange(**payload)

    elif exchange_name in ("KRX", "NASDAQ", "NYSE", "AMEX"):
        _kis = f"KIS{kis_number}"
        key = check_key(_kis)
        KEY, SECRET, ACCOUNT_NUMBER, ACCOUNT_CODE = key
        if not payload.get(_kis):
            payload |= {_kis: globals()["KoreaInvestment"](KEY, SECRET, ACCOUNT_NUMBER, ACCOUNT_CODE, kis_number)}
        exchange = Exchange(**payload)
        kis: KoreaInvestment = exchange.dict()[_kis]
        kis.auth()
        # print(payload, _kis, id(payload[_kis]))
        return kis


def check_key(exchange_name):
    settings_dict = settings.dict()
    if exchange_name in ("UPBIT", "BINANCE", "BYBIT", "BITGET"):
        key = settings_dict.get(exchange_name+"_KEY")
        secret = settings_dict.get(exchange_name+"_SECRET")
        passphrase = settings_dict.get(exchange_name+"_PASSPHRASE")
        if not key:
            msg = f"{exchange_name}_KEY가 없습니다"
            log_message(msg)
            raise HTTPException(
                status_code=404, detail=msg)
        elif not secret:
            msg = f"{exchange_name}_SECRET가 없습니다"
            log_message(msg)
            raise HTTPException(
                status_code=404, detail=msg)
        return key, secret, passphrase
    elif exchange_name in ("KIS1", "KIS2", "KIS3", "KIS4"):
        key = settings_dict.get(f"{exchange_name}_KEY")
        secret = settings_dict.get(f"{exchange_name}_SECRET")
        account_number = settings_dict.get(f"{exchange_name}_ACCOUNT_NUMBER")
        account_code = settings_dict.get(f"{exchange_name}_ACCOUNT_CODE")
        print("env파일:", key, secret, account_number, account_code)
        if key and secret and account_number and account_code:
            return key, secret, account_number, account_code
        else:
            raise Exception(f"{exchange_name} 키가 없습니다")
