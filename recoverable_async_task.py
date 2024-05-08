import asyncio
import functools
import json
import traceback
from pathlib import Path
from typing import (
    AsyncIterator,
    Callable,
    Coroutine,
    Generic,
    Iterator,
    TypedDict,
    TypeVar,
    Union,
)

from loguru import logger
from tqdm import tqdm

JSON_ITEM = TypeVar("JSON_ITEM", bound=Union[str, int, float, bool, None])

JSON = Union[JSON_ITEM, dict[str, "JSON"], list["JSON"]]

T = TypeVar("T", bound=JSON)


class TaskException(Exception):
    def __init__(
        self,
        error_num: int,
        task_function: Callable,
        args: tuple,
        kwargs: dict,
        exception: Exception,
    ) -> None:
        self.error_num = error_num
        self.task_function = task_function
        self.args = args
        self.kwargs = kwargs
        self.exception = exception

    def __str__(self) -> str:
        return f"{self.task_function.__name__} args: {self.args}, kwargs: {self.kwargs}, error: {self.exception}, error_num: {self.error_num}\n{traceback.format_exception(self.exception)}"


class FakeLock:
    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class AsyncTask(Generic[T]):
    """Used for convenient concurrency execution of async coroutine tasks.
    Submit tasks using `AsyncTask.push`, and then use `async for result in AsyncTask.collect_results(): ...` to obtain the results.

    Example:
        ```python
        async def my_task(data):
            # I/O-bound long-running tasks.
            return result

        async_t = AsyncTask(my_task, max_workers=10, max_qps=3)

        for data in datas:
            async_t.push(data)

        async for result in async_t.collect_results():
            print(result)
        ```
    """

    def __init__(
        self,
        task_function: Callable[..., Coroutine[None, None, T]],
        max_workers: int = 10,
        max_qps: float = 0,
        retry_n: int = 3,
        raise_after_retry: bool = False,
    ) -> None:
        self.task_function = task_function
        self.max_workers = max_workers
        if self.max_workers > 0:
            self.workers_lock = asyncio.Semaphore(self.max_workers)
        else:
            self.workers_lock = FakeLock()  # type: ignore[assignment]
        self.max_qps = max_qps
        self.qps_lock = asyncio.Lock()
        self.running_tasks: list[asyncio.Future[T]] = []
        self.retry_n = retry_n
        self.raise_after_retry = raise_after_retry

        self.done_tasks: asyncio.Queue[asyncio.Future[T]] = asyncio.Queue()

    def __len__(self):
        return len(self.running_tasks)

    def clear(self):
        for fut in self.running_tasks:
            fut.cancel()
        self.running_tasks.clear()

    def push(self, *args, **kwargs):
        async def _task(error_num):
            if self.max_qps > 1e-5:
                async with self.qps_lock:
                    await asyncio.sleep(1 / self.max_qps)
            async with self.workers_lock:
                try:
                    return await self.task_function(*args, **kwargs)
                except Exception as e:
                    error_num += 1
                    if error_num < self.retry_n:
                        _add_task(error_num)

                    logger.error(
                        f"task_function={self.task_function.__name__} - args={args}, kwargs={kwargs} - error: {e}, retry {error_num}/{self.retry_n}"
                    )

                    raise TaskException(
                        error_num, self.task_function, args, kwargs, e
                    ) from e

        def _add_task(error_num=0):
            def _on_done(task):
                self.done_tasks.put_nowait(task)
                self.running_tasks.remove(task)

            task = asyncio.create_task(_task(error_num))
            task.add_done_callback(_on_done)
            self.running_tasks.append(task)

        _add_task()

    async def collect_results(self) -> AsyncIterator[T]:
        while len(self.running_tasks):
            done_task = await self.done_tasks.get()
            try:
                yield done_task.result()
            except TaskException as e:
                if e.error_num >= self.retry_n and self.raise_after_retry:
                    raise e


ID_T = TypeVar("ID_T", bound=int | str)


class CheckpointData(TypedDict, Generic[ID_T, T]):
    id: ID_T
    data: T


def json_default_serializer(o: JSON_ITEM):
    logger.warning(
        f"Object {str(o)} of type {o.__class__.__name__} is not JSON serializable"
    )
    return str(o)


