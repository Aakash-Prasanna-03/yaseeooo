import sys

from app.integrations import gemini_langchain_patch

gemini_langchain_patch.apply()

from celery import Celery
from app.config import get_settings

s = get_settings()
celery_app = Celery(
    "yeseeeooo",
    broker=s.redis_url,
    backend=s.redis_url,
)
celery_app.conf.task_default_queue = "content"
# prefork/billiard multiprocessing is unreliable on Windows; use a single-process pool locally.
if sys.platform == "win32":
    celery_app.conf.worker_pool = "solo"
celery_app.conf.broker_connection_retry_on_startup = True

# Register tasks
from app import tasks as _tasks  # noqa: E402,F401
