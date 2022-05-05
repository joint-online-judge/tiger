import asyncio
from typing import Any, Awaitable, Dict, cast

from joj.horse_client.api import AuthApi, JudgeApi
from joj.horse_client.api_client import ApiClient, Configuration
from joj.horse_client.models import (
    AuthTokens,
    AuthTokensResp,
    ErrorCode,
    JudgeClaim,
    JudgeCredentials,
    JudgeCredentialsResp,
)
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from joj.tiger import errors
from joj.tiger.config import settings


class HorseClient:
    def __init__(self, base_url: str):
        configuration = Configuration()
        configuration.host = f"{base_url}/api/v1"
        self.client = ApiClient(configuration)

    def __del__(self) -> None:
        loop = asyncio.get_event_loop()
        task = self.client.rest_client.pool_manager.close()
        if loop.is_running():
            loop.create_task(task)
        else:
            loop.run_until_complete(task)

    @staticmethod
    async def _retry(func: Awaitable[Any]) -> Any:
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(2))
        async def wrapper() -> Any:
            return await func

    async def login(self) -> None:
        auth_api = AuthApi(self.client)
        request = auth_api.v1_login(
            grant_type="password",
            username=settings.horse_username,
            password=settings.horse_password,
            scope="",
            client_id="",
            client_secret="",
            response_type="json",
        )
        try:
            response: AuthTokensResp = await self._retry(request)
        except RetryError:
            # horse is down or network error of the worker
            raise errors.WorkerRejectError()

        if response.error_code != ErrorCode.SUCCESS:
            # username / password error
            raise errors.WorkerRejectError()

        auth_tokens = cast(AuthTokens, response.data)

        def configuration_auth_settings(_: Any) -> Dict[str, Dict[str, str]]:
            return {
                "HTTPBearer": {
                    "in": "header",
                    "key": "Authorization",
                    "value": f"Bearer {auth_tokens.access_token}",
                }
            }

        self.client.configuration.auth_settings = configuration_auth_settings

    async def claim_record(
        self, domain_id: str, record_id: str, task_id: str
    ) -> JudgeCredentials:
        judge_api = JudgeApi(self.client)
        judge_claim = JudgeClaim(task_id=task_id)
        request = judge_api.v1_claim_record_by_judge(
            body=judge_claim,
            domain=domain_id,
            record=record_id,
        )

        try:
            response: JudgeCredentialsResp = await self._retry(request)
        except RetryError:
            # horse is down or network error of the worker
            raise errors.WorkerRejectError()

        if response.error_code != ErrorCode.SUCCESS:
            raise errors.FatalError()

        judge_credentials = cast(JudgeCredentials, response.data)
        return judge_credentials


# @lru_cache()
# def get_horse_client(base_url: str) -> HorseClient:
#     return HorseClient(base_url)
