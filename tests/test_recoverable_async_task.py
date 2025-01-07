import asyncio
import json
from pathlib import Path

import pytest

from recoverable_async_task import (
    RecoverableTask,
    TaskRecord,
    TaskStorage,
    make_recoverable,
)

# 测试用的临时目录
TEST_DIR = Path(".test_output")


@pytest.fixture(autouse=True)
def setup_teardown():
    """设置和清理测试环境"""
    # 设置
    TEST_DIR.mkdir(exist_ok=True)
    yield
    # 清理
    import shutil

    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)


class TestTaskStorage:
    def test_init_and_load(self):
        """测试 TaskStorage 的初始化和加载功能"""
        storage_path = TEST_DIR / "test_storage"
        storage = TaskStorage[int, dict](str(storage_path))

        assert storage.storage_path.exists()
        assert len(storage.records) == 0

    def test_add_and_load(self):
        """测试添加记录和重新加载"""
        storage_path = TEST_DIR / "test_add"
        storage = TaskStorage[int, dict](str(storage_path))

        test_data = {"test": "value"}
        storage.add(test_data, id=1)

        # 创建新的 storage 实例来测试加载
        new_storage = TaskStorage[int, dict](str(storage_path))
        assert 1 in new_storage.records
        assert new_storage.records[1] == test_data

    def test_export(self):
        """测试导出功能"""
        storage_path = TEST_DIR / "test_export"
        storage = TaskStorage[int, dict](str(storage_path))

        test_data = {"test": "value"}
        storage.add(test_data, id=1)

        export_path = storage.export(TEST_DIR / "export.json")
        assert Path(export_path).exists()

        with open(export_path) as f:
            exported_data = json.load(f)
            assert exported_data == [test_data]

    def test_load_with_invalid_json(self):
        """测试加载无效 JSON 数据时的错误处理"""
        storage_path = TEST_DIR / "test_invalid_json"
        storage_path.parent.mkdir(exist_ok=True)

        # 写入一些无效的 JSON 数据
        with storage_path.open("w") as f:
            f.write('{"id": 1, "data": "valid"}\n')  # 有效行
            f.write("invalid json\n")  # 无效行
            f.write('{"id": 2, "data": "valid"}\n')  # 有效行

        # 应该能够加载有效的记录，同时忽略无效的记录
        records: list[TaskRecord] = list(TaskStorage.load(storage_path))
        assert len(records) == 2
        assert records[0]["id"] == 1
        assert records[1]["id"] == 2

    def test_json_serialization_error(self):
        """测试 JSON 序列化错误处理"""
        storage_path = TEST_DIR / "test_serialization"
        storage = TaskStorage[int, dict](str(storage_path))

        # 创建一个包含不可序列化对象的数据
        class UnserializableObject:
            pass

        test_data = {"test": UnserializableObject()}
        storage.add(test_data, id=1)

        # 验证数据被存储为字符串形式
        new_storage = TaskStorage[int, dict](str(storage_path))
        assert "UnserializableObject" in str(new_storage.records[1]["test"])


