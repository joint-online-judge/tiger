from functools import lru_cache

from joj.horse_client.api_client import ApiClient, Configuration

from joj.tiger.config import settings


@lru_cache()
def get_horse_client() -> ApiClient:
    configuration = Configuration()
    configuration.host = f"http://{settings.horse_host}:{settings.horse_port}/api/v1"
    client = ApiClient(configuration)
    return client
