from functools import lru_cache
from typing import Any, Dict, List

import docker
from benedict import benedict
from loguru import logger
from pydantic import BaseModel, root_validator


class Image(BaseModel):
    name: str
    image: str

    def pull(self) -> None:
        logger.info("docker pull {}", self.image)
        client = docker.from_env()
        client.images.pull(self.image)


class Queue(BaseModel):
    name: str
    images: List[str]
    build: bool = False


class ToolchainsConfig(BaseModel):
    images: Dict[str, Image]
    queues: Dict[str, Queue]
    queues_type: str

    @root_validator(pre=True)
    def validate_all(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        from joj.tiger.config import settings

        images = values.get("images", {})
        queues = values.get("queues", {})

        for name, image in images.items():
            images[name]["name"] = name

        new_queues = {}
        for name in settings.queues.split(","):
            if name not in queues:
                raise ValueError(f"queue {name} not defined in queues!")
            queue = queues.get(name)
            queue["name"] = name
            for image in queue["images"]:
                if image not in images:
                    raise ValueError(f"image {image} not defined in images!")
            new_queues[name] = queue

        values["queues"] = new_queues
        values["queues_type"] = settings.queues_type
        return values

    def pull_images(self) -> None:
        unique_images = set()
        for queue in self.queues.values():
            for image in queue.images:
                unique_images.add(image)
        for image in unique_images:
            self.images[image].pull()

    def generate_queues(self) -> List[str]:
        result = []
        for name in self.queues.keys():
            result.append(f"joj.tiger.{self.queues_type}.{name}")
        return result


@lru_cache()
def get_toolchains_config() -> ToolchainsConfig:
    from joj.tiger.config import settings

    data = benedict(settings.toolchains_config)
    config = ToolchainsConfig(**data.dict())

    return config
