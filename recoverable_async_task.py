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

    def __init__(self, checkpoint_path_name: str) -> None:
        self.checkpoint_path_name = checkpoint_path_name
        self.name = Path(checkpoint_path_name).stem[-100:]
        self.checkpoint_path = Path(checkpoint_path_name).with_name(
            Path(checkpoint_path_name).stem + "-checkpoint.jsonl"
        )
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        self.checkpoint_path.touch(exist_ok=True)
        self.datas: dict[ID_T, T] = {
            ckpt["id"]: ckpt["data"] for ckpt in self.load(self.checkpoint_path)
        }

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

    def export(self, save_path: str | Path | None = None):
        save_path = save_path or Path(self.checkpoint_path_name).with_name(
            Path(self.checkpoint_path_name).stem + f"-results-{len(self.datas)}.json"
        )
        logger.debug(f"save checkpoint to {save_path}")
        with Path(save_path).open("w") as f:
            json.dump(
                list(self.datas.values()),
                f,
                ensure_ascii=False,
                indent=4,
                default=json_default_serializer,
            )

        return save_path


# 添加新的类型定义
TaskFunction = Callable[[ID_T], Coroutine[None, None, T]]


class TaskWrapper(Generic[ID_T, T]):
    def __init__(
        self,
        task_function: TaskFunction[ID_T, T],
        checkpoint: Checkpoint[ID_T, T],
        raise_on_error: bool = True,
        show_progress: bool = True,
        force_rerun: bool = False,
    ):
        self.task_function = task_function
        self.checkpoint = checkpoint
        self.raise_on_error = raise_on_error
        self.show_progress = show_progress
        self.force_rerun = force_rerun
        functools.update_wrapper(self, task_function)

    async def __call__(self, id: ID_T) -> T:
        result = await self.task_function(id)
        self.checkpoint.add(result, id=id)
        return result

    async def as_completed(self, id_list: list[ID_T]) -> AsyncIterator[T]:
        tasks: list[asyncio.Task[T]] = []
        for id in id_list:
            if self.force_rerun or id not in self.checkpoint.datas:
                tasks.append(asyncio.create_task(self(id)))

        if not tasks:
            return

        with tqdm(
            asyncio.as_completed(tasks),
            total=len(id_list),
            desc=f"Processing {self.checkpoint.name}",
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


def jsonl_checkpoint(
    checkpoint_path_name: str | None = None,
    raise_on_error: bool = True,
    show_progress: bool = True,
    force_rerun: bool = False,
) -> Callable[[TaskFunction[ID_T, T]], TaskWrapper[ID_T, T]]:
    def decorator(task_function: TaskFunction[ID_T, T]) -> TaskWrapper[ID_T, T]:
        checkpoint = Checkpoint[ID_T, T](checkpoint_path_name or task_function.__name__)
        wrapper = TaskWrapper(
            task_function, checkpoint, raise_on_error, show_progress, force_rerun
        )
        return wrapper

    return decorator


if __name__ == "__main__":
    import random

    async def main():
        @jsonl_checkpoint(
            checkpoint_path_name=".test/test",
            raise_on_error=False,
            show_progress=True,
            force_rerun=False,
        )
        async def task(id: int) -> dict[str, int | float]:
            await asyncio.sleep(random.random() * 10)
            return {"id": id, "data": id / (id % 3)}

        # 创建一���测试用的 id 列表
        test_ids = list(range(1, 20))

        async for result in task.as_completed(test_ids):
            print(result)

        print(f"Finished {len(task.checkpoint.datas)} tasks.")

    asyncio.run(main())
