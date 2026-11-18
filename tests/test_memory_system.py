"""Automated unit and integration tests for Phase 7 Persistent Memory System."""

import datetime
from pathlib import Path
import pytest

from local_agent.memory.privacy import PrivacyScrubber, PrivacyViolationError
from local_agent.memory.schema import MemoryCategory, MemoryEntry, UserPreference
from local_agent.memory.store import MemoryStore
from local_agent.memory.manager import MemoryManager
from local_agent.tasks.registry import ToolRegistry
from local_agent.tasks.memory_tools import register_memory_tools
from local_agent.engine.nova_engine import NovaEngine
from local_agent.tasks.planner import TaskPlanner
from local_agent.llm.provider import LLMProvider, ChatMessage, ProviderConfig


# ---------------------------------------------------------------------------
# Database & Store Tests
# ---------------------------------------------------------------------------
class TestMemoryStore:
    """Verify SQLite table initialization, CRUD, and expiration."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> MemoryStore:
        db_file = tmp_path / "test_memory.db"
        return MemoryStore(db_file)

    def test_schema_initialization(self, store: MemoryStore):
        # Verify default user is created
        cur = store._conn.execute("SELECT * FROM users WHERE id = 'default_user'")
        row = cur.fetchone()
        assert row is not None
        assert row["username"] == "akramlatif"

    def test_save_and_get_memory(self, store: MemoryStore):
        entry = MemoryEntry(
            category=MemoryCategory.PROJECT,
            key="NOVA_goal",
            content="Local AI personal assistant for Windows 11",
            confidence=0.95,
        )
        mem_id = store.save_memory(entry)
        assert mem_id > 0

        fetched = store.get_memory(category="project", key="NOVA_goal")
        assert fetched is not None
        assert fetched.content == "Local AI personal assistant for Windows 11"
        assert fetched.confidence == 0.95
        assert fetched.access_count == 1

    def test_search_memories(self, store: MemoryStore):
        store.save_memory(MemoryEntry(category=MemoryCategory.FACT, key="fav_editor", content="Visual Studio Code"))
        store.save_memory(MemoryEntry(category=MemoryCategory.FACT, key="fav_shell", content="PowerShell 7"))
        store.save_memory(MemoryEntry(category=MemoryCategory.PROJECT, key="project_name", content="NOVA Assistant"))

        results = store.search_memories(query="Visual Studio")
        assert len(results) == 1
        assert results[0].key == "fav_editor"

        cat_results = store.search_memories(query="NOVA", category="project")
        assert len(cat_results) == 1
        assert cat_results[0].key == "project_name"

    def test_delete_memory(self, store: MemoryStore):
        entry = MemoryEntry(category=MemoryCategory.FACT, key="temporary_note", content="Delete me")
        mem_id = store.save_memory(entry)
        assert store.delete_memory(mem_id) is True
        assert store.get_memory("fact", "temporary_note") is None

    def test_clear_category(self, store: MemoryStore):
        store.save_memory(MemoryEntry(category=MemoryCategory.TEMPORARY, key="t1", content="one"))
        store.save_memory(MemoryEntry(category=MemoryCategory.TEMPORARY, key="t2", content="two"))
        count = store.clear_category("temporary")
        assert count == 2
        assert len(store.list_memories(category="temporary")) == 0

    def test_purge_expired_memories(self, store: MemoryStore):
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)
        entry = MemoryEntry(
            category=MemoryCategory.TEMPORARY,
            key="expired_key",
            content="Old data",
            expires_at=past_time,
        )
        store.save_memory(entry)
        # Should not show in get_memory
        assert store.get_memory("temporary", "expired_key") is None
        # Purge removes it physically
        purged = store.purge_expired()
        assert purged >= 1

    def test_preferences_crud(self, store: MemoryStore):
        store.set_preference(key="default_browser", value="chrome", category="browser")
        val = store.get_preference("default_browser", category="browser")
        assert val == "chrome"

        prefs = store.list_preferences(category="browser")
        assert prefs == {"default_browser": "chrome"}

    def test_conversations_and_messages(self, store: MemoryStore):
        conv_id = "test-conv-123"
        store.create_conversation(conv_id, title="Test Chat")
        m1 = store.add_message(conv_id, "user", "Hello NOVA")
        m2 = store.add_message(conv_id, "assistant", "Hello Akram")

        messages = store.get_messages(conv_id)
        assert len(messages) == 2
        assert messages[0]["content"] == "Hello NOVA"
        assert messages[1]["content"] == "Hello Akram"

    def test_tasks_and_logs(self, store: MemoryStore):
        task_id = "task-alpha-1"
        store.record_task(task_id, user_request="Download PDF", status="running")
        store.add_task_step_log(task_id, step_id=1, tool_name="browser_navigate", status="success", duration_ms=120)
        store.update_task_status(task_id, status="completed", summary="PDF downloaded successfully")

        history = store.get_task_history(limit=5)
        assert len(history) == 1
        assert history[0]["id"] == task_id
        assert history[0]["status"] == "completed"


# ---------------------------------------------------------------------------
# Privacy Scrubber Tests
# ---------------------------------------------------------------------------
class TestPrivacyScrubber:
    """Verify that credentials, tokens, and passwords are strictly blocked."""

    def test_block_openai_token(self):
        with pytest.raises(PrivacyViolationError, match="OpenAI/LLM Key"):
            PrivacyScrubber.validate_memory_content("key", "sk-1234567890abcdef1234567890abcdef")

    def test_block_github_token(self):
        with pytest.raises(PrivacyViolationError, match="GitHub Token"):
            PrivacyScrubber.validate_memory_content("token", "ghp_1234567890abcdefghijklmnopqrstuvwxyz1234")

    def test_block_password(self):
        with pytest.raises(PrivacyViolationError, match="Password"):
            PrivacyScrubber.validate_memory_content("creds", "password = SuperSecretPass123!")

    def test_block_private_key(self):
        with pytest.raises(PrivacyViolationError, match="Private Key"):
            PrivacyScrubber.validate_memory_content("ssh_key", "-----BEGIN RSA PRIVATE KEY-----\nMIIE...")

    def test_clean_content_passes(self):
        # Standard facts and project details pass cleanly
        PrivacyScrubber.validate_memory_content("project_dir", "E:\\3rd Semester\\Projects\\NOVA")
        PrivacyScrubber.validate_memory_content("preferred_browser", "Google Chrome")

    def test_scrub_text(self):
        dirty = "User token is ghp_1234567890abcdefghijklmnopqrstuvwxyz1234 and password=secretword"
        clean = PrivacyScrubber.scrub_text(dirty)
        assert "ghp_" not in clean
        assert "secretword" not in clean
        assert "[REDACTED_SECRET]" in clean


# ---------------------------------------------------------------------------
# High-Level Memory Manager Tests
# ---------------------------------------------------------------------------
class TestMemoryManager:
    """Verify short-term, long-term, duplicate detection, and prompt context formatting."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> MemoryManager:
        db_file = tmp_path / "nova_manager.db"
        return MemoryManager(db_path=db_file)

    def test_remember_and_duplicate_detection(self, manager: MemoryManager):
        id1 = manager.remember(key="editor", content="VS Code", category=MemoryCategory.APPLICATION)
        assert id1 is not None

        # Exact duplicate returns the same ID without creating a new entry
        id2 = manager.remember(key="editor", content="VS Code", category=MemoryCategory.APPLICATION)
        assert id1 == id2

    def test_get_context_for_prompt(self, manager: MemoryManager):
        manager.remember(key="project_tech", content="Python, Playwright, SQLite", category=MemoryCategory.PROJECT)
        manager.set_preference("preferred_editor", "VS Code")

        context = manager.get_context_for_prompt("What tech stack does our project use?")
        assert "### Relevant Persistent Memories" in context
        assert "project_tech" in context
        assert "Playwright" in context

    def test_short_term_active_task(self, manager: MemoryManager):
        manager.set_active_task("task-100", "Analyze logs", intent="Troubleshooting")
        active = manager.get_active_task()
        assert active is not None
        assert active["task_id"] == "task-100"

        manager.record_step_result("task-100", step_id=1, tool_name="file_read", status="success")
        active = manager.get_active_task()
        assert len(active["steps"]) == 1

        manager.complete_active_task("task-100", summary="Logs analyzed")
        assert manager.get_active_task() is None

    def test_remember_task_failure_lesson(self, manager: MemoryManager):
        manager.remember_task_outcome(
            task_id="task-fail-1",
            user_request="Download video from site",
            status="failed",
            error="Site requires captcha login",
        )
        # Verify a task failure memory was retained
        recalled = manager.recall(query="captcha", category=MemoryCategory.TASK)
        assert len(recalled) == 1
        assert "failed" in recalled[0].content

    def test_memory_disable_toggle(self, manager: MemoryManager):
        manager.disable()
        assert manager.remember("key", "content") is None
        assert manager.recall("content") == []
        assert manager.get_context_for_prompt("test") == ""

        manager.enable()
        assert manager.remember("key", "content") is not None
        assert len(manager.recall("content")) == 1

    def test_inspect_and_forget(self, manager: MemoryManager):
        manager.remember(key="doc_folder", content="D:\\Documents", category=MemoryCategory.FOLDER)
        all_mems = manager.inspect_memories()
        assert len(all_mems) == 1
        assert all_mems[0]["key"] == "doc_folder"

        manager.forget_key("folder", "doc_folder")
        assert len(manager.inspect_memories()) == 0


