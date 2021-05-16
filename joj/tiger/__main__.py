import sys

import jwt

from joj.tiger import celery_app

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("invalid argv length")
        exit(1)
    access_jwt = sys.argv[1]
    jwt_dict = jwt.decode(access_jwt, verify=False)
    assert jwt_dict["name"]
    celery_app.worker_main(argv=["worker", "-n", jwt_dict["name"], "-j", access_jwt])
