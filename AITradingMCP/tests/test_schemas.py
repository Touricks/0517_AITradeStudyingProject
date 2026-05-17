from __future__ import annotations

import unittest
from unittest.mock import patch

from aitrading_ability_mcp import schemas
from aitrading_ability_mcp.client import AITradingClient
from aitrading_ability_mcp.tools import call_tool, list_tools


class FakeClient:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def get(self, path):
        self.last_path = path
        return self.snapshot


class SchemaTest(unittest.TestCase):
    def test_all_tools_have_strict_object_schemas(self) -> None:
        for tool in list_tools():
            schema = tool["inputSchema"]
            self.assertEqual(schema["type"], "object", tool["name"])
            self.assertIn("additionalProperties", schema, tool["name"])

    def test_invalid_tool_args_fail_before_backend_call(self) -> None:
        client = AITradingClient("http://127.0.0.1:1", timeout_seconds=0.01)
        is_error, payload = call_tool(client, "aitrading_extract_user_profile", {"unexpected": "field"})
        self.assertTrue(is_error)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error_type"], "validation_error")
        self.assertIn("arguments.unexpected is not allowed", payload["details"]["errors"])

    def test_extract_profile_infers_single_local_user(self) -> None:
        client = FakeClient(
            {
                "user_profiles": {
                    "u_001": {
                        "user_id": "u_001",
                        "trader_type": "规则型交易者",
                        "total_score": 68,
                        "dimension_scores": {"risk_control": 14},
                        "risk_tags": ["追涨"],
                        "weaknesses": ["执行纪律"],
                        "risk_level": "medium",
                        "updated_at": "2026-05-17T00:00:00+00:00",
                    }
                },
                "questionnaire_results": [],
                "assessment_results": [],
                "session_memories": [],
            }
        )
        is_error, payload = call_tool(client, "aitrading_extract_user_profile", {})
        self.assertFalse(is_error)
        data = payload["data"]
        self.assertEqual("u_001", data["user_id"])
        self.assertEqual("single_user_memory", data["user_resolution"]["source"])
        self.assertEqual("compact_profile", data["profile_status"])

    def test_extract_profile_reports_ambiguous_users(self) -> None:
        client = FakeClient(
            {
                "user_profiles": {"u_001": {"user_id": "u_001"}, "u_002": {"user_id": "u_002"}},
                "questionnaire_results": [],
                "assessment_results": [],
                "session_memories": [],
            }
        )
        is_error, payload = call_tool(client, "aitrading_extract_user_profile", {})
        self.assertFalse(is_error)
        data = payload["data"]
        self.assertEqual("ambiguous_user", data["profile_status"])
        self.assertEqual(["u_001", "u_002"], data["user_resolution"]["candidates"])

    def test_default_user_env_resolves_without_argument(self) -> None:
        client = FakeClient(
            {
                "user_profiles": {"u_001": {"user_id": "u_001"}, "u_002": {"user_id": "u_002"}},
                "questionnaire_results": [],
                "assessment_results": [],
                "session_memories": [],
            }
        )
        with patch.dict("os.environ", {"AITRADING_MCP_DEFAULT_USER_ID": "u_002"}):
            is_error, payload = call_tool(client, "aitrading_extract_user_profile", {})
        self.assertFalse(is_error)
        self.assertEqual("u_002", payload["data"]["user_id"])
        self.assertEqual("env", payload["data"]["user_resolution"]["source"])

    def test_default_tool_list_is_profile_reader_only(self) -> None:
        names = [tool["name"] for tool in list_tools()]
        self.assertIn("aitrading_extract_user_profile", names)
        self.assertIn("aitrading_get_user_profile_raw", names)
        self.assertNotIn("aitrading_submit_questionnaire_assessment", names)
        self.assertNotIn("aitrading_check_behavior_plan", names)

    def test_write_tools_are_opt_in(self) -> None:
        client = AITradingClient("http://127.0.0.1:1", timeout_seconds=0.01)
        is_error, payload = call_tool(client, "aitrading_check_behavior_plan", {})
        self.assertTrue(is_error)
        self.assertEqual(payload["error_type"], "tool_disabled")
        with patch.dict("os.environ", {"AITRADING_MCP_ENABLE_WRITE_TOOLS": "true"}):
            names = [tool["name"] for tool in list_tools()]
        self.assertIn("aitrading_check_behavior_plan", names)

    def test_behavior_plan_schema_requires_training_fields(self) -> None:
        schema = schemas.behavior_plan_schema()
        args = {
            "trade_plan": {
                "reason": "计划测试",
                "stop_loss": "",
                "max_loss": "2%",
                "holding_period": "1-2周",
                "emotion": "平稳",
            }
        }
        args = schemas.apply_defaults(schema, args)
        self.assertEqual([], schemas.validate(schema, args))


if __name__ == "__main__":
    unittest.main()
