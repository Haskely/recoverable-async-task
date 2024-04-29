import asyncio

from recoverable_async_task import RecoverableAsyncTask


async def main():
    async def task(id: int | str):
        import random

        await asyncio.sleep(0.1)

        if random.randint(1, 2) == 1:
            raise Exception(f"Task {id=} failed!")

        return {"id": id, "data": f"Task {id=} finished!"}

    # 创建 RecoverableAsyncTask 实例
    re_async_task = RecoverableAsyncTask(
        task,
        max_workers=10,
        max_qps=10,
        retry_n=3,
        checkpoint_path_name="save-dir/my-example-task",
    )

    # 推送任务以并发处理
    for i in range(100):
        re_async_task.push(i)

    # 收集并打印结果
    async for result in re_async_task.collect_results():
        print(result)


asyncio.run(main())
