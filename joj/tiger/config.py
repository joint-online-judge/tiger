from os import path
from pathlib import Path
from typing import Type

from pydantic_universal_settings import (
    BaseSettings,
    CLIWatchMixin,
    EnvFileMixin,
    add_settings,
    generate_all_settings,
    get_settings_proxy,
)


@add_settings
class BaseConfig(BaseSettings):
    debug: bool = False
    workers: int = 1
    worker_name: str = ""

    # horse_host: str = "localhost"
    # horse_port: int = 34765
    horse_username: str = ""
    horse_password: str = ""

    # redis config
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db_index: int = 0

    backend_url: str = "rpc://"
    broker_url: str = "amqp://guest:guest@localhost:5672/"

    toolchains_config: str = str(
        (
            Path(path.dirname(__file__)).parent.parent / "toolchains/config.yaml"
        ).absolute()
    )
    queues: str = "default"
    queues_type: str = "official"


GeneratedSettings: Type[BaseConfig] = generate_all_settings(
    mixins=[EnvFileMixin, CLIWatchMixin]
)


class AllSettings(GeneratedSettings):  # type: ignore
    pass


settings: AllSettings = get_settings_proxy()
