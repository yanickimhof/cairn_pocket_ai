"""Searching the notes by words and by meaning: a sentence is not a list of words that must all be there."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cairn import config, embed, search


def write(folder, note_id, title, text, date="2026-11-01"):
    note = {"id": note_id, "title": title, "date": date, "status": "done", "summary": {"tldr": ""}, "clean": text}
    config.write_json(folder / (note_id + ".json"), note)


class WordSearchTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        write(self.folder, "a", "Ventilation Alpenda", "On a parlé de la ventilation et du budget de la maison.")
        write(self.folder, "b", "Réunion SICPA", "Premier jour chez SICPA, visite des départements.", "2026-11-02")

    def ids(self, query):
        return [r["id"] for r in search.find(self.folder, query)]

    def test_filler_words_do_not_have_to_be_found(self):
        self.assertEqual(search.terms("le budget de la maison"), ["budget", "maison"])
        self.assertEqual(self.ids("le budget de la maison"), ["a"])
        self.assertEqual(search.terms("le de la"), ["le", "de", "la"])  # only filler: they are searched as they are

    def test_a_plural_finds_the_singular(self):
        self.assertEqual(self.ids("ventilations"), ["a"])
        self.assertEqual(self.ids("ventilation"), ["a"])
        self.assertEqual(search.terms("jours"), ["jour"])
        self.assertEqual(search.terms("bus"), ["bus"])  # a short word keeps its letter

    def test_when_no_note_has_every_word_the_notes_with_part_of_them_come(self):
        self.assertEqual(self.ids("budget voiture"), [])  # two words: both are needed
        self.assertEqual(self.ids("voiture bateau avion"), [])  # none of the words
        self.assertEqual(self.ids("reunion sicpa toiture isolation"), ["b"])

    def test_every_word_still_ranks_first(self):
        write(self.folder, "c", "Budget", "Le budget de la ventilation de la maison.", "2026-11-03")
        found = self.ids("budget ventilation")
        self.assertEqual(set(found), {"a", "c"})

    def test_nothing_found_stays_nothing(self):
        self.assertEqual(self.ids("dragon pirate"), [])


class MeaningSearchTest(unittest.TestCase):
    def test_a_question_is_read_with_its_instruction_by_the_models_that_want_it(self):
        self.assertTrue(embed._prefix("qwen3-embedding:0.6b").startswith("Instruct:"))
        self.assertEqual(embed._prefix("nomic-embed-text"), "")

    def test_the_question_that_is_sent_carries_the_instruction(self):
        sent = []

        def fake(model, texts):
            sent.extend(texts)
            return [[1.0, 0.0] for _ in texts]

        store = mock.Mock()
        store.slim.return_value = []
        with mock.patch.object(embed, "embed", side_effect=fake):
            embed.search(store, "budget", "qwen3-embedding:0.6b")
        self.assertTrue(sent[0].endswith("Query: budget"))


if __name__ == "__main__":
    unittest.main()