class Checkpoint(Generic[ID_T, T]):
    @staticmethod
    def load(checkpoint_path: str | Path) -> Iterator[CheckpointData[ID_T, T]]:
        logger.debug(f"load checkpoint from {checkpoint_path}")
        with Path(checkpoint_path).open() as f:
            for ln, line in enumerate(f):
                line = line.strip()
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f'Failed to load checkpoint:\n  File "{checkpoint_path}", line {ln+1}\n    {line=}\n{e}'
                    )

    @staticmethod
    def save_datas(save_path: str | Path, datas: JSON):
        logger.debug(f"save checkpoint to {save_path}")
        with (saved := Path(save_path)).open("w") as f:
            json.dump(
                datas, f, ensure_ascii=False, indent=4, default=json_default_serializer
            )

        return saved

    def __init__(self, checkpoint_path_name: str) -> None:
        self.name = checkpoint_path_name
        self.checkpoint_path = Path(checkpoint_path_name).with_name(
            Path(checkpoint_path_name).stem + "-checkpoint.jsonl"
        )
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        self.checkpoint_path.touch(exist_ok=True)
        self.datas: dict[ID_T, T] = {
            ckpt["id"]: ckpt["data"] for ckpt in self.load(self.checkpoint_path)
        }

        self.saved = None

    def add(self, data: T, id: ID_T):
        assert id not in self.datas, f"id {id} already exists"
        self.datas[id] = data
        with self.checkpoint_path.open("a") as f:
            json.dump(
                CheckpointData(id=id, data=data),
                f,
                ensure_ascii=False,
                default=json_default_serializer,
            )
            f.write("\n")

    def save(self, save_path: str | Path | None = None):
        self.saved = Checkpoint.save_datas(
            save_path
            or Path(self.name).with_name(
                Path(self.name).name + f"-results-{len(self.datas)}.json"
            ),
            list(self.datas.values()),
        )

        return self.saved


class RecoverableAsyncTask(AsyncTask, Generic[ID_T, T]):
    """
    RecoverableAsyncTask extends the functionality of the AsyncTask class by adding checkpointing support.

    Parameters:
    - task_function: A coroutine function that takes an int or str as Task ID and returns a result.
    - max_workers: Maximum number of concurrent workers to execute tasks. Default is 10.
    - max_qps: Maximum queries per second limit. Default is 0 (no limit).
    - retry_n: Number of retries for failed tasks. Default is 3.

    Example Usage:

    ```python
    import asyncio

    async def main():
        async def task(id: int | str):
            await asyncio.sleep(3)
            return {
                "id": id,
                "data": id
            }

        # Create a RecoverableAsyncTask instance
        re_async_task = RecoverableAsyncTask(task, max_workers=10, max_qps=10, retry_n=3)

        # Push tasks to be processed concurrently
        for i in range(100):
            re_async_task.push(i)

        # Collect and print results
        async for result in re_async_task.collect_results():
            print(result)

    asyncio.run(main())
    ```

    Attributes:
    - `checkpoint`: An instance of the Checkpoint class for managing checkpointing.

    Methods:
    - `push(id: int | str)`: Push a task with the given ID to be processed if it hasn't been processed before.
    - `collect_results() -> Iterator[T]`: Asynchronously collect and yield results while updating a progress bar.
    """

    def __init__(
        self,
        task_function: Callable[[ID_T], Coroutine[None, None, T]],
        max_workers: int = 10,
        max_qps: float = 0,
        retry_n: int = 3,
        checkpoint_path_name: str | None = None,
    ) -> None:
        """
        Initialize a RecoverableAsyncTask instance.

        Parameters:
        - task_function: A coroutine function that takes an int or str as input and returns a result.
        - max_workers: Maximum number of concurrent workers to execute tasks. Default is 10.
        - max_qps: Maximum queries per second limit. Default is 0 (no limit).
        - retry_n: Number of retries for failed tasks. Default is 3.
        """
        self.checkpoint = Checkpoint[ID_T, T](
            checkpoint_path_name or task_function.__name__
        )

        @functools.wraps(task_function)
        async def _task_with_checkpoint(id: ID_T):
            result = await task_function(id)
            self.checkpoint.add(result, id=id)
            return result

        super().__init__(_task_with_checkpoint, max_workers, max_qps, retry_n)

    def push(self, id: ID_T):
        """
        Push a task with the given ID to be processed if it hasn't been processed before.

        Parameters:
        - id: ID of the task to be processed.
        """
        if id not in self.checkpoint.datas:
            super().push(id)

    async def collect_results(self) -> AsyncIterator[T]:
        """
        Asynchronously collect and yield results while updating a progress bar and save checkpoint intimely.

        Returns:
        - An asynchronous iterator that yields results as they become available.
        """
        try:
            with tqdm(
                total=len(self) + len(self.checkpoint.datas),
                desc=self.checkpoint.name,
                initial=len(self.checkpoint.datas),
            ) as pbar:
                async for result in super().collect_results():
                    pbar.update(1)
                    yield result
        except KeyboardInterrupt as e:
            logger.error(f"KeyboardInterrupt: {e}")
        finally:
            self.save_path = self.checkpoint.save()
            summary = f"{pbar.n} finished, {pbar.total - pbar.n} failed, checkpoint saved to {self.save_path}"
            if pbar.total - pbar.n > 0:
                logger.warning(summary)
            else:
                logger.success(summary)


if __name__ == "__main__":

    async def main():
        async def task(id: int) -> dict[str, int | float]:
            await asyncio.sleep(1)
            return {"id": id, "data": id / (id % 3)}

        re_async_task = RecoverableAsyncTask(
            task,
            max_workers=10,
            max_qps=10,
            retry_n=3,
            checkpoint_path_name=".test_task/test",
        )

        for i in range(17):
            re_async_task.push(i)

        async for result in re_async_task.collect_results():
            print(result)

        print(f"Finished {len(re_async_task.checkpoint.datas)} tasks.")

    asyncio.run(main())
