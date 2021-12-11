from typing import Type, Union

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

    horse_host: str = "localhost"
    horse_port: int = 34765
    horse_username: str
    horse_password: str

    # redis config
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db_index: int = 0


GeneratedSettings: Type[Union[BaseConfig]] = generate_all_settings(
    mixins=[EnvFileMixin, CLIWatchMixin]
)


class AllSettings(GeneratedSettings):  # type: ignore
    pass


settings: AllSettings = get_settings_proxy()
