from core.tools.annotations import shutdown_before
from core.tools.article_content_check import run_with_app
import logging

logger = logging.getLogger(__name__)  

@shutdown_before(priority=100)
@run_with_app
def update_schedule_tasks_completed():
    from api.rest.services.scheduled_task import update_schdule_task
    update_schdule_task()
    logger.info(f'updated scheduled task to failed.')