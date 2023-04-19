from fastapi.exception_handlers import (
    request_validation_exception_handler,
)
from pprint import pprint
from fastapi import FastAPI, Request, status, BackgroundTasks
from fastapi.responses import ORJSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
import httpx
from exchange.stock.kis import KoreaInvestment
from model import MarketOrder, PriceRequest, HedgeData
from utility import settings, log_order_message, log_alert_message, print_alert_message, logger_test, log_order_error_message, log_validation_error_message, log_hedge_message, log_error_message, log_message
import traceback
from exchange import get_exchange, log_message, db, settings, get_bot, pocket

VERSION = "0.0.9"
app = FastAPI(default_response_class=ORJSONResponse)

@app.on_event("startup")
async def startup():
    log_message(f"POABOT 실행 완료! - 버전:{VERSION}")


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
async def whitelist_middleware(request: Request, call_next):
    try:
        if request.client.host not in whitelist:
            msg = f"{request.client.host}는 안됩니다"
            print(msg)
            return ORJSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=f"{request.client.host}는 허용되지 않습니다")
        # elif request.url.path == "/order" and request.method == "POST":
        #     request_json  = await request.json()
        #     if "hedge" in request_json:
        #         async with httpx.AsyncClient() as client:
        #             port = app.state.port
        #             await client.post(f"http://127.0.0.1:{port}/hedge", json=(await request.json()))
        #             return ORJSONResponse(status_code=status.HTTP_200_OK, content="OK")
    except:
        log_error_message(traceback.format_exc(), "미들웨어 에러")
    else:
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
    data = httpx.get("https://ipv4.jsonip.com").json()["ip"]
    log_message(data)


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

def get_hedge_records(base):
    records = pocket.get_full_list("kimp", query_params={"filter": f'base = "{base}"'})
    binance_amount = 0.0
    binance_records_id = []
    upbit_amount = 0.0
    upbit_records_id = []
    for record in records:
        if record.exchange == "BINANCE":
            binance_amount += record.amount
            binance_records_id.append(record.id)
        elif record.exchange == "UPBIT":
            upbit_amount += record.amount
            upbit_records_id.append(record.id)
    
    return {"BINANCE": {"amount": binance_amount, "records_id": binance_records_id}, "UPBIT": {"amount": upbit_amount, "records_id": upbit_records_id}}
    


@ app.post("/hedge")
async def hedge(hedge_data: HedgeData, background_tasks: BackgroundTasks):
    exchange_name = hedge_data.exchange.upper()
    bot = get_bot(exchange_name)
    upbit = get_bot("UPBIT")
    
    base = hedge_data.base
    quote = hedge_data.quote
    amount = hedge_data.amount
    leverage = hedge_data.leverage
    hedge = hedge_data.hedge

    if hedge == "ON":
        try:
            if amount is None:
                raise Exception("헷지할 수량을 요청하세요")
            binance_order_result = bot.market_short_entry(base, quote, amount, None, None, leverage=leverage)
            binance_order_amount = binance_order_result["amount"]
            pocket.create("kimp", {"exchange": "BINANCE", "base": base, "quote": quote, "amount": binance_order_amount})
            if leverage is None:
                leverage = 1
            try:
                upbit_order_result = upbit.market_buy(base, "KRW", "market", "buy", binance_order_amount)
            except Exception as e:
                hedge_records = get_hedge_records(base)
                binance_records_id = hedge_records["BINANCE"]["records_id"]
                binance_amount = hedge_records["BINANCE"]["amount"]
                binance_order_result = bot.market_short_close(base, quote, binance_amount, None, None)
                for binance_record_id in binance_records_id:
                    pocket.delete("kimp", binance_record_id)
                log_message("[헷지 실패] 업비트에서 에러가 발생하여 바이낸스 포지션을 종료합니다", str(e))
            else:
                upbit_order_info = upbit.fetch_order(upbit_order_result["id"])
                upbit_order_amount = upbit_order_info["filled"]
                pocket.create("kimp", {"exchange": "UPBIT", "base": base, "quote": "KRW", "amount": upbit_order_amount})
                log_hedge_message(exchange_name, base, quote, binance_order_amount, upbit_order_amount, hedge)

        except Exception as e:
            # log_message(f"{e}")
            background_tasks.add_task(log_error_message, traceback.format_exc(), "헷지 에러")
            return {"result":"error"}
        else:
            return {"result":"success"}

    elif hedge == "OFF":
        try:
            records = pocket.get_full_list("kimp", query_params={"filter": f'base = "{base}"'})
            binance_amount = 0.0
            binance_records_id = []
            upbit_amount = 0.0
            upbit_records_id = []
            for record in records:
                if record.exchange == "BINANCE":
                    binance_amount += record.amount
                    binance_records_id.append(record.id)
                elif record.exchange == "UPBIT":
                    upbit_amount += record.amount
                    upbit_records_id.append(record.id)
            
            if binance_amount > 0 and upbit_amount > 0:
                # 바이낸스
                binance_order_result = bot.market_short_close(base, quote, binance_amount, None, None)
                for binance_record_id in binance_records_id:
                    pocket.delete("kimp", binance_record_id)
                # 업비트
                upbit_order_result = upbit.market_sell(base, "KRW", "market", "sell", upbit_amount)
                for upbit_record_id in upbit_records_id:
                    pocket.delete("kimp", upbit_record_id)
                
                log_hedge_message(exchange_name, base, quote, binance_amount, upbit_amount, hedge)
            elif binance_amount == 0 and upbit_amount == 0:
                log_message(f"{exchange_name}, UPBIT에 종료할 수량이 없습니다")
            elif binance_amount == 0:
                log_message(f"{exchange_name}에 종료할 수량이 없습니다")
            elif upbit_amount == 0:
                log_message("UPBIT에 종료할 수량이 없습니다")
        except Exception as e:
            background_tasks.add_task(log_error_message, traceback.format_exc(), "헷지종료 에러")
            return {"result":"error"}
        else:
            return {"result":"success"}