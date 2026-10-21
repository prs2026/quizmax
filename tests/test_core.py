import json
from pathlib import Path
import random
import tempfile
import unittest

from quizmax.core import Card, LearnSession, Library, StudySet, parse_text


class ImportTests(unittest.TestCase):
    def test_four_columns(self):
        self.assertEqual(parse_text('Q | A | Family | Why | more detail', '|', True, True),
                         [Card('Q', 'A', 'Family', 'Why | more detail')])
        self.assertEqual(parse_text('Q\tA\t\t', '\t', True, True), [Card('Q', 'A')])
        with self.assertRaises(ValueError):
            parse_text('Q | A | Family', '|', True, True)
        with self.assertRaises(ValueError):
            parse_text('Q | A | Family | Why', '|', False, True)

    def test_category_import(self):
        self.assertEqual(parse_text('cat | gato | Animals\nred | rojo | Colors', '|', True),
                         [Card('cat', 'gato', 'Animals'), Card('red', 'rojo', 'Colors')])
        self.assertEqual(parse_text('cat\tgato\t', '\t', True), [Card('cat', 'gato')])
        self.assertEqual(parse_text('a | b | c | Family', '|', True), [Card('a', 'b | c', 'Family')])
        with self.assertRaises(ValueError):
            parse_text('cat | gato', '|', True)

    def test_supported_separators(self):
        for separator in ('\t', '|', '::', ';', ' - ', ':'):
            with self.subTest(separator=separator):
                self.assertEqual(parse_text(f'one{separator}uno\ntwo{separator}dos'),
                                 [Card('one', 'uno'), Card('two', 'dos')])

    def test_bom_comments_duplicates_and_embedded_separator(self):
        self.assertEqual(parse_text('\ufeff# heading\n\na | b | c\na | b | c\n'), [Card('a', 'b | c')])

    def test_bad_line_rejects_whole_import(self):
        for text in ('good | yes\nbroken', 'good | yes\nmissing |', ' | missing'):
            with self.assertRaisesRegex(ValueError, 'line'):
                parse_text(text, '|')

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            parse_text('# only a comment\n')

    def test_explicit_separator_resolves_ambiguity(self):
        self.assertEqual(parse_text('a: b | c: d', '|'), [Card('a: b', 'c: d')])


class LearnTests(unittest.TestCase):
    def test_choices_stay_in_category_in_both_directions(self):
        cards = [Card('cat', 'gato', 'Animals'), Card('dog', 'perro', ' animals '),
                 Card('red', 'rojo', 'Colors'), Card('blue', 'azul', 'Colors'),
                 Card('one', 'uno'), Card('two', 'dos'), Card('solo', 'alone', 'Single')]
        for reverse in (False, True):
            session = LearnSession(StudySet('Mixed', cards), reverse)
            for card, partner in ((cards[0], cards[1]), (cards[2], cards[3]), (cards[4], cards[5])):
                session.queue = [card]
                self.assertEqual(set(session.choices()), {session.sides(card)[1], session.sides(partner)[1]})
            session.queue = [cards[-1]]
            self.assertEqual(session.choices(), [])

    def test_category_changes_preserve_progress_key(self):
        self.assertEqual(Card('cat', 'gato').key, Card('cat', 'gato', 'Animals').key)
        self.assertEqual(Card('cat', 'gato').key, Card('cat', 'gato', 'Animals', 'Explanation').key)

    def setUp(self):
        self.study_set = StudySet('Numbers', [Card('one', 'uno'), Card('two', 'dos'), Card('three', 'tres')])
        self.session = LearnSession(self.study_set, rng=random.Random(3))

    def test_mastery_requires_two_and_changes_question_type(self):
        while self.session.current:
            card = self.session.current
            score = self.session.scores.get(card.key, 0)
            self.assertEqual(bool(self.session.choices()), score == 0)
            self.assertTrue(self.session.submit('  ' + card.definition.upper() + '  '))
        self.assertEqual(self.session.mastered, 3)
        self.assertIsNone(LearnSession(self.study_set).current)

    def test_miss_resets_and_requeues(self):
        card = self.session.current
        self.session.scores[card.key] = 1
        self.assertFalse(self.session.submit('wrong'))
        self.assertEqual(self.session.scores[card.key], 0)
        self.assertEqual(self.session.queue[-1], card)
        self.assertNotEqual(self.session.current, card)

    def test_override_restores_streak_once(self):
        card = self.session.current
        self.session.scores[card.key] = 1
        self.session.submit('synonym')
        self.session.accept_previous()
        self.session.accept_previous()
        self.assertEqual(self.session.scores[card.key], 2)
        self.assertNotIn(card, self.session.queue)

    def test_reverse_is_independent(self):
        reverse = LearnSession(self.study_set, reverse=True)
        card = reverse.current
        self.assertEqual(reverse.sides(card), (card.definition, card.term))
        reverse.submit(card.term)
        self.assertEqual(self.session.scores, {})

    def test_one_card_and_skip(self):
        session = LearnSession(StudySet('Single', [Card('A', 'B')]))
        self.assertEqual(session.choices(), [])
        self.assertFalse(session.submit('B', force_wrong=True))
        self.assertEqual(session.mastered, 0)

    def test_duplicate_prompts_do_not_create_ambiguous_choices(self):
        session = LearnSession(StudySet('Ambiguous', [Card('A', 'B'), Card('A', 'C')]))
        self.assertEqual(session.choices(), [])


class StorageTests(unittest.TestCase):
    def test_explanation_storage_and_legacy_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Library(Path(directory))
            library.sets.append(StudySet('Explained', [Card('Q', 'A', 'Family', 'Because')]))
            library.save()
            library.load()
            self.assertEqual(library.sets[0].cards[0].explanation, 'Because')
            data = json.loads(library.path.read_text())
            del data['sets'][0]['cards'][0]['explanation']
            library.path.write_text(json.dumps(data))
            library.load()
            self.assertEqual(library.sets[0].cards[0].explanation, '')
            data['sets'][0]['cards'][0]['explanation'] = 42
            library.path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                library.load()

    def test_categories_and_legacy_library(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Library(Path(directory))
            library.sets.append(StudySet('Animals', [Card('cat', 'gato', 'Animals')]))
            library.save()
            library.load()
            self.assertEqual(library.sets[0].cards[0].category, 'Animals')
            data = json.loads(library.path.read_text())
            del data['sets'][0]['cards'][0]['category']
            library.path.write_text(json.dumps(data))
            library.load()
            self.assertEqual(library.sets[0].cards[0].category, '')
            data['sets'][0]['cards'][0]['category'] = []
            library.path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                library.load()

    def test_round_trip_unicode_and_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Library(Path(directory))
            study_set = StudySet('Français', [Card('été', 'summer')])
            study_set.scores()[study_set.cards[0].key] = 1
            library.sets.append(study_set)
            library.save()
            loaded = Library(Path(directory))
            loaded.load()
            self.assertEqual(loaded.sets, library.sets)
            self.assertFalse(library.path.with_suffix('.tmp').exists())

    def test_corrupt_library_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Library(Path(directory))
            for content in ('{broken', json.dumps({'version': 999, 'sets': []}),
                            json.dumps({'version': 1, 'sets': [{'id': 'x', 'name': 'Empty', 'cards': []}]})):
                library.path.write_text(content)
                with self.assertRaises(ValueError):
                    library.load()
                self.assertEqual(library.path.read_text(), content)


if __name__ == '__main__':
    unittest.main()
