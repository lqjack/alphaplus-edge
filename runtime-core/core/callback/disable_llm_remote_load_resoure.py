from core.tools.annotations import startup_before
import os
import logging
logger = logging.getLogger(__name__) 

@startup_before(priority=-1)
def init_llm_disable_remote_load_resource():
    os.environ['LITELLM_DISABLE_REMOTE_REQUESTS'] = 'True'
    os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
    logger.info(f'disabled litellm remote request.')