# ---------------------------------------------------------------------------
# Tool Registry Integration Tests
# ---------------------------------------------------------------------------
class TestMemoryToolRegistration:
    """Verify registration and execution of memory tools via ToolRegistry."""

    def test_all_memory_tools_registered(self, tmp_path: Path):
        registry = ToolRegistry()
        db_file = tmp_path / "tools_mem.db"
        manager = MemoryManager(db_path=db_file)
        register_memory_tools(registry, manager=manager)

        expected_tools = [
            "memory_remember",
            "memory_recall",
            "memory_inspect",
            "memory_forget",
            "memory_set_preference",
            "memory_get_preference",
        ]
        for t in expected_tools:
            assert registry.has(t), f"Missing tool: {t}"

    def test_execute_memory_tools(self, tmp_path: Path):
        registry = ToolRegistry()
        db_file = tmp_path / "tools_mem.db"
        manager = MemoryManager(db_path=db_file)
        register_memory_tools(registry, manager=manager)

        # 1. Store via tool
        remember_tool = registry.get("memory_remember")
        res1 = remember_tool.handler(key="favorite_food", content="Biryani", category="fact")
        assert res1["success"] is True

        # 2. Recall via tool
        recall_tool = registry.get("memory_recall")
        res2 = recall_tool.handler(query="Biryani")
        assert res2["count"] == 1
        assert res2["results"][0]["key"] == "favorite_food"

        # 3. Preference via tool
        pref_tool = registry.get("memory_set_preference")
        pref_tool.handler(key="theme", value="dark")
        get_tool = registry.get("memory_get_preference")
        res3 = get_tool.handler(key="theme")
        assert res3["value"] == "dark"


