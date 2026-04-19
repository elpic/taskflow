from src.server import task_complete, task_create, task_fail, task_list, task_start


class TestTaskList:
    async def test_task_list_empty(self):
        result = await task_list()
        assert result == "No tasks found."

    async def test_task_list_single_task(self):
        await task_create("My Task")
        result = await task_list()
        assert "My Task" in result
        assert "pending" in result

    async def test_task_list_nested_tasks(self):
        root_id = await task_create("Root")
        await task_create("Child", parent_id=root_id)
        result = await task_list()
        assert "Root" in result
        assert "Child" in result
        assert "└──" in result

    async def test_task_list_shows_status_icons(self):
        task_id = await task_create("Started")
        await task_start(task_id)
        result = await task_list()
        assert "in_progress" in result

    async def test_task_list_multiple_roots(self):
        await task_create("Root A")
        await task_create("Root B")
        result = await task_list()
        assert "Root A" in result
        assert "Root B" in result

    async def test_task_list_shows_all_statuses(self):
        await task_create("Pending Task")
        t2 = await task_create("Started Task")
        t3 = await task_create("Failed Task")
        await task_start(t2)
        await task_start(t3)
        await task_fail(t3, "broken")
        result = await task_list()
        assert "pending" in result
        assert "in_progress" in result
        assert "failed" in result

    async def test_task_list_with_completed_task(self):
        task_id = await task_create("Done Task")
        await task_complete(task_id)
        result = await task_list()
        assert "done" in result
