import ccxt
import ccxt.async_support as ccxt_async
import httpx
from fastapi import HTTPException
from pydantic import BaseModel
from .binance import Binance
from .upbit import Upbit
from .bybit import Bybit
from .bitget import Bitget
from .okx import Okx
from .stock import KoreaInvestment
from exchange.utility import settings, log_message
from .database import db
from typing import Literal
import pendulum
import time
from devtools import debug
from loguru import logger


from .model import CRYPTO_EXCHANGES, STOCK_EXCHANGES, MarketOrder


class Exchange(BaseModel):
    UPBIT: Upbit | None = None
    BINANCE: Binance | None = None
    BYBIT: Bybit | None = None
    BITGET: Bitget | None = None
    OKX: Okx | None = None
    KIS1: KoreaInvestment | None = None
    KIS2: KoreaInvestment | None = None
    KIS3: KoreaInvestment | None = None
    KIS4: KoreaInvestment | None = None

    class Config:
        arbitrary_types_allowed = True


payload = {}


def get_exchange(exchange_name: str, kis_number=None):
    global payload
    if exchange_name in CRYPTO_EXCHANGES:
        KEY, SECRET, PASSPHRASE = check_key(exchange_name)
        if not payload.get(exchange_name):
            if exchange_name in ("BITGET", "OKX"):
                payload |= {
                    exchange_name: globals()[exchange_name.title()](
                        KEY, SECRET, PASSPHRASE
                    )
                }
            else:
                if not payload.get(exchange_name):
                    payload |= {
                        exchange_name: globals()[exchange_name.title()](KEY, SECRET)
                    }

        return Exchange(**payload)

    elif exchange_name in ("KRX", "NASDAQ", "NYSE", "AMEX"):
        _kis = f"KIS{kis_number}"
        key = check_key(_kis)
        KEY, SECRET, ACCOUNT_NUMBER, ACCOUNT_CODE = key
        if not payload.get(_kis):
            payload |= {
                _kis: globals()["KoreaInvestment"](
                    KEY, SECRET, ACCOUNT_NUMBER, ACCOUNT_CODE, kis_number
                )
            }
        exchange = Exchange(**payload)
        kis: KoreaInvestment = exchange.dict()[_kis]
        kis.auth()
        return kis


def get_bot(
    exchange_name: Literal[
        "BINANCE", "UPBIT", "BYBIT", "BITGET", "KRX", "NASDAQ", "NYSE", "AMEX", "OKX"
    ],
    kis_number=None,
) -> Binance | Upbit | Bybit | Bitget | KoreaInvestment | Okx:
    exchange_name = exchange_name.upper()
    if exchange_name in CRYPTO_EXCHANGES:
        return get_exchange(exchange_name, kis_number).dict()[exchange_name]
    elif exchange_name in STOCK_EXCHANGES:
        return get_exchange(exchange_name, kis_number)


def check_key(exchange_name):
    settings_dict = settings.dict()
    if exchange_name in CRYPTO_EXCHANGES:
        key = settings_dict.get(exchange_name + "_KEY")
        secret = settings_dict.get(exchange_name + "_SECRET")
        passphrase = settings_dict.get(exchange_name + "_PASSPHRASE")
        if not key:
            msg = f"{exchange_name}_KEY가 없습니다"
            log_message(msg)
            raise HTTPException(status_code=404, detail=msg)
        elif not secret:
            msg = f"{exchange_name}_SECRET가 없습니다"
            log_message(msg)
            raise HTTPException(status_code=404, detail=msg)
        return key, secret, passphrase
    elif exchange_name in ("KIS1", "KIS2", "KIS3", "KIS4"):
        key = settings_dict.get(f"{exchange_name}_KEY")
        secret = settings_dict.get(f"{exchange_name}_SECRET")
        account_number = settings_dict.get(f"{exchange_name}_ACCOUNT_NUMBER")
        account_code = settings_dict.get(f"{exchange_name}_ACCOUNT_CODE")
        if key and secret and account_number and account_code:
            return key, secret, account_number, account_code
        else:
            raise Exception(f"{exchange_name} 키가 없습니다")


def get_today_timestamp(timezone="Asia/Seoul"):
    today = pendulum.today(timezone)
    today_start = int(today.start_of("day").timestamp() * 1000)
    today_end = int(today.end_of("day").timestamp() * 1000)
    return today_start, today_end


