from functools import lru_cache

from joj.horse_client.api_client import ApiClient, Configuration


@lru_cache()
def get_horse_client(base_url: str) -> ApiClient:
    configuration = Configuration()
    configuration.host = f"{base_url}/api/v1"
    client = ApiClient(configuration)
    return client
