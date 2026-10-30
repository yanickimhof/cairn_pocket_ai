"""Correcting a line by hand, the rules it teaches, and the list of names worth checking."""

import copy
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cairn import vocab, vocabcheck  # noqa: E402


def seg(start, text, logprob=-0.2, **extra):
    return dict({"start": float(start), "end": float(start) + 3, "text": text, "logprob": logprob, "compression": 1.2, "no_speech": 0.0}, **extra)


class RuleFromEditTest(unittest.TestCase):
    def test_only_the_changed_words_become_a_rule(self):
        rules = vocab.rule_from_edit("On a vu l'association Brant à Bordeaux", "On a vu l'association Brandt à Bordeaux")
        self.assertEqual(len(rules), 1)
        self.assertEqual((rules[0]["wrong"], rules[0]["right"]), ("Brant", "Brandt"))

    def test_a_long_word_stands_alone_a_short_one_gets_a_context(self):
        long = vocab.rule_from_edit("Le projet Brantne avance", "Le projet Brandt avance")[0]
        self.assertEqual(long["context"], [])
        short = vocab.rule_from_edit("we meet at five in Geneva", "we meet at nine in Geneva")[0]
        self.assertEqual((short["wrong"], short["right"]), ("five", "nine"))
        self.assertTrue(short["context"] and len(short["context"]) <= 2)
        self.assertNotIn("five", short["context"])

    def test_a_line_without_a_difference_or_with_only_added_words_gives_no_rule(self):
        self.assertEqual(vocab.rule_from_edit("same words here", "same words here"), [])
        self.assertEqual(vocab.rule_from_edit("it is late", "it is very late"), [])
        self.assertEqual(vocab.rule_from_edit("uh we start", "we start"), [])

    def test_several_changes_give_several_rules(self):
        rules = vocab.rule_from_edit("Brantne signe avec Zelda hier", "Brandt signe avec Zelda demain")
        self.assertEqual([(r["wrong"], r["right"]) for r in rules], [("Brantne", "Brandt"), ("hier", "demain")])

    def test_punctuation_is_not_part_of_the_words(self):
        rule = vocab.rule_from_edit("Merci, Brantne.", "Merci, Brandt.")[0]
        self.assertEqual((rule["wrong"], rule["right"]), ("Brantne", "Brandt"))

    def test_characters_of_the_rule_syntax_never_end_up_in_a_rule(self):
        self.assertEqual(vocab.rule_from_edit("see x|y now", "see z now"), [])
        self.assertEqual(vocab.rule_from_edit("see x=>y now", "see z now"), [])
        self.assertEqual(vocab.rule_from_edit("see x,y now", "see z now"), [])
        for rule in vocab.rule_from_edit("voir Brantne ici", "voir Brandt ici"):
            self.assertEqual(vocab.parse(vocab.rule_line(rule)), [vocab.rule_line(rule)])

    def test_the_line_of_a_rule_is_understood_by_the_vocabulary(self):
        rule = vocab.rule_from_edit("we meet at five in Geneva", "we meet at nine in Geneva")[0]
        line = vocab.rule_line(rule)
        terms = vocab.add_entries([], [line])
        self.assertEqual(vocab.fix_text("we meet at five in Geneva", terms)[0], "we meet at nine in Geneva")
        self.assertEqual(vocab.fix_text("it was five", terms)[0], "it was five")  # the context is not there
        self.assertEqual(vocab.add_entries(terms, [line]), terms)  # never twice


class ManualEditsStayTest(unittest.TestCase):
    def test_apply_leaves_a_corrected_line_alone_and_still_fixes_the_others(self):
        segments = [seg(0, "Brant arrive", orig="Brant arrive", edit=True), seg(3, "Brant part")]
        segments[0]["text"] = "Notre Brant arrive"
        vocab.apply(segments, ["Brant => Brandt"])
        self.assertEqual(segments[0]["text"], "Notre Brant arrive")
        self.assertEqual(segments[1]["text"], "Brandt part")
        vocab.apply(segments, [])
        self.assertEqual(segments[0]["text"], "Notre Brant arrive")
        self.assertEqual(segments[1]["text"], "Brant part")


