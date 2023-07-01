class TokenExpired(Exception):
    def __init__(self, msg="Token Expired!", *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


# {'rt_cd': '1', 'msg_cd': 'EGW00205', 'msg1': 'credentials_type이 유효하지 않습니다.(Bearer)'}
# {'rt_cd': '7', 'msg_cd': 'APAC0081', 'msg1': '계좌번호 입력 오류입니다'}
# {'rt_cd': '7', 'msg_cd': 'APBK0919', 'msg1': '장운영일자가 주문일과 상이합니다'}