# ---------------------------------------------------------------------------
# NovaEngine & Planner Integration
# ---------------------------------------------------------------------------
class DummyLLMProvider(LLMProvider):
    """Predictable dummy provider for integration tests."""

    def __init__(self, output: str) -> None:
        super().__init__(ProviderConfig(model_name="dummy"))
        self.output = output
        self.last_context = []

    def is_available(self) -> bool:
        return True

    def generate(self, context: list[ChatMessage]) -> str:
        self.last_context = context
        return self.output

    def generate_stream(self, context: list[ChatMessage]):
        yield self.output


class TestMemoryEngineIntegration:
    """Verify that NovaEngine and TaskPlanner inject memory context into prompts."""

    def test_engine_injects_memory_context(self, tmp_path: Path):
        db_file = tmp_path / "engine_mem.db"
        mem = MemoryManager(db_path=db_file)
        mem.remember("favorite_framework", "FastAPI for Phase 8", category=MemoryCategory.FACT)

        response_json = (
            '{"response_type": "conversation", "detected_intent": "chat", '
            '"requested_action": null, "required_tools": [], '
            '"execution_plan": [], "requires_confirmation": false}'
        )
        provider = DummyLLMProvider(response_json)
        engine = NovaEngine(provider=provider, data_dir=tmp_path, memory_manager=mem)

        conv_id = engine.store.new_conversation()
        engine.chat(conv_id, "Which framework do I prefer?")

        # Check that system prompt sent to LLM included the memory context
        system_msg = provider.last_context[0].content
        assert "### Relevant Persistent Memories" in system_msg
        assert "FastAPI" in system_msg

    def test_planner_injects_memory_context(self, tmp_path: Path):
        db_file = tmp_path / "planner_mem.db"
        mem = MemoryManager(db_path=db_file)
        mem.remember("project_root", "E:\\3rd Semester\\Projects\\NOVA", category=MemoryCategory.PROJECT)

        plan_json = (
            '{"intent_summary": "Check files", "expected_result": "Success", '
            '"steps": []}'
        )
        provider = DummyLLMProvider(plan_json)
        registry = ToolRegistry()
        planner = TaskPlanner(provider=provider, registry=registry, memory_manager=mem)

        planner.plan("Inspect files in our project root")
        user_prompt = provider.last_context[1].content
        assert "### Relevant Persistent Memories" in user_prompt
        assert "project_root" in user_prompt