class CheckListTest(unittest.TestCase):
    def notes(self):
        return [
            {"id": "a", "status": "done", "title": "A", "segments": [
                seg(0, "On travaille avec Brandt sur le projet."), seg(3, "Nous voyons Brant demain."),
                seg(6, "Bonjour Marc, avec Xylophia.", logprob=-1.5)]},
            {"id": "b", "status": "done", "title": "B", "segments": [seg(0, "Dis à Brandt que Marc vient."), seg(3, "Avec Brandt aussi.")]},
            {"id": "c", "status": "waiting", "title": "C", "segments": [seg(0, "Avec Brantne et Brantne.")]},
        ]

    def test_variants_and_unsure_names_are_listed(self):
        items = vocabcheck.candidates(self.notes(), [])
        by = {i["suggest"]: i for i in items}
        self.assertEqual(by["Brandt"]["reason"], "variants")
        self.assertEqual([f["text"] for f in by["Brandt"]["forms"]], ["Brandt", "Brant"])
        self.assertEqual(by["Brandt"]["forms"][0]["count"], 3)
        self.assertEqual(by["Xylophia"]["reason"], "doubtful")
        self.assertNotIn("Marc", by)  # said clearly and always the same way
        self.assertEqual(items[0]["reason"], "variants")  # variants come first
        self.assertTrue(all(e["text"] for i in items for e in i["examples"]))

    def test_notes_not_finished_and_corrected_lines_are_not_looked_at(self):
        items = vocabcheck.candidates(self.notes(), [])
        self.assertFalse(any("Brantne" in f["text"] for i in items for f in i["forms"]))
        notes = self.notes()
        notes[0]["segments"][2]["edit"] = True
        self.assertFalse(any(i["suggest"] == "Xylophia" for i in vocabcheck.candidates(notes, [])))

    def test_what_the_vocabulary_already_knows_is_not_listed_again(self):
        items = vocabcheck.candidates(self.notes(), ["Xylophia"])
        self.assertFalse(any(i["suggest"] == "Xylophia" for i in items))
        items = vocabcheck.candidates(self.notes(), ["Brandt"])
        brandt = [i for i in items if i["reason"] == "variants"][0]
        self.assertEqual(brandt["suggest"], "Brandt")  # the known spelling is the one proposed

    def test_ignored_names_stay_out(self):
        first = vocabcheck.candidates(self.notes(), [])
        keys = [i["key"] for i in first]
        again = vocabcheck.candidates(self.notes(), [], ignored=keys)
        self.assertEqual(again, [])

    def test_sentence_starts_and_ordinary_words_are_not_names(self):
        notes = [{"id": "x", "status": "done", "segments": [seg(0, "Bonjour tout le monde. Alors on commence. Lundi nous voyons Janvier."), seg(3, "Bonjour encore. Alors on finit.")]}]
        self.assertEqual(vocabcheck.candidates(notes, []), [])

    def test_other_forms_of_one_word_and_two_equal_names_are_not_misheard_names(self):
        def note(text, i):
            return {"id": "n%d" % i, "status": "done", "segments": [seg(0, "Hier nous parlons de %s" % text)]}

        texts = ["Europe", "Europe", "European", "European", "Adrian's", "Adrian", "Adrian", "States", "State", "State"]
        notes = [note(t, i) for i, t in enumerate(texts)]
        self.assertEqual(vocabcheck.candidates(notes, []), [])  # Europe/European, Adrian's, State/States: forms of the same word
        balanced = [note(t, i) for i, t in enumerate(["Anna", "Anna", "Anne", "Anne"])]
        self.assertEqual(vocabcheck.candidates(balanced, []), [])  # said as often: two people
        stray = [note(t, i) for i, t in enumerate(["Thomas", "Thomas", "Thomas", "Tomas"])]
        self.assertEqual([[f["text"] for f in i["forms"]] for i in vocabcheck.candidates(stray, [])], [["Thomas", "Tomas"]])

    def test_the_list_is_bounded(self):
        words = ["Zorbak", "Quimby", "Fennick", "Tarlow", "Vondra", "Hexler", "Mirkwood", "Plansky", "Dornel", "Yaskov"]
        segments = [seg(i * 3, "Hier avec %s et %s ici." % (words[i % 10], words[(i + 3) % 10]), logprob=-1.5) for i in range(30)]
        items = vocabcheck.candidates([{"id": "n", "status": "done", "segments": segments}], [], limit=5)
        self.assertLessEqual(len(items), 5)


