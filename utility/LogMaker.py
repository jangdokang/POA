import sys
from model import MarketOrder
from utility import settings
from datetime import datetime, timedelta
from dhooks import Webhook, Embed
from pprint import pprint
from loguru import logger
logger.remove(0)
logger.add("./log/poa.log", rotation="1 days", retention="7 days", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
logger.add(sys.stderr, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>")

try:
    url = settings.DISCORD_WEBHOOK_URL.replace("discordapp", "discord")
    hook = Webhook(url)
except Exception as e:
    print("웹훅 URL이 유효하지 않습니다: ", settings.DISCORD_WEBHOOK_URL)


def parse_time(utc_timestamp):
    timestamp = utc_timestamp + timedelta(hours=9).seconds
    date = datetime.fromtimestamp(timestamp)
    return date.strftime('%y-%m-%d %H:%M:%S')


def logger_test():
    date = parse_time(datetime.utcnow().timestamp())
    logger.info(date)


def log_message(message="None", embed: Embed = None):
    if hook:
        if embed:
            hook.send(embed=embed)
        else:
            hook.send(message)
        # hook.send(str(message), embed)
    else:
        logger.info(message)
        print(message)


def log_order_message(exchange_name, order_result: dict, order_info: MarketOrder):
    date = parse_time(datetime.utcnow().timestamp())
    if order_info.side.upper() == "BUY" and exchange_name in ("UPBIT", "BITGET", "BYBIT"):
        f_name = "비용"
        if order_info.amount is not None:
            if exchange_name == "UPBIT":
                amount = str(order_result.get('cost'))
            elif exchange_name == "BITGET":
                amount = str(order_info.amount*order_info.price)
            elif exchange_name == "BYBIT":
                amount = str(order_result.get("info").get("origQty"))
        elif order_info.percent is not None:
            f_name = "비율"
            amount = f"{order_info.percent}%"

    else:
        f_name = "수량"
        if exchange_name in ("BITGET", "KRX", "NASDAQ", "AMEX", "NYSE"):
            if order_info.amount is not None:
                amount = str(order_info.amount)
            elif order_info.percent is not None:
                f_name = "비율"
                amount = f"{order_info.percent}%"
        else:
            amount = str(order_result.get('amount'))
    side = ""
    symbol = order_info.base + '/' + order_info.quote
    if order_info.side == "buy":
        side = "매수"
    elif order_info.side == "sell":
        side = "매도"
    elif order_info.side == "entry/buy":
        side = "롱 진입"
    elif order_info.side == "entry/sell":
        side = "숏 진입"
    elif order_info.side == "close/buy":
        side = "숏 종료"
    elif order_info.side == "close/sell":
        side = "롱 종료"

    if exchange_name in ("KRX", "NASDAQ", "NYSE", "AMEX"):
        content = f"일시\n{date}\n\n거래소\n{exchange_name}\n\n티커\n{order_info.base}\n\n거래유형\n{side}\n\n{amount}"
        embed = Embed(title=order_info.order_name, description=f"체결 {exchange_name} {order_info.base} {side} {amount}", color=0x0000FF)
        embed.add_field(name="일시", value=str(date), inline=False)
        embed.add_field(name="거래소", value=exchange_name, inline=False)
        embed.add_field(name="티커", value=order_info.base, inline=False)
        embed.add_field(name="거래유형", value=side, inline=False)
        embed.add_field(name="수량", value=amount, inline=False)
        embed.add_field(name="계좌", value=f"{order_info.kis_number}번째 계좌", inline=False)
        log_message(content, embed)
    else:
        content = f"일시\n{date}\n\n거래소\n{exchange_name}\n\n심볼\n{symbol}\n\n거래유형\n{order_result.get('side')}\n\n{amount}"
        embed = Embed(title=order_info.order_name, description=f"체결: {exchange_name} {symbol} {side} {amount}", color=0x0000FF)

        embed.add_field(name='일시', value=str(date), inline=False)
        embed.add_field(name='거래소', value=exchange_name, inline=False)
        embed.add_field(name='심볼', value=symbol, inline=False)
        embed.add_field(name='거래유형', value=side, inline=False)
        embed.add_field(name=f_name, value=amount, inline=False)
        log_message(content, embed)


def log_order_error_message(error, order_info: MarketOrder):
    embed = Embed(
        title=order_info.order_name,
        description=f"[주문 오류가 발생했습니다]\n{error}",
        color=0xFF0000,
    )
    logger.error(f"[주문 오류가 발생했습니다]\n{error}")

    log_message(embed=embed)


def log_validation_error_message(msg):
    logger.error(f"검증 오류가 발생했습니다\n{msg}")
    log_message(msg)


def print_alert_message(order_info: MarketOrder):
    msg = str(order_info.dict(exclude_none=True)).replace(" ", "").replace("{", "").replace("}", "").replace(",", "\n")
    logger.info(f"주문 성공 웹훅메세지\n{msg}")


def log_alert_message(order_info: MarketOrder):
    embed = Embed(
        title=order_info.order_name,
        description="[웹훅 alert_message]",
        color=0xFF0000,
    )
    order_info_dict = order_info.dict(exclude_none=True)
    for key, value in order_info_dict.items():
        embed.add_field(name=key, value=str(value), inline=False)
    msg = str(order_info_dict).replace(" ", "").replace("{", "").replace("}", "").replace(",", "\n")
    logger.info("주문 실패 웹훅메세지\n"+msg)
    log_message(embed=embed)
