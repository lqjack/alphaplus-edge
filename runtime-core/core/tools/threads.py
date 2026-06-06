from concurrent.futures import ThreadPoolExecutor
import asyncio
_async_executor = ThreadPoolExecutor(max_workers=4)

def thread_safe_async(async_func, *args, **kwargs):
    """
    线程安全的异步调用方案
    :param async_func: 需要调用的协程函数或协程对象
    :return: 同步执行结果
    """
    loop = asyncio.new_event_loop()
    try:
        # 检查是协程函数还是协程对象
        if asyncio.iscoroutine(async_func):
            # 如果是协程对象，直接运行
            coro = async_func
        else:
            # 如果是协程函数，调用它获取协程对象
            coro = async_func(*args, **kwargs)
            
        # 在新线程中运行事件循环
        future = _async_executor.submit(
            lambda: loop.run_until_complete(coro)
        )
        return future.result()
    finally:
        loop.close()