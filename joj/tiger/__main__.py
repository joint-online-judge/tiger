import platform
import subprocess
import sys

from pydantic_universal_settings import cli
from watchgod import watch

from joj.tiger.config import settings


@cli.command()
def main() -> None:
    from joj.tiger.app import main

    if platform.system() == "Windows" and settings.workers != 1:
        print("Now only solo mode is supported on Windows, so workers must be set to 1")
        exit(-1)

    if not settings.debug or settings.workers != 1:
        main()
    else:
        p = subprocess.Popen([sys.executable, "-m", "joj.tiger.app"])
        for changes in watch("joj/tiger"):
            print("changes", changes)
            p.terminate()
            p.poll()
            p = subprocess.Popen([sys.executable, "-m", "joj.tiger.app"])


if __name__ == "__main__":
    main()