class Client:
    def __init__(self, app):
        self.app = app

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=30)
        headers = {"Host": "127.0.0.1:%d" % self.app.port, "Cookie": "cairn_session=" + self.app.token}
        if method == "POST":
            headers.update({"Content-Type": "application/json", "X-Cairn": "1"})
        conn.request(method, path, json.dumps(body or {}) if method == "POST" else None, headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw)
        except ValueError:
            return resp.status, raw.decode("utf-8", "replace")


class AssistantApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        os.environ.update(CAIRN_HOME=str(root / "Cairn"), CAIRN_POCKET_DIR=str(root / "none"), CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b",
                          OLLAMA_HOST="127.0.0.1:9", CAIRN_WHISPER_MODEL=str(root))
        from cairn import server

        cls.app, cls.httpd = server.make_server(18810)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.c = Client(cls.app)
        cls.app.check_wait = 0.0
        cls.started = []
        cls.app.jobs.start_vocab = lambda ids, force=True: cls.started.append((list(ids), force))  # the model is not needed here
        cls.base = [
            {"id": "a", "status": "done", "title": "A", "date": "2026-10-01T10:00:00", "lang": "fr", "vocab_key": "",
             "summary": {"title": "A", "tldr": "x"},
             "segments": [seg(0, "On a vu l'association Brant à Bordeaux"), seg(3, "Brant est contente"), seg(6, "Fin de la réunion")],
             "clean": ""},
            {"id": "b", "status": "done", "title": "B", "date": "2026-10-02T10:00:00", "lang": "fr", "vocab_key": "",
             "summary": {"title": "B", "tldr": "y"}, "segments": [seg(0, "Avec Brandt demain"), seg(3, "Et Brant aussi")], "clean": ""},
        ]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        from cairn import config

        config.save_settings({"vocabulary": [], "vocab_ignored": []})
        self.started.clear()
        for note in self.base:
            self.app.store.save(copy.deepcopy(note))

    def segments(self, note_id="a"):
        return self.app.store.get(note_id)["segments"]

    def test_here_changes_one_line_and_nothing_else(self):
        status, data = self.c.call("POST", "/api/note/a/segment", {"index": 0, "text": "On a vu l'association Brandt à Bordeaux", "scope": "here"})
        self.assertEqual((status, data["rules"], data["updating"]), (200, [], 0))
        segs = self.segments()
        self.assertEqual(segs[0]["text"], "On a vu l'association Brandt à Bordeaux")
        self.assertEqual(segs[0]["orig"], "On a vu l'association Brant à Bordeaux")
        self.assertTrue(segs[0]["edit"])
        self.assertEqual(segs[1]["text"], "Brant est contente")
        self.assertIn("Brandt à Bordeaux", self.app.store.get("a")["clean"])
        self.assertEqual(config_vocab(), [])
        self.assertEqual(self.started, [])

    def test_always_teaches_a_rule_and_writes_the_other_notes_again(self):
        status, data = self.c.call("POST", "/api/note/a/segment", {"index": 0, "text": "On a vu l'association Brandt à Bordeaux", "scope": "always"})
        self.assertEqual(status, 200)
        self.assertEqual(len(data["rules"]), 1)
        self.assertTrue(data["rules"][0].startswith("Brant => Brandt"))
        self.assertEqual(config_vocab(), data["rules"])
        self.assertTrue(self.started)  # the notes the rule changes are written again
        ids = self.started[0][0]
        self.assertIn("b", ids)
        self.assertEqual(self.segments()[0]["text"], "On a vu l'association Brandt à Bordeaux")

    def test_the_same_rule_is_not_added_twice(self):
        for _ in range(2):
            self.c.call("POST", "/api/note/a/segment", {"index": 0, "text": "On a vu l'association Brandt à Bordeaux", "scope": "always"})
        self.assertEqual(len(config_vocab()), 1)

    def test_putting_the_original_back_clears_the_correction(self):
        self.c.call("POST", "/api/note/a/segment", {"index": 2, "text": "Fin de la séance", "scope": "here"})
        self.assertTrue(self.segments()[2].get("edit"))
        self.c.call("POST", "/api/note/a/segment", {"index": 2, "text": "Fin de la réunion", "scope": "here"})
        restored = self.segments()[2]
        self.assertEqual(restored["text"], "Fin de la réunion")
        self.assertNotIn("edit", restored)
        self.assertNotIn("orig", restored)

    def test_the_rule_comes_from_what_the_engine_wrote_not_from_a_corrected_text(self):
        self.c.call("POST", "/api/note/a/segment", {"index": 0, "text": "On a vu l'association Brandt à Bordeaux", "scope": "here"})
        status, data = self.c.call("POST", "/api/note/a/segment", {"index": 0, "text": "On a vu l'association Brandt à Bordeaux-les-Bains", "scope": "always"})
        self.assertEqual(status, 200)
        self.assertTrue(any(r.startswith("Brant => Brandt") for r in data["rules"]) or any(r.startswith("Bordeaux") for r in data["rules"]), data)

    def test_bad_requests_are_refused_and_change_nothing(self):
        before = self.segments()
        for body in ({"index": 9, "text": "x", "scope": "here"}, {"index": -1, "text": "x", "scope": "here"}, {"index": "0", "text": "x", "scope": "here"},
                     {"index": True, "text": "x", "scope": "here"}, {"index": 0, "text": "", "scope": "here"}, {"index": 0, "text": "x" * 2001, "scope": "here"},
                     {"index": 0, "text": "x", "scope": "everywhere"}, {"index": 0, "text": "x"}):
            with self.subTest(body=body):
                self.assertEqual(self.c.call("POST", "/api/note/a/segment", body)[0], 400)
        self.assertEqual(self.c.call("POST", "/api/note/nope/segment", {"index": 0, "text": "x", "scope": "here"})[0], 404)
        self.assertEqual(self.c.call("POST", "/api/note/a/segment", {"index": 0, "text": "On a vu l'association Brant à Bordeaux", "scope": "always"})[0], 400)  # no change, no rule
        self.assertEqual(self.segments(), before)

    def test_the_list_the_badge_and_the_answer(self):
        _, data = self.c.call("GET", "/api/vocabulary/check")
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["suggest"], "Brant")
        self.assertEqual({f["text"] for f in item["forms"]}, {"Brant", "Brandt"})
        status, answer = self.c.call("POST", "/api/vocabulary/check/apply", {"key": item["key"], "right": "Brandt"})
        self.assertEqual(status, 200)
        self.assertEqual(config_vocab(), ["Brant => Brandt"])
        self.assertTrue(self.started)
        _, data = self.c.call("GET", "/api/vocabulary/check")
        self.assertEqual(data["items"], [])  # a name a rule already rewrites is no longer proposed
        self.assertEqual(self.c.call("POST", "/api/vocabulary/check/apply", {"key": "nothing", "right": "X"})[0], 404)
        self.assertEqual(self.c.call("POST", "/api/vocabulary/check/apply", {"key": item["key"], "right": "A|B"})[0], 400)

    def test_a_context_can_be_given(self):
        _, data = self.c.call("GET", "/api/vocabulary/check")
        key = data["items"][0]["key"]
        self.c.call("POST", "/api/vocabulary/check/apply", {"key": key, "right": "Brandt", "context": "Bordeaux, association"})
        self.assertEqual(config_vocab(), ["Brant => Brandt | Bordeaux, association"])

    def test_ignoring_hides_the_name(self):
        _, data = self.c.call("GET", "/api/vocabulary/check")
        self.c.call("POST", "/api/vocabulary/check/ignore", {"key": data["items"][0]["key"]})
        _, again = self.c.call("GET", "/api/vocabulary/check")
        self.assertEqual(again["items"], [])
        self.assertEqual(self.c.call("POST", "/api/vocabulary/check/ignore", {"key": ""})[0], 400)

    def test_the_badge_follows_the_notes(self):
        deadline = time.time() + 5
        count = -1
        while time.time() < deadline:
            count = self.c.call("GET", "/api/state?list=0")[1]["totals"]["vocab_check"]
            if count == 1:
                break
            time.sleep(0.1)
        self.assertEqual(count, 1)


def config_vocab():
    from cairn import config

    return config.load_settings()["vocabulary"]


if __name__ == "__main__":
    unittest.main()
