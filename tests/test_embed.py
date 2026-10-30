"""Search by meaning: the model server is replaced by a stub that turns words into vectors."""

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TOPICS = ["budget", "voyage", "recrutement", "securite"]


def vector(text):
    """A tiny meaning: how much of each topic the text mentions (synonyms count), plus a constant."""
    low = text.lower()
    words = {"budget": ("budget", "francs", "cout", "depense"), "voyage": ("voyage", "avion", "vol", "hotel"),
             "recrutement": ("recrutement", "embauche", "candidat"), "securite": ("securite", "chiffrement", "mot de passe")}
    import zlib

    noise = [0.0] * 64
    noise[zlib.crc32(low.encode()) % 64] = 0.05  # a passage that is about no topic still has its own direction
    return [float(sum(low.count(w) for w in words[t])) for t in TOPICS] + noise


class StubEmbed(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *args):
        pass

    def _send(self, data):
        raw = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._send({"version": "0"} if self.path == "/api/version" else {"models": [{"name": "qwen3-embedding:0.6b", "size": 640000000}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        StubEmbed.seen.append(self.path)
        if self.path == "/api/embed":
            return self._send({"embeddings": [vector(t) for t in body["input"]]})
        self._send({})


def seg(start, text):
    return {"start": float(start), "end": float(start) + 3, "text": text}


class EmbedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.model = ThreadingHTTPServer(("127.0.0.1", 0), StubEmbed)
        threading.Thread(target=cls.model.serve_forever, daemon=True).start()
        os.environ.update(CAIRN_HOME=str(root / "Cairn"), CAIRN_POCKET_DIR=str(root / "none"), CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b",
                          OLLAMA_HOST="127.0.0.1:%d" % cls.model.server_address[1], CAIRN_WHISPER_MODEL=str(root))
        from cairn import config, embed, notes

        cls.config, cls.embed = config, embed
        cls.store = notes.Store(config.home() / "Texts")
        cls.store.save({"id": "a", "status": "done", "title": "Point finances", "date": "2026-10-01T10:00:00", "tags": [],
                        "summary": {"tldr": "Le budget de 300 000 francs est approuvé", "key_points": ["Dépenses maîtrisées"], "actions": [{"what": "Envoyer le plan", "who": "Sophie"}]},
                        "segments": [seg(0, "On parle du budget de l'année."), seg(3, "Les francs prévus couvrent le coût du projet.")]})
        cls.store.save({"id": "b", "status": "done", "title": "Déplacement", "date": "2026-10-02T10:00:00", "tags": [],
                        "summary": {"tldr": "Le voyage est réservé"}, "segments": [seg(0, "Le vol part lundi et l'hôtel est pris.")]})
        cls.store.save({"id": "c", "status": "waiting", "title": "Pas fini", "date": "2026-10-03T10:00:00", "segments": [seg(0, "budget budget")]})

    @classmethod
    def tearDownClass(cls):
        cls.model.shutdown()
        cls.model.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        self.config.save_settings({"embed": "qwen3-embedding:0.6b"})
        self.embed.forget("qwen3-embedding:0.6b")

    def test_a_model_that_is_not_installed_or_chosen_is_not_used(self):
        self.config.save_settings({"embed": None})
        self.assertIsNone(self.embed.chosen())
        self.assertEqual(self.embed.search(self.store, "budget"), [])
        self.assertEqual(self.embed.status(self.store, None), {"model": None, "indexed": 0, "total": 2})
        with self.assertRaises(ValueError):
            self.config.save_settings({"embed": "some-other-model"})

    def test_indexing_covers_finished_notes_only_and_is_incremental(self):
        model = "qwen3-embedding:0.6b"
        self.assertEqual(self.embed.build(self.store, model), 2)
        self.assertEqual(self.embed.status(self.store, model), {"model": model, "indexed": 2, "total": 2})
        before = StubEmbed.seen.count("/api/embed")
        self.assertEqual(self.embed.build(self.store, model), 0)  # nothing changed: nothing read again
        self.assertEqual(StubEmbed.seen.count("/api/embed"), before)
        note = self.store.get("b")
        note["summary"]["tldr"] = "Le voyage est annulé"
        self.store.save(note)
        self.assertEqual(self.embed.build(self.store, model), 1)

    def test_a_question_finds_the_note_whose_words_differ(self):
        self.embed.build(self.store, "qwen3-embedding:0.6b")
        results = self.embed.search(self.store, "cout et depense du projet")
        self.assertEqual([r["id"] for r in results][:1], ["a"])
        self.assertTrue(results[0]["hits"])
        results = self.embed.search(self.store, "quel hôtel et quel avion")
        self.assertEqual(results[0]["id"], "b")
        transcript = [h for h in results[0]["hits"] if h["where"] == "transcript"]
        self.assertTrue(transcript and transcript[0]["start"] == 0.0)

    def test_unrelated_questions_find_nothing(self):
        self.embed.build(self.store, "qwen3-embedding:0.6b")
        self.assertEqual(self.embed.search(self.store, "xyzzy plugh"), [])
        self.assertEqual(self.embed.search(self.store, ""), [])

    def test_deleted_notes_leave_the_index(self):
        model = "qwen3-embedding:0.6b"
        self.embed.build(self.store, model)
        self.store.save({"id": "z", "status": "done", "title": "Temp", "segments": [seg(0, "budget")], "summary": {"tldr": "budget"}})
        self.embed.build(self.store, model)
        self.store.delete("z")
        self.embed.build(self.store, model)
        self.assertFalse((self.embed._folder(model) / "z.json").exists())
        self.assertNotIn("z", [r["id"] for r in self.embed.search(self.store, "budget")])

    def test_it_works_without_numpy(self):
        self.embed.build(self.store, "qwen3-embedding:0.6b")
        with self.embed._lock:
            self.embed._cache.clear()
        saved = self.embed.np
        self.embed.np = None
        try:
            self.assertEqual(self.embed.search(self.store, "voyage en avion")[0]["id"], "b")
        finally:
            self.embed.np = saved
            with self.embed._lock:
                self.embed._cache.clear()

    def test_a_damaged_index_file_is_ignored(self):
        model = "qwen3-embedding:0.6b"
        self.embed.build(self.store, model)
        (self.embed._folder(model) / "a.json").write_text("{not json")
        with self.embed._lock:
            self.embed._cache.clear()
        self.assertEqual([r["id"] for r in self.embed.search(self.store, "voyage")], ["b"])
        self.assertEqual(self.embed.build(self.store, model), 1)  # and it is rebuilt

    def test_a_model_with_other_dimensions_does_not_mix_with_old_vectors(self):
        model = "qwen3-embedding:0.6b"
        self.embed.build(self.store, model)
        path = self.embed._folder(model) / "a.json"
        data = json.loads(path.read_text())
        data["dim"] = 3
        path.write_text(json.dumps(data))
        with self.embed._lock:
            self.embed._cache.clear()
        self.assertNotIn("a", [r["id"] for r in self.embed.search(self.store, "budget")])

    def test_chunks_group_the_transcript_and_keep_its_start(self):
        note = {"title": "T", "tags": ["x"], "summary": {"tldr": "S"}, "segments": [seg(i * 3, "mot " * 30) for i in range(10)]}
        items = self.embed.chunks(note)
        transcript = [i for i in items if i[0] == "transcript"]
        self.assertGreater(len(transcript), 1)
        self.assertEqual(transcript[0][1], 0.0)
        self.assertTrue(all(len(i[2]) <= self.embed.MAX_CHUNK for i in items))
        self.assertEqual(items[0][0], "title")

    def test_the_server_offers_the_search_and_the_catalog(self):
        from cairn import catalog, models

        self.assertEqual(catalog.EMBED_IDS, ("qwen3-embedding:0.6b", "bge-m3"))
        listing = models.listing(None)
        self.assertEqual([m["id"] for m in listing["embed"]], list(catalog.EMBED_IDS))
        first = listing["embed"][0]
        self.assertTrue(first["installed"] and first["selected"])
        self.assertFalse(listing["embed"][1]["installed"])
        self.assertEqual(models.select("embed", "qwen3-embedding:0.6b")["embed"], "qwen3-embedding:0.6b")
        with self.assertRaises(ValueError):
            models.select("embed", "bge-m3")  # not installed


if __name__ == "__main__":
    unittest.main()
