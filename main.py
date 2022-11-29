# version 0.0.4
from fastapi.exception_handlers import (
    request_validation_exception_handler,
)

from fastapi import FastAPI, Request, status, BackgroundTasks
from fastapi.responses import ORJSONResponse
from fastapi.exceptions import RequestValidationError
import httpx
from exchange.stock.kis import KoreaInvestment
from model import MarketOrder, PriceRequest
from utility import settings, log_order_message, log_alert_message, print_alert_message, logger_test, log_order_error_message, log_validation_error_message
import traceback
from exchange import get_exchange, log_message, db, settings


app = FastAPI(default_response_class=ORJSONResponse)


@app.on_event("startup")
async def startup():
    pass


@app.on_event("shutdown")
async def shutdown():
    db.close()

whitelist = ["52.89.214.238", "34.212.75.30",
             "54.218.53.128", "52.32.178.7", "127.0.0.1"]
whitelist = whitelist + settings.WHITELIST


# @app.middleware("http")
# async def add_process_time_header(request: Request, call_next):
#     start_time = time.perf_counter()
#     response = await call_next(request)
#     process_time = time.perf_counter() - start_time
#     response.headers["X-Process-Time"] = str(process_time)
#     return response


@app.middleware('http')
async def settings_whitelist_middleware(request: Request, call_next):
    if request.client.host not in whitelist:
        msg = f"{request.client.host}는 안됩니다"
        print(msg)
        return ORJSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=f"{request.client.host} Not Allowed")
    response = await call_next(request)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    msgs = [f"[에러{index+1}] " + f"{error.get('msg')} \n{error.get('loc')}"
            for index, error in enumerate(exc.errors())]
    message = "[Error]\n"
    for msg in msgs:
        message = message+msg+"\n"

    log_validation_error_message(f"{message}\n {exc.body}")
    return await request_validation_exception_handler(request, exc)


@app.get("/ip")
async def get_ip():
    data = httpx.get("https://ifconfig.me").text
    log_message(data)
    return data


@ app.get("/hi")
async def welcome():
    return "hi!!"


@ app.post("/price")
async def price(price_req: PriceRequest, background_tasks: BackgroundTasks):
    exchange = get_exchange(price_req.exchange)
    price = exchange.dict()[price_req.exchange].fetch_price(price_req.base, price_req.quote)
    return price


def log(exchange_name, result, order_info):
    log_order_message(exchange_name, result, order_info)
    print_alert_message(order_info)


@ app.post("/order")
async def order(order_info: MarketOrder, background_tasks: BackgroundTasks):
    result = None
    try:
        exchange_name = order_info.exchange.upper()
        exchange = get_exchange(exchange_name, order_info.kis_number)
        if exchange_name in ("BINANCE", "UPBIT", "BYBIT", "BITGET"):
            bot = exchange.dict()[order_info.exchange]
            bot.order_info = order_info
            if order_info.side == "buy":
                result = bot.market_buy(order_info.base, order_info.quote, order_info.type, order_info.side, order_info.amount, order_info.price, order_info.percent)
            elif order_info.side == "sell":
                result = bot.market_sell(order_info.base, order_info.quote, order_info.type,
                                         order_info.side, order_info.amount, order_info.price, order_info.percent)
            elif order_info.side.startswith("entry/"):
                if order_info.stop_price and order_info.profit_price:
                    result = bot.market_sltp_order(order_info.base, order_info.quote, order_info.type,
                                                   order_info.side, order_info.amount, order_info.stop_price, order_info.profit_price)
                else:
                    result = bot.market_entry(order_info.base, order_info.quote, order_info.type, order_info.side, order_info.amount, order_info.price, order_info.percent, order_info.leverage)
            elif order_info.side.startswith("close/"):
                result = bot.market_close(order_info.base, order_info.quote, order_info.type, order_info.side, order_info.amount, order_info.price, order_info.percent)
            background_tasks.add_task(log, exchange_name, result, order_info)
        elif exchange_name in ("KRX", "NASDAQ", "NYSE", "AMEX"):
            kis: KoreaInvestment = exchange
            result = kis.create_order(order_info.exchange, order_info.base, order_info.type.lower(), order_info.side.lower(), order_info.amount)
            background_tasks.add_task(log, exchange_name, result, order_info)

    except TypeError:
        background_tasks.add_task(log_order_error_message, traceback.format_exc(), order_info)
    except Exception:
        background_tasks.add_task(log_order_error_message, traceback.format_exc(), order_info)
        log_alert_message(order_info)

    else:
        return {"result": "success"}

    finally:
        pass
