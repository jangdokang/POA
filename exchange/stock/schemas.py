from enum import Enum
from typing import Literal
from pydantic import BaseModel

korea_stocks = ("KRX")
us_stocks = ("NASDAQ", "NYSE", "AMEX")


class BaseUrls(str, Enum):
    base_url = "https://openapi.koreainvestment.com:9443"
    paper_base_url = "https://openapivts.koreainvestment.com:29443"


class BaseHeaders(BaseModel):
    authorization: str
    appkey: str
    appsecret: str
    custtype: str = "P"
    # tr_id: str = Literal[TransactionId.korea_buy, TransactionId.korea_sell, TransactionId.korea_paper_buy, TransactionId.korea_paper_sell,
    #  TransactionId.korea_paper_cancel, TransactionId.usa_buy, TransactionId.usa_sell, TransactionId.usa_paper_buy, TransactionId.usa_paper_sell]


class Endpoints(str, Enum):
    korea_order_base = "/uapi/domestic-stock/v1"
    korea_order = f"{korea_order_base}/trading/order-cash"
    korea_order_buyable = f"{korea_order_base}/trading/inquire-psbl-order"

    usa_order_base = "/uapi/overseas-stock/v1"
    usa_order = f"{usa_order_base}/trading/order"
    usa_order_buyable = f"{usa_order_base}/trading/inquire-psamount"
    usa_current_price = f"/uapi/overseas-price/v1/quotations/price"

    korea_ticker = "/uapi/domestic-stock/v1/quotations/inquire-price"
    usa_ticker = "/uapi/overseas-price/v1/quotations/price"


class TransactionId(str, Enum):

    korea_buy = "TTTC0802U"
    korea_sell = "TTTC0801U"

    korea_paper_buy = "VTTC0802U"
    korea_paper_sell = "VTTC0801U"
    korea_paper_cancel = "VTTC0803U"

    usa_buy = "JTTT1002U"
    usa_sell = "JTTT1006U"

    usa_paper_buy = "VTTT1002U"
    usa_paper_sell = "VTTT1001U"

    korea_ticker = "FHKST01010100"
    usa_ticker = "HHDFS00000300"


class KoreaTickerQuery(BaseModel):
    FID_COND_MRKT_DIV_CODE: str = "J"
    FID_INPUT_ISCD: str


class UsaTickerQuery(BaseModel):
    AUTH: str = ""
    EXCD: Literal["NYS", "NAS", "AMS"]
    SYMB: str                           # 종목코드


class ExchangeCode(str, Enum):
    NYSE = "NYSE"
    NASDAQ = "NASD"
    AMEX = "AMEX"


class QueryExchangeCode(str, Enum):
    NYSE = "NYS"
    NASDAQ = "NAS"
    AMEX = "AMS"


class KoreaOrderType(str, Enum):
    market = "01"   # 시장가
    limit = "00"    # 지정가


class UsaOrderType(str, Enum):
    limit = "00"    # 지정가


class OrderSide(str, Enum):
    buy = "buy"
    sell = "sell"


class TokenInfo(BaseModel):
    access_token: str
    access_token_token_expired: str


class KoreaTickerHeaders(BaseHeaders):
    tr_id: str = TransactionId.korea_ticker.value


class UsaTickerHeaders(BaseHeaders):
    tr_id: str = TransactionId.usa_ticker.value


class KoreaBuyOrderHeaders(BaseHeaders):
    tr_id: str = TransactionId.korea_buy.value


class KoreaSellOrderHeaders(BaseHeaders):
    tr_id: str = TransactionId.korea_sell.value


class KoreaPaperBuyOrderHeaders(BaseHeaders):
    tr_id: str = TransactionId.korea_paper_buy.value


class KoreaPaperSellOrderHeaders(BaseHeaders):
    tr_id: str = TransactionId.korea_paper_sell.value


class UsaBuyOrderHeaders(BaseHeaders):
    tr_id: str = TransactionId.usa_buy.value


class UsaSellOrderHeaders(BaseHeaders):
    tr_id: str = TransactionId.usa_sell.value


class UsaPaperBuyOrderHeaders(BaseHeaders):
    tr_id: str = TransactionId.usa_paper_buy.value


class UsaPaperSellOrderHeaders(BaseHeaders):
    tr_id: str = TransactionId.usa_paper_sell.value


class AccountInfo(BaseModel):
    CANO: str           # 계좌번호 앞 8자리
    ACNT_PRDT_CD: str   # 계좌번호 뒤 2자리


# class BaseBody(BaseModel):


class OrderBody(AccountInfo):
    PDNO: str           # 종목코드 6자리
    ORD_QTY: str        # 주문수량


class KoreaOrderBody(OrderBody):
    ORD_DVSN: Literal[f"{KoreaOrderType.market}", f"{KoreaOrderType.limit}"]
    ORD_UNPR: str       # 주문가격


class KoreaMarketOrderBody(KoreaOrderBody):
    ORD_DVSN: str = KoreaOrderType.market.value
    ORD_UNPR: str = "0"


class UsaOrderBody(OrderBody):
    ORD_DVSN: str = UsaOrderType.limit.value  # 주문구분
    OVRS_ORD_UNPR: str  # 주문가격
    OVRS_EXCG_CD: Literal[ExchangeCode.NYSE, ExchangeCode.NASDAQ, ExchangeCode.AMEX]   # 거래소코드  NASD : 나스닥, NYSE: 뉴욕, AMEX: 아멕스
    ORD_SVR_DVSN_CD: str = "0"


# class OrderType(str, Enum):
#     limit = "limit"
#     market = "market"


# class OrderBase(BaseModel):
#     ticker: str
#     type: Literal[OrderType.limit, OrderType.market]
#     side: Literal[OrderSide.buy, OrderSide.sell]
#     amount: int
#     price: float
#     exchange_code: Literal[ExchangeCode.NYSE, ExchangeCode.NASDAQ, ExchangeCode.AMEX]
#     mintick: float
