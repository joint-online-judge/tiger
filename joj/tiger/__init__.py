from celery import Celery
import time

celery_app = Celery('tasks', broker='pyamqp://localhost//')

celery_app.conf.update({
    'result_backend': 'rpc://',
    'result_persistent': False,
    'task_routes': ([
        ('joj.tiger.*', {'queue': 'tiger'}),
        ('joj.horse.*', {'queue': 'horse'}),
    ], )
})


@celery_app.task(name='joj.tiger.compile')
def compile_task(msg):
    print('waiting 5 secs')
    time.sleep(5)
    print(msg)
    return 'success'


if __name__ == '__main__':
    celery_app.worker_main()
