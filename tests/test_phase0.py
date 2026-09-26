import unittest
from unittest.mock import MagicMock, Mock, patch

from flamoris_ai_agent import chat, db
from flamoris_ai_agent.intelligence import IntelligenceClient, IntelligenceError
from flamoris_ai_agent.register_runtime import register


class IntelligenceClientTests(unittest.TestCase):
    def test_resolves_served_id_and_builds_chat_payload(self):
        models = Mock()
        models.json.return_value = {"data": [{"id": "actual-served-id"}]}
        answer = Mock()
        answer.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "こんにちは"}}]
        }
        messages = [{"role": "system", "content": "梅子"}]
        with patch(
            "flamoris_ai_agent.intelligence.requests.request", side_effect=[models, answer]
        ) as request:
            client = IntelligenceClient("http://127.0.0.1:8081/")
            model = client.resolve_model()
            self.assertEqual(model, "actual-served-id")
            self.assertEqual(client.chat(model, messages), "こんにちは")
        self.assertEqual(request.call_args_list[0].args, ("GET", "http://127.0.0.1:8081/v1/models"))
        self.assertEqual(
            request.call_args_list[1].kwargs["json"],
            {"model": model, "messages": messages, "stream": False},
        )

    def test_rejects_wrong_model_and_ambiguous_list(self):
        response = Mock()
        response.json.return_value = {"data": [{"id": "a"}, {"id": "b"}]}
        with patch("flamoris_ai_agent.intelligence.requests.request", return_value=response):
            with self.assertRaisesRegex(IntelligenceError, "multiple models"):
                IntelligenceClient("http://localhost:8081").resolve_model()
            with self.assertRaisesRegex(IntelligenceError, "absent"):
                IntelligenceClient("http://localhost:8081", "wrong").resolve_model()

    def test_network_and_invalid_response_fail_cleanly(self):
        import requests

        with patch(
            "flamoris_ai_agent.intelligence.requests.request",
            side_effect=requests.ConnectionError("offline"),
        ):
            with self.assertRaises(IntelligenceError):
                IntelligenceClient("http://localhost:8081").resolve_model()
        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": "  "}}]}
        with patch("flamoris_ai_agent.intelligence.requests.request", return_value=response):
            with self.assertRaisesRegex(IntelligenceError, "Invalid chat completion"):
                IntelligenceClient("http://localhost:8081").chat("model", [])


class ModelProvenanceTests(unittest.TestCase):
    def test_rejects_old_ollama_identity(self):
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = ("ollama", "umeko")
        with self.assertRaisesRegex(RuntimeError, "register_runtime"):
            db.validate_model_ref(conn, "old-id", "actual-served-id")

    def test_registration_does_not_repoint_existing_model(self):
        conn = MagicMock()
        conn.execute.side_effect = [
            Mock(),
            Mock(),
            Mock(fetchone=Mock(return_value=("lime",))),
            Mock(fetchone=Mock(return_value=("llama.cpp", "different-id"))),
        ]
        with patch("flamoris_ai_agent.register_runtime.platform.node", return_value="lime"):
            with self.assertRaisesRegex(RuntimeError, "different model"):
                register(
                    conn,
                    host_key="lime",
                    model_key="llama.cpp:gpt-oss-20b",
                    served_model="actual-id",
                )
        self.assertIn("ON CONFLICT (model_key) DO NOTHING", conn.execute.call_args_list[1].args[0])