def retry(
    func,
    *args,
    order_info: MarketOrder,
    max_attempts=3,
    delay=1,
    instance: Binance | Bybit | Bitget | Upbit | Okx = None,
):
    attempts = 0

    while attempts < max_attempts:
        try:
            result = func(*args)  # 함수 실행
            return result
        except Exception as e:
            logger.error(f"에러 발생: {str(e)}")
            attempts += 1
            if func.__name__ == "create_order":
                if order_info.exchange in ("BINANCE"):
                    if "Internal error" in str(e):
                        time.sleep(delay)  # 재시도 간격 설정
                    elif "position side does not match" in str(e):
                        if instance.position_mode == "one-way":
                            instance.position_mode = "hedge"
                            if order_info.side == "buy":
                                if order_info.is_entry:
                                    positionSide = "LONG"
                                elif order_info.is_close:
                                    positionSide = "SHORT"
                            elif order_info.side == "sell":
                                if order_info.is_entry:
                                    positionSide = "SHORT"
                                elif order_info.is_close:
                                    positionSide = "LONG"

                            params = {"positionSide": positionSide}
                        elif instance.position_mode == "hedge":
                            instance.position_mode = "one-way"
                            if order_info.is_entry:
                                params = {}
                            elif order_info.is_close:
                                params = {"reduceOnly": True}

                        args = tuple(
                            params if i == 5 else arg for i, arg in enumerate(args)
                        )

                    else:
                        attempts = max_attempts
                elif order_info.exchange in ("BYBIT"):
                    if "position idx not match position mode" in str(e):
                        if instance.position_mode == "one-way":
                            instance.position_mode = "hedge"
                            position_idx = None
                            if order_info.side == "buy":
                                if order_info.is_entry:
                                    position_idx = 1
                                    params = {"position_idx": position_idx}
                                elif order_info.is_close:
                                    position_idx = 2
                                    params = {
                                        "reduceOnly": True,
                                        "position_idx": position_idx,
                                    }
                            elif order_info.side == "sell":
                                if order_info.is_entry:
                                    position_idx = 2
                                    params = {"position_idx": position_idx}
                                elif order_info.is_close:
                                    position_idx = 1
                                    params = {
                                        "reduceOnly": True,
                                        "position_idx": position_idx,
                                    }
                        elif instance.position_mode == "hedge":
                            instance.position_mode = "one-way"
                            if order_info.is_entry:
                                params = {"position_idx": 0}
                            elif order_info.is_close:
                                params = {"reduceOnly": True, "position_idx": 0}

                        args = tuple(
                            params if i == 5 else arg for i, arg in enumerate(args)
                        )
                    elif "check your server timestamp" in str(e):
                        bybit: Bybit = instance
                        bybit.load_time_difference()
                    else:
                        attempts = max_attempts

                elif order_info.exchange in ("OKX"):
                    if "posSide error" in str(e):
                        params = {}

                        if instance.position_mode == "one-way":
                            instance.position_mode = "hedge"
                            pos_side = "net"
                            if order_info.is_futures and order_info.side == "buy":
                                if order_info.is_entry:
                                    pos_side = "long"
                                elif order_info.is_close:
                                    pos_side = "short"
                            elif order_info.is_futures and order_info.side == "sell":
                                if order_info.is_entry:
                                    pos_side = "short"
                                elif order_info.is_close:
                                    pos_side = "long"

                            if (
                                order_info.margin_mode is None
                                or order_info.margin_mode == "isolated"
                            ):
                                params |= {"posSide": pos_side, "tdMode": "isolated"}
                            elif order_info.margin_mode == "cross":
                                params |= {"posSide": pos_side, "tdMode": "cross"}
                        elif instance.position_mode == "hedge":
                            instance.position_mode = "one-way"
                            if order_info.is_entry:
                                params |= {}
                            elif order_info.is_close:
                                params |= {"reduceOnly": True}

                        if order_info.is_entry:
                            if order_info.leverage is None:
                                instance.set_leverage(1, order_info.unified_symbol)
                            else:
                                instance.set_leverage(
                                    order_info.leverage, order_info.unified_symbol
                                )
                            if order_info.margin_mode is None:
                                params |= {"tdMode": "isolated"}
                            else:
                                params |= {"tdMode": order_info.margin_mode}

                        args = tuple(
                            params if i == 5 else arg for i, arg in enumerate(args)
                        )
                    else:
                        attempts = max_attempts
                elif order_info.exchange in ("BITGET"):
                    if "unilateral position" in str(e):
                        if instance.position_mode == "hedge":
                            instance.position_mode = "one-way"
                            new_side = order_info.side + "_single"
                            new_params = {"side": new_side}
                            args = tuple(
                                new_side if i == 2 else arg
                                for i, arg in enumerate(args)
                            )
                            args = tuple(
                                new_params if i == 5 else arg
                                for i, arg in enumerate(args)
                            )
                        elif instance.position_mode == "one-way":
                            instance.position_mode = "hedge"
                            if order_info.is_entry:
                                new_params = {}
                            elif order_info.is_close:
                                new_params = {"reduceOnly": True}
                            args = tuple(
                                new_params if i == 5 else arg
                                for i, arg in enumerate(args)
                            )

                    elif "two-way positions" in str(e):
                        if instance.position_mode == "hedge":
                            instance.position_mode = "one-way"
                            new_side = order_info.side + "_single"
                            new_params = {"reduceOnly": True, "side": new_side}
                            args = tuple(
                                new_side if i == 2 else arg
                                for i, arg in enumerate(args)
                            )
                            args = tuple(
                                new_params if i == 5 else arg
                                for i, arg in enumerate(args)
                            )
                        elif instance.position_mode == "one-way":
                            instance.position_mode = "hedge"
                            if order_info.is_entry:
                                new_params = {}
                            elif order_info.is_close:
                                new_params = {"reduceOnly": True}
                            args = tuple(
                                new_params if i == 5 else arg
                                for i, arg in enumerate(args)
                            )
                    else:
                        attempts = max_attempts
                else:
                    attempts = max_attempts

            if attempts == max_attempts:
                raise
            else:
                logger.error(f"재시도 {max_attempts - attempts}번 남았음")
