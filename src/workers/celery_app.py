from celery import Celery
from kombu import Queue
import os

celery_app = Celery(
    'vijayshreepathak_scraper',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    include=['workers.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_default_queue='default',
    task_queues=(
        Queue('high_priority', routing_key='high'),
        Queue('normal_priority', routing_key='normal'),
        Queue('low_priority', routing_key='low'),
    ),
    task_default_exchange='tasks',
    task_default_exchange_type='direct',
    task_default_routing_key='normal',
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_annotations={
        'workers.tasks.scrape_single_page': {
            'rate_limit': '10/s',
            'time_limit': 300,
            'soft_time_limit': 240,
        },
        'workers.tasks.validate_links': {
            'rate_limit': '5/s',
            'time_limit': 60,
        }
    }
)

if __name__ == '__main__':
    celery_app.start() 