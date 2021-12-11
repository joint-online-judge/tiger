from typing import cast

from joj.horse_client.api.auth_api import AuthApi
from joj.horse_client.models.auth_tokens import AuthTokens
from joj.horse_client.models.auth_tokens_resp import AuthTokensResp
from joj.horse_client.models.error_code import ErrorCode
from tenacity import retry, stop_after_attempt

from joj.tiger.client import get_horse_client
from joj.tiger.config import settings
from joj.tiger.errors import TigerError


@retry(stop=stop_after_attempt(3))
async def get_access_token() -> str:
    auth_api = AuthApi(get_horse_client())
    response: AuthTokensResp = await auth_api.v1_login(
        grant_type="password",
        username=settings.horse_username,
        password=settings.horse_password,
        scope="",
        client_id="",
        client_secret="",
        response_type="json",
    )
    if response.error_code != ErrorCode.SUCCESS:
        raise TigerError()
    auth_tokens = cast(AuthTokens, response.data)
    return auth_tokens.access_token
