"""The read-only MCP server: the protocol, the tools, and the guard Cairn applies to requests that come from it."""
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from cairn import config, mcp, server


class ProtocolTest(unittest.TestCase):
    def ask(self, method, params=None, ident=1):
        message = {"jsonrpc": "2.0", "method": method}
        if ident is not None:
            message["id"] = ident
        if params is not None:
            message["params"] = params
        return mcp.handle(message)

    def test_initialize_answers_with_a_known_protocol_and_the_tools_capability(self):
        reply = self.ask("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "x"}})
        self.assertEqual(reply["result"]["protocolVersion"], "2024-11-05")
        self.assertIn("tools", reply["result"]["capabilities"])
        self.assertEqual(self.ask("initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"], mcp.PROTOCOLS[0])

    def test_a_notification_gets_no_answer(self):
        self.assertIsNone(self.ask("notifications/initialized", ident=None))

    def test_tools_are_three_and_all_declared_read_only(self):
        tools = self.ask("tools/list")["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {"cairn_search", "cairn_list_notes", "cairn_get_note"})
        self.assertTrue(all(t["annotations"]["readOnlyHint"] and not t["annotations"]["destructiveHint"] for t in tools))

    def test_unknown_method_and_bad_requests(self):
        self.assertEqual(self.ask("resources/list")["error"]["code"], -32601)
        self.assertEqual(mcp.handle({"id": 1})["error"]["code"], -32600)
        self.assertEqual(self.ask("tools/call", {"arguments": {}})["error"]["code"], -32602)

    def test_unknown_tool_is_a_tool_error_not_a_crash(self):
        result = self.ask("tools/call", {"name": "cairn_delete_note", "arguments": {"id": "a"}})["result"]
        self.assertTrue(result["isError"])

    def test_serve_reads_lines_and_survives_garbage(self):
        out = io.StringIO()
        lines = '{"jsonrpc":"2.0","id":1,"method":"ping"}\nnot json\n\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        mcp.serve(io.StringIO(lines), out)
        replies = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(replies[0]["result"], {})
        self.assertEqual(replies[1]["error"]["code"], -32700)
        self.assertEqual(len(replies), 2)


class ToolTest(unittest.TestCase):
    def test_get_note_cuts_what_is_too_long_and_marks_it_as_data(self):
        note = {"id": "n1", "title": "T", "date": "2026-11-17", "audio": "/media/x/Audio/a.mp3", "sha256": "ff", "source": "2026/a.mp3",
                "status": "done", "summary": {"tldr": "short"}, "clean": "word " * 20000}
        with mock.patch.object(mcp, "get", return_value=dict(note)):
            text = mcp.call("cairn_get_note", {"id": "n1", "transcript": True})["content"][0]["text"]
        self.assertTrue(text.startswith(mcp.NOTICE))
        self.assertLessEqual(len(text), mcp.LIMIT_CHARS + len(mcp.NOTICE) + 200)
        self.assertIn("Cut here", text)
        self.assertNotIn("/media/x", text)

    def test_ids_are_checked_before_any_request(self):
        with mock.patch.object(mcp, "get") as get:
            result = mcp.call("cairn_get_note", {"id": "../../api/lock/disable"})
        get.assert_not_called()
        self.assertTrue(result["isError"])

    def test_search_returns_extracts_without_markup(self):
        hits = [{"id": "n1", "title": "Brandt", "date": "2026-11-01", "hits": [{"parts": [{"t": "le budget de ", "m": False}, {"t": "300", "m": True}]}]}]
        with mock.patch.object(mcp, "get", return_value={"results": hits}) as get:
            text = mcp.call("cairn_search", {"query": "budget & co"})["content"][0]["text"]
        self.assertIn("le budget de 300", text)
        self.assertIn("budget%20%26%20co", get.call_args.args[0])

    def test_a_refusal_from_cairn_is_explained(self):
        with mock.patch.object(mcp, "_address", return_value=(1, "k" * 20)), mock.patch.object(mcp.http.client, "HTTPConnection") as conn:
            reply = conn.return_value.getresponse.return_value
            reply.status, reply.read.return_value = 423, b'{"error":"locked"}'
            result = mcp.call("cairn_list_notes", {})
        self.assertTrue(result["isError"])
        self.assertIn("locked", result["content"][0]["text"].lower())

    def test_only_get_requests_leave_this_module(self):
        with mock.patch.object(mcp, "_address", return_value=(1, "k" * 20)), mock.patch.object(mcp.http.client, "HTTPConnection") as conn:
            reply = conn.return_value.getresponse.return_value
            reply.status, reply.read.return_value = 200, b'{"notes": []}'
            mcp.call("cairn_list_notes", {"tag": "x"})
        self.assertEqual(conn.return_value.request.call_args.args[0], "GET")
        self.assertEqual(conn.call_args.args[0], "127.0.0.1")


class GuardTest(unittest.TestCase):
    """Requests marked as coming from the MCP server: read only, and only when MCP access is on."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"CAIRN_HOME": str(Path(self.tmp.name) / "Cairn")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app, self.httpd = server.make_server(18797)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        for ident, date, tags in (("old", "2026-10-01", ["a"]), ("new", "2026-11-10", ["b"])):
            self.app.store.save({"id": ident, "title": ident, "date": date, "status": "done", "tags": tags, "duration": 60,
                                 "summary": {"tldr": "x"}, "segments": [{"text": "secret words"}]})

    def call(self, method, path, mcp_client=True, body=None):
        headers = {"X-Cairn-Key": self.app.token}
        if mcp_client:
            headers["X-Cairn-Client"] = "mcp"
        if method == "POST":
            headers.update({"X-Cairn": "1", "Content-Type": "application/json"})
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=10)
        conn.request(method, path, body=json.dumps(body or {}) if method == "POST" else None, headers=headers)
        reply = conn.getresponse()
        data = json.loads(reply.read() or b"{}")
        conn.close()
        return reply.status, data

    def test_off_by_default(self):
        self.assertEqual(self.call("GET", "/api/mcp/notes"), (403, {"error": "mcp_off"}))

    def test_on_it_lists_newest_first_with_filters(self):
        config.save_settings({"mcp": True})
        status, data = self.call("GET", "/api/mcp/notes")
        self.assertEqual(status, 200)
        self.assertEqual([n["id"] for n in data["notes"]], ["new", "old"])
        self.assertEqual(set(data["notes"][0]), {"id", "title", "date", "duration", "status", "tags"})
        self.assertEqual([n["id"] for n in self.call("GET", "/api/mcp/notes?since=2026-11-01")[1]["notes"]], ["new"])
        self.assertEqual([n["id"] for n in self.call("GET", "/api/mcp/notes?tag=%23A")[1]["notes"]], ["old"])
        self.assertEqual(len(self.call("GET", "/api/mcp/notes?limit=1")[1]["notes"]), 1)
        self.assertEqual(self.call("GET", "/api/note/new")[0], 200)

    def test_nothing_can_be_changed_or_reached_beyond_reading_notes(self):
        config.save_settings({"mcp": True})
        for method, path in (("POST", "/api/settings"), ("POST", "/api/cancel"), ("POST", "/api/lock/disable"), ("GET", "/api/state"),
                             ("GET", "/api/lock"), ("GET", "/api/note/new/audio"), ("GET", "/api/note/new/export"), ("POST", "/api/note/new/action")):
            status, data = self.call(method, path, body={"mcp": False})
            self.assertEqual((status, data), (403, {"error": "mcp_read_only"}), path)
        self.assertTrue(config.load_settings()["mcp"])

    def test_the_session_key_is_still_required(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=10)
        conn.request("GET", "/api/mcp/notes", headers={"X-Cairn-Client": "mcp"})
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()

    def test_the_whole_chain_from_the_tool_to_the_server(self):
        config.save_settings({"mcp": True})
        (config.home() / "url.txt").write_text("http://127.0.0.1:%d/?k=%s\n" % (self.app.port, self.app.token))
        text = mcp.call("cairn_list_notes", {})["content"][0]["text"]
        self.assertIn("new | 2026-11-10", text)
        config.save_settings({"mcp": False})
        self.assertIn("switched off", mcp.call("cairn_list_notes", {})["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
