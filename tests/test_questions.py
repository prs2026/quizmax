from pathlib import Path
import tempfile
import unittest

from quizmax.core import Card, LearnSession, Library, StudySet, parse_questions, parse_text


QUESTION = '''# quizmax-questions
Q: Is HF a strong acid?
A: No
Choice: Yes
Choice: No
Category: Acids
Explanation: It only partially ionizes.
'''


class QuestionTests(unittest.TestCase):
    def test_import_detected_with_default_column_settings(self):
        cards = parse_text(QUESTION, categorized=True, explained=True)
        self.assertEqual(cards, [Card('Is HF a strong acid?', 'No', 'Acids',
                                     'It only partially ionizes.', True, ('Yes', 'No'))])

    def test_explicit_choices_remain_on_second_attempt(self):
        cards = parse_questions(QUESTION)
        cards.append(Card('Other question', 'Unrelated answer', 'Acids'))
        session = LearnSession(StudySet('Questions', cards), reverse=True)
        self.assertFalse(session.reverse)
        session.queue = [cards[0]]
        self.assertEqual(set(session.choices()), {'Yes', 'No'})
        self.assertTrue(session.submit('no'))
        self.assertEqual(set(session.choices()), {'Yes', 'No'})
        self.assertFalse(session.submit('Yes'))
        self.assertTrue(session.submit('No'))
        self.assertTrue(session.submit('No'))
        self.assertIsNone(session.current)

    def test_typed_questions_do_not_borrow_choices(self):
        cards = parse_questions('Q: Ratio?\nA: 1:2\nQ: Other ratio?\nA: 1:3')
        session = LearnSession(StudySet('Ratios', cards))
        self.assertEqual(session.choices(), [])
        self.assertTrue(session.submit(session.current.definition))

    def test_invalid_questions_rejected(self):
        for text in ('Q: Missing answer', 'A: No', 'Q: X\nA: Yes\nChoice: No\nChoice: Maybe',
                     'Q: X\nA: No\nChoice: No\nChoice: no', 'Q: X\nA: No\nChoice: No',
                     'Q: X\nA: No\nA: Yes', 'Q: X\nA: No\nUnknown: Y',
                     'Q: X\nA: No\nQ: X\nA: No', '# empty'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_questions(text)

    def test_question_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Library(Path(directory))
            library.sets = [StudySet('Questions', parse_questions(QUESTION))]
            library.save()
            loaded = Library(Path(directory))
            loaded.load()
            self.assertEqual(loaded.sets, library.sets)

    def test_example_imports(self):
        cards = parse_text(Path('examples/chemistry_questions.txt').read_text(encoding='utf-8'))
        self.assertEqual(len(cards), 4)
        self.assertTrue(all(c.question and c.explanation for c in cards))


if __name__ == '__main__':
    unittest.main()
