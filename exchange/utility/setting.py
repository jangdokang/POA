from exchange.model import Settings
from functools import lru_cache


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
