import sys

from joj.tiger import celery_app

if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) != 1 else []
    celery_app.worker_main(argv=["worker", *args])
