

def run_with_sub_process(func, name):
    def __wrapper(*args, **kwargs):
        from core.settings import ENABLE_THREAD
        thread = None
        if ENABLE_THREAD:
            import threading
            thread = threading.Thread(target=func,name=name, args=args, kwargs=kwargs)
        else:
            from multiprocessing import Process
            thread = Process(target=func,name=name, args=args, kwargs=kwargs)

        if thread:
            thread.join()
    return __wrapper