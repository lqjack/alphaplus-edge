import time
MAX_RETRIES = 5
RETRY_DELAY = 1 
def commit_with_retry(session):
    from sqlalchemy.exc import OperationalError
    retries = 0
    while retries < MAX_RETRIES:
        try:
            session.commit()
            return
        except OperationalError as e:
            if 'database is locked' in str(e):
                retries += 1
                time.sleep(RETRY_DELAY)
            else:
                raise
    raise RuntimeError("Failed to commit after multiple retries")
