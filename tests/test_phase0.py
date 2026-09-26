import unittest
from unittest.mock import MagicMock, Mock, patch

from flamoris_ai_agent import db
from flamoris_ai_agent.register_runtime import register


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
