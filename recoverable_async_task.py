"""
This module provides functionality for creating recoverable asynchronous tasks with checkpoint storage.
It allows tasks to be resumed from where they left off in case of interruption.
"""

import asyncio
import functools
import json
import sys
import traceback
from collections.abc import AsyncIterator, Coroutine, Iterator
from pathlib import Path
from typing import (
    Callable,
    Generic,
    TypeVar,
    Union,
)

from loguru import logger
from tqdm import tqdm

if sys.version_info >= (3, 11):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

JSON_ITEM = TypeVar("JSON_ITEM", bound=Union[str, int, float, bool, None])

JSON = Union[JSON_ITEM, dict[str, "JSON"], list["JSON"]]

T = TypeVar("T", bound=JSON)

ID_T = TypeVar("ID_T", bound=int | str)


class TaskRecord(TypedDict, Generic[ID_T, T]):
    id: ID_T
    data: T


def json_default_serializer(o: JSON_ITEM):
    logger.warning(
        f"Object {str(o)} of type {o.__class__.__name__} is not JSON serializable"
    )
    return str(o)


class TaskStorage(Generic[ID_T, T]):
    """
    A storage class that handles saving and loading task results to/from disk.

    Args:
        storage_path_name (str): Base path for the storage file.

    Attributes:
        storage_path_name (str): Original path name provided
        name (str): Shortened name for display purposes
        storage_path (Path): Path to the actual storage file
        records (dict): Dictionary containing loaded records
    """

    @staticmethod
    def load(storage_path: str | Path) -> Iterator[TaskRecord[ID_T, T]]:
        """
        Load task records from a storage file.

        Args:
            storage_path: Path to the storage file

        Yields:
            TaskRecord: Records containing task IDs and their results
        """
        logger.debug(f"load checkpoint from {storage_path}")
        with Path(storage_path).open() as f:
            for ln, line in enumerate(f):
                line = line.strip()
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f'Failed to load checkpoint:\n  File "{storage_path}", line {ln+1}\n    {line=}\n{e}'
                    )

    def __init__(self, storage_path_name: str) -> None:
        self.storage_path_name = storage_path_name
        self.name = storage_path_name
        if len(self.name) > 80:
            self.name = "..." + self.name[-80:]
        self.storage_path = Path(storage_path_name).with_name(
            Path(storage_path_name).stem + "-storage.jsonl"
        )
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self.storage_path.touch(exist_ok=True)
        self.records: dict[ID_T, T] = {
            record["id"]: record["data"] for record in self.load(self.storage_path)
        }

    def add(self, data: T, id: ID_T):
        """
        Add a new record to storage.

        Args:
            data: Task result data to store
            id: Unique identifier for the task
        """
        self.records[id] = data
        with self.storage_path.open("a") as f:
            json.dump(
                TaskRecord(id=id, data=data),
                f,
                ensure_ascii=False,
                default=json_default_serializer,
            )
            f.write("\n")

    def export(self, save_path: str | Path | None = None):
        """
        Export all stored records to a JSON file.

        Args:
            save_path: Optional custom path for the export file

        Returns:
            Path: Path where the results were saved
        """
        save_path = save_path or Path(self.storage_path_name).with_name(
            Path(self.storage_path_name).stem + f"-results-{len(self.records)}.json"
        )
        logger.debug(f"save checkpoint to {save_path}")
        with Path(save_path).open("w") as f:
            json.dump(
                list(self.records.values()),
                f,
                ensure_ascii=False,
                indent=4,
                default=json_default_serializer,
            )

        return save_path


TaskFunction = Callable[[ID_T], Coroutine[None, None, T]]


class RecoverableTask(Generic[ID_T, T]):
    """
    A wrapper class that makes async tasks recoverable by storing their results.

    Args:
        task_function: The async function to make recoverable
        storage: TaskStorage instance for storing results
        raise_on_error: Whether to raise exceptions or log them
        show_progress: Whether to show progress bar
        force_rerun: Whether to rerun tasks even if results exist
    """

    def __init__(
        self,
        task_function: TaskFunction[ID_T, T],
        storage: TaskStorage[ID_T, T],
        raise_on_error: bool = True,
        show_progress: bool = True,
        force_rerun: bool = False,
    ):
        self.task_function = task_function
        self.storage = storage
        self.raise_on_error = raise_on_error
        self.show_progress = show_progress
        self.force_rerun = force_rerun
        functools.update_wrapper(self, task_function)

    async def __call__(self, id: ID_T) -> T:
        """
        Execute the task for a single ID.

        Args:
            id: Task identifier

        Returns:
            The task result
        """
        if not self.force_rerun and id in self.storage.records:
            return self.storage.records[id]

        result = await self.task_function(id)
        self.storage.add(result, id=id)
        return result

    async def as_completed(self, id_list: list[ID_T]) -> AsyncIterator[T]:
        """
        Execute multiple tasks and yield results as they complete.

        Args:
            id_list: List of task identifiers to process

        Yields:
            Task results as they complete

        Raises:
            Exception: If raise_on_error is True and a task fails
        """
        tasks: list[asyncio.Task[T]] = []

        if not self.force_rerun:
            for id in id_list:
                if id in self.storage.records:
                    yield self.storage.records[id]

        for id in id_list:
            if self.force_rerun or id not in self.storage.records:
                tasks.append(asyncio.create_task(self(id)))

        if not tasks:
            return

        with tqdm(
            asyncio.as_completed(tasks),
            total=len(id_list),
            desc=f"Processing {self.storage.name}",
            disable=not self.show_progress,
            initial=len(id_list) - len(tasks),
        ) as pbar:
            for completed_task in pbar:
                try:
                    result = await completed_task
                    yield result
                except Exception as e:
                    if self.raise_on_error:
                        raise e
                    else:
                        logger.error(f"Task failed: {e}")
                        logger.error(traceback.format_exc())


def make_recoverable(
    storage_path_name: str | None = None,
    raise_on_error: bool = True,
    show_progress: bool = True,
    force_rerun: bool = False,
) -> Callable[[TaskFunction[ID_T, T]], RecoverableTask[ID_T, T]]:
    """
    Decorator factory that creates recoverable versions of async tasks.

    Args:
        storage_path_name: Base path for storing results
        raise_on_error: Whether to raise exceptions from tasks
        show_progress: Whether to show progress bar
        force_rerun: Whether to rerun tasks even if results exist

    Returns:
        A decorator that wraps async functions into RecoverableTask instances

    Example:
        @make_recoverable(storage_path_name="tasks/mytask")
        async def my_task(id: int) -> dict:
            result = await process(id)
            return result
    """

    def decorator(task_function: TaskFunction[ID_T, T]) -> RecoverableTask[ID_T, T]:
        storage = TaskStorage[ID_T, T](storage_path_name or task_function.__name__)
        wrapper = RecoverableTask(
            task_function, storage, raise_on_error, show_progress, force_rerun
        )
        return wrapper

    return decorator


if __name__ == "__main__":
    import random

    async def main():
        @make_recoverable(
            storage_path_name=".test/test",
            raise_on_error=False,
            show_progress=True,
            force_rerun=False,
        )
        async def task(id: int) -> dict[str, int | float]:
            await asyncio.sleep(random.random() * 10)
            return {"id": id, "data": id / (id % 3)}

        # 创建一测试用的 id 列表
        test_ids = list(range(1, 20))

        async for result in task.as_completed(test_ids):
            print(result)

        print(f"Finished {len(task.storage.records)} tasks.")

    asyncio.run(main())