class UmekoSessionTests(unittest.TestCase):
    def test_failed_conversation_start_closes_instance(self):
        client = Mock()
        client.resolve_model.return_value = "model-id"
        with (
            patch.object(chat, "IntelligenceClient", return_value=client),
            patch.object(chat, "get_connection", return_value=Mock()),
            patch.object(
                chat,
                "load_runtime_refs",
                return_value={
                    "agent_id": "agent",
                    "project_id": "project",
                    "model_id": "model-row",
                },
            ),
            patch.object(chat, "validate_model_ref"),
            patch.object(chat, "get_previous_conversation", return_value=None),
            patch.object(chat, "start_instance", return_value="instance"),
            patch.object(chat, "start_conversation", side_effect=RuntimeError("DB error")),
            patch.object(chat, "close_instance") as close,
        ):
            with self.assertRaisesRegex(RuntimeError, "DB error"):
                chat.main()
        close.assert_called_once_with(unittest.mock.ANY, "instance")

    def test_message_persistence_previous_context_and_clean_exit(self):
        refs = {"agent_id": "same-agent", "project_id": "project", "model_id": "model-row"}
        runtime = {
            "conversation_id": "new-conversation",
            "conversation_session_id": "session",
            "human_participant_id": "human",
            "agent_participant_id": "agent",
        }
        previous = {
            "conversation_id": "old-conversation",
            "messages": [
                {"sender": "愛乃", "content": "前回の話"},
            ],
        }
        client = Mock()
        client.resolve_model.return_value = "actual-served-id"
        client.chat.return_value = "梅だよ"
        with (
            patch.object(chat, "IntelligenceClient", return_value=client),
            patch.object(chat, "get_connection", return_value=Mock()),
            patch.object(chat, "load_runtime_refs", return_value=refs),
            patch.object(chat, "validate_model_ref") as validate,
            patch.object(chat, "get_previous_conversation", return_value=previous) as get_previous,
            patch.object(chat, "start_instance", return_value="instance"),
            patch.object(chat, "start_conversation", return_value=runtime) as start,
            patch.object(chat, "save_message") as save,
            patch.object(chat, "close_runtime") as close,
            patch("builtins.input", side_effect=["こんにちは", "/bye"]),
        ):
            chat.main()
        validate.assert_called_once_with(unittest.mock.ANY, "model-row", "actual-served-id")
        get_previous.assert_called_once()
        self.assertEqual(get_previous.call_args.kwargs["agent_id"], "same-agent")
        self.assertNotIn("前回の話", start.call_args.kwargs["system_prompt"])
        self.assertIn("前回の話", client.chat.call_args.args[1][1]["content"])
        self.assertEqual(
            start.call_args.kwargs["system_context"]["previous_conversation"], previous
        )
        self.assertEqual([c.kwargs["role"] for c in save.call_args_list], ["user", "assistant"])
        self.assertEqual(
            save.call_args_list[1].kwargs["metadata"], {"intelligence_model": "actual-served-id"}
        )
        self.assertEqual(client.chat.call_args.args[1][-1]["content"], "こんにちは")
        close.assert_called_once_with(
            unittest.mock.ANY,
            conversation_id="new-conversation",
            conversation_session_id="session",
            instance_id="instance",
        )

    def test_failed_completion_leaves_only_user_message_and_closes(self):
        refs = {"agent_id": "same-agent", "project_id": "project", "model_id": "model-row"}
        runtime = {
            "conversation_id": "conversation",
            "conversation_session_id": "session",
            "human_participant_id": "human",
            "agent_participant_id": "agent",
        }
        client = Mock()
        client.resolve_model.return_value = "model-id"
        client.chat.side_effect = IntelligenceError("offline")
        with (
            patch.object(chat, "IntelligenceClient", return_value=client),
            patch.object(chat, "get_connection", return_value=Mock()),
            patch.object(chat, "load_runtime_refs", return_value=refs),
            patch.object(chat, "validate_model_ref"),
            patch.object(chat, "get_previous_conversation", return_value=None),
            patch.object(chat, "start_instance", return_value="instance"),
            patch.object(chat, "start_conversation", return_value=runtime),
            patch.object(chat, "save_message") as save,
            patch.object(chat, "close_runtime") as close,
            patch("builtins.input", side_effect=["こんにちは", "/bye"]),
        ):
            chat.main()
        self.assertEqual(save.call_count, 1)
        self.assertEqual(save.call_args.kwargs["role"], "user")
        close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