class TestRecoverableTask:
    @pytest.mark.asyncio
    async def test_basic_execution(self):
        """测试基本的任务执行"""
        storage_path = TEST_DIR / "test_execution"

        async def task(id: int) -> dict:
            return {"id": id, "value": id * 2}

        storage = TaskStorage[int, dict](str(storage_path))
        recoverable = RecoverableTask(task, storage)

        result = await recoverable(1)
        assert result == {"id": 1, "value": 2}
        assert 1 in storage.records

    @pytest.mark.asyncio
    async def test_as_completed(self):
        """测试批量任务执行"""
        storage_path = TEST_DIR / "test_batch"

        async def task(id: int) -> dict:
            await asyncio.sleep(0.1)  # 模拟异步操作
            return {"id": id, "value": id * 2}

        storage = TaskStorage[int, dict](str(storage_path))
        recoverable = RecoverableTask(task, storage)

        id_list = [1, 2, 3]
        results = []
        async for result in recoverable.as_completed(id_list):
            results.append(result)

        assert len(results) == 3
        assert all(r["value"] == r["id"] * 2 for r in results)

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """测试错误处理"""
        storage_path = TEST_DIR / "test_error"

        async def failing_task(id: int) -> dict:
            if id == 2:
                raise ValueError("测试错误")
            return {"id": id, "value": id * 2}

        storage = TaskStorage[int, dict](str(storage_path))

        # 测试抛出错误的情况
        recoverable = RecoverableTask(failing_task, storage)
        with pytest.raises(ValueError):
            await recoverable(2)  # 直接测试单个失败任务

    @pytest.mark.asyncio
    async def test_progress_bar(self):
        """测试进度条功能"""
        storage_path = TEST_DIR / "test_progress"

        async def task(id: int) -> dict:
            await asyncio.sleep(0.01)
            return {"id": id}

        storage = TaskStorage[int, dict](str(storage_path))

        # 测试显示进度条
        recoverable = RecoverableTask(task, storage, show_progress=True)
        results = []
        async for result in recoverable.as_completed([1, 2, 3]):
            results.append(result)
        assert len(results) == 3

        # 测试不显示进度条
        recoverable = RecoverableTask(task, storage, show_progress=False)
        results = []
        async for result in recoverable.as_completed([4, 5, 6]):
            results.append(result)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_force_rerun_detailed(self):
        """详细测试强制重新运行功能"""
        storage_path = TEST_DIR / "test_force_rerun_detailed"
        execution_count = 0

        async def task(id: int) -> dict:
            nonlocal execution_count
            execution_count += 1
            return {"id": id, "count": execution_count}

        storage = TaskStorage[int, dict](str(storage_path))
        recoverable = RecoverableTask(task, storage)

        # 首次运行
        result1 = await recoverable(1)
        assert result1["count"] == 1

        # 不强制重新运行时应该返回缓存的结果
        result2 = await recoverable(1)
        assert result2["count"] == 1
        assert execution_count == 1

        # 强制重新运行
        recoverable.force_rerun = True
        result3 = await recoverable(1)
        assert result3["count"] == 2
        assert execution_count == 2

        # 测试批量处理中的强制重新运行
        results = []
        async for result in recoverable.as_completed([1, 2]):
            results.append(result)
        assert len(results) == 2
        assert execution_count == 4  # 两个任务都应该被执行


class TestMakeRecoverable:
    @pytest.mark.asyncio
    async def test_decorator(self):
        """测试装饰器功能"""

        @make_recoverable(storage_path_name=str(TEST_DIR / "test_decorator"))
        async def task(id: int) -> dict:
            return {"id": id, "value": id * 2}

        result = await task(1)
        assert result == {"id": 1, "value": 2}
        assert 1 in task.storage.records

    @pytest.mark.asyncio
    async def test_force_rerun(self):
        """测试强制重新运行功能"""
        storage_path = str(TEST_DIR / "test_force_rerun")
        counter = 0

        @make_recoverable(storage_path_name=storage_path)
        async def task(id: int) -> dict:
            nonlocal counter
            counter += 1
            return {"id": id, "value": counter}

        # 第一次运行
        await task(1)
        assert counter == 1

        # 正常情况下不会重新运行
        await task(1)
        assert counter == 1

        # 使用 force_rerun
        task.force_rerun = True
        await task(1)
        assert counter == 2

    @pytest.mark.asyncio
    async def test_decorator_error_handling(self):
        """测试装饰器的错误处理功能"""
        storage_path = str(TEST_DIR / "test_decorator_error")

        @make_recoverable(storage_path_name=storage_path)
        async def failing_task(id: int) -> dict:
            if id == 2:
                raise ValueError("测试错误")
            return {"id": id, "value": id * 2}

        # 测试成功的情况
        result = await failing_task(1)
        assert result == {"id": 1, "value": 2}

        # 测试失败的情况
        with pytest.raises(ValueError):
            await failing_task(2)

        # 测试批量处理
        results = []
        async for result in failing_task.as_completed([1, 3]):  # 跳过会失败的 id=2
            results.append(result)
        assert len(results) == 2
        assert all(r["value"] == r["id"] * 2 for r in results)
