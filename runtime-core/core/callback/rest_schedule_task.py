
from core.tools.annotations import shutdown_before

@shutdown_before
def rest_schedule_task_status():
    from api.rest.services.scheduled_task import update_schdule_task
    update_schdule_task()