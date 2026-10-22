"""Offline storage, text imports, and study logic (independent of the UI)."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import random
import re
import unicodedata
import uuid


SEPARATORS = {"Tab": "\t", "Pipe (|)": "|", "Double colon (::)": "::",
              "Semicolon (;)": ";", "Dash ( - )": " - ", "Colon (:)": ":"}


@dataclass(frozen=True)
class Card:
    term: str
    definition: str
    category: str = ''
    explanation: str = ''
    question: bool = False
    options: tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.question) is not bool or not isinstance(self.options, (list, tuple)):
            raise ValueError('Invalid question format')
        if any(not isinstance(option, str) or not option.strip() for option in self.options):
            raise ValueError('Answer choices must be nonempty text')
        object.__setattr__(self, 'options', tuple(self.options))
        if self.options:
            if not self.question or not 2 <= len(self.options) <= 6:
                raise ValueError('Questions need between 2 and 6 choices, or no choices for typed answers')
            normalized = [normalize(option) for option in self.options]
            if len(set(normalized)) != len(normalized):
                raise ValueError('Answer choices must be distinct')
            if normalize(self.definition) not in normalized:
                raise ValueError('The correct answer must match one of the choices')

    @property
    def key(self) -> str:
        return hashlib.sha256(json.dumps([self.term, self.definition]).encode()).hexdigest()


def parse_text(text: str, separator: str | None = None, categorized: bool = False,
               explained: bool = False) -> list[Card]:
    """Parse one pair per line. Auto-detection chooses one delimiter per file."""
    if text.lstrip('\ufeff \r\n').startswith('# quizmax-questions'):
        return parse_questions(text)
    if explained and not categorized:
        raise ValueError('The explanation column requires the category column (which may be blank).')
    lines = [(n, line.strip(' \r')) for n, line in enumerate(text.lstrip('\ufeff').splitlines(), 1)
             if line.strip() and not line.lstrip().startswith('#')]
    if not lines:
        raise ValueError("The file has no cards. Add a term and definition on each line.")
    if separator is None:
        # Prefer the delimiter that explains the most rows; ties prefer tabs.
        separator = max(SEPARATORS.values(), key=lambda sep: sum(sep in line for _, line in lines))
    if not separator:
        raise ValueError("Choose a nonempty separator.")
    cards, seen, errors = [], set(), []
    for number, line in lines:
        parts = line.split(separator, 1)
        if explained:
            parts = line.split(separator, 3)
        elif categorized and len(parts) == 2:
            parts = [parts[0], *parts[1].rsplit(separator, 1)]
        if categorized and len(parts) != (4 if explained else 3):
            errors.append(str(number))
            continue
        if len(parts) < 2 or not all(part.strip() for part in parts[:2]):
            errors.append(str(number))
            continue
        card = Card(*(part.strip() for part in parts))
        if card.key not in seen:
            cards.append(card)
            seen.add(card.key)
    if errors:
        shown = ', '.join(errors[:12]) + ('…' if len(errors) > 12 else '')
        raise ValueError(f"Invalid card on line(s) {shown}. Each line needs a nonempty term, "
                         "a separator, and a nonempty definition. Choose the separator explicitly "
                         "if automatic detection picked the wrong one. With categories enabled, "
                         "include a third column; with explanations enabled, include a fourth. "
                         "Category and explanation may be blank. Nothing was imported.")
    return cards


def parse_questions(text: str) -> list[Card]:
    """Read Q:/A:/Choice: blocks, with a new Q: starting each question."""
    cards, fields, options = [], {}, []
    start = 1

    def finish():
        if not fields:
            return
        if not fields.get('q') or not fields.get('a'):
            raise ValueError(f'Question at line {start} needs nonempty Q: and A: fields.')
        try:
            cards.append(Card(fields['q'], fields['a'], fields.get('category', ''),
                              fields.get('explanation', ''), True, tuple(options)))
        except ValueError as exc:
            raise ValueError(f'Question at line {start}: {exc}') from exc

    for number, raw in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        label, sep, value = line.partition(':')
        label, value = label.lower().strip(), value.strip()
        if not sep or label not in ('q', 'a', 'choice', 'category', 'explanation'):
            raise ValueError(f'Invalid field on line {number}. Use Q:, A:, Choice:, Category:, or Explanation:.')
        if label == 'q':
            finish()
            fields, options, start = {}, [], number
        elif not fields:
            raise ValueError(f'Line {number}: start each question with Q:.')
        if label == 'choice':
            options.append(value)
        elif label in fields:
            raise ValueError(f'Duplicate {label} field on line {number}.')
        else:
            fields[label] = value
    finish()
    if not cards:
        raise ValueError('The file has no questions.')
    if len({card.key for card in cards}) != len(cards):
        raise ValueError('Duplicate question and answer pairs are not allowed.')
    return cards


def normalize(answer: str) -> str:
    """Ignore case and repeated whitespace; preserve meaningful punctuation."""
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', answer).strip()).casefold()


@dataclass
class StudySet:
    name: str
    cards: list[Card]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    progress: dict[str, dict[str, int]] = field(default_factory=dict)

    def scores(self, reverse: bool = False) -> dict[str, int]:
        return self.progress.setdefault('reverse' if reverse else 'forward', {})


class Library:
    def __init__(self, directory: Path):
        self.directory = directory
        self.path = directory / 'library.json'
        self.sets: list[StudySet] = []

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data['version'] != 1 or not isinstance(data['sets'], list):
                raise ValueError('Unsupported library format')
            loaded = []
            ids = set()
            for item in data['sets']:
                if not isinstance(item['name'], str) or not item['name'].strip():
                    raise ValueError('Invalid set name')
                if not isinstance(item['id'], str) or item['id'] in ids:
                    raise ValueError('Invalid set ID')
                ids.add(item['id'])
                cards = [Card(**c) for c in item['cards']]
                if not cards or any(not isinstance(v, str) or not v.strip()
                                    for c in cards for v in (c.term, c.definition)):
                    raise ValueError('Invalid cards')
                if any(not isinstance(c.category, str) for c in cards):
                    raise ValueError('Invalid category')
                if any(not isinstance(c.explanation, str) for c in cards):
                    raise ValueError('Invalid explanation')
                progress = item.get('progress', {})
                if not isinstance(progress, dict):
                    raise ValueError('Invalid progress')
                for direction, scores in progress.items():
                    if direction not in ('forward', 'reverse') or not isinstance(scores, dict):
                        raise ValueError('Invalid progress')
                    if any(not isinstance(k, str) or type(v) is not int or v not in (0, 1, 2)
                           for k, v in scores.items()):
                        raise ValueError('Invalid score')
                loaded.append(StudySet(item['name'], cards, item['id'], progress))
            self.sets = loaded
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Could not read {self.path}. Your file has been left untouched. "
                             f"Restore a valid library or move it aside before restarting. ({exc})") from exc

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        data = {'version': 1, 'sets': [
            {'id': s.id, 'name': s.name, 'cards': [vars(c) for c in s.cards], 'progress': s.progress}
            for s in self.sets]}
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, self.path)


class LearnSession:
    """Two consecutive correct answers master a card; misses go to the queue's end."""

    def __init__(self, study_set: StudySet, reverse: bool = False, rng=None):
        self.study_set = study_set
        self.reverse = reverse and not any(c.question for c in study_set.cards)
        self.rng = rng or random.Random()
        self.scores = study_set.scores(self.reverse)
        self.queue = [c for c in study_set.cards if self.scores.get(c.key, 0) < 2]
        self.rng.shuffle(self.queue)
        self.previous: tuple[Card, int] | None = None

    def sides(self, card: Card) -> tuple[str, str]:
        return (card.definition, card.term) if self.reverse else (card.term, card.definition)

    @property
    def current(self) -> Card | None:
        return self.queue[0] if self.queue else None

    @property
    def mastered(self) -> int:
        return sum(self.scores.get(c.key, 0) >= 2 for c in self.study_set.cards)

    def choices(self) -> list[str]:
        card = self.current
        if card is None:
            return []
        if card.question:
            options = list(card.options)
            self.rng.shuffle(options)
            return options
        if self.scores.get(card.key, 0) > 0:
            return []
        prompt, answer = self.sides(card)
        # Don't offer a second valid answer when several cards share a prompt.
        valid_answers = {normalize(self.sides(c)[1]) for c in self.study_set.cards
                         if normalize(self.sides(c)[0]) == normalize(prompt)}
        pool = {}
        for other in self.study_set.cards:
            if normalize(other.category) != normalize(card.category):
                continue
            value = self.sides(other)[1]
            if normalize(value) not in valid_answers:
                pool[normalize(value)] = value
        if not pool:
            return []
        options = self.rng.sample(list(pool.values()), min(3, len(pool))) + [answer]
        self.rng.shuffle(options)
        return options

    def submit(self, answer: str, force_wrong: bool = False) -> bool:
        if self.current is None:
            raise ValueError('This session is complete.')
        card = self.queue.pop(0)
        old = self.scores.get(card.key, 0)
        correct = not force_wrong and normalize(answer) == normalize(self.sides(card)[1])
        self.previous = (card, old)
        self.scores[card.key] = min(2, old + 1) if correct else 0
        if self.scores[card.key] < 2:
            self.queue.append(card)
        return correct

    def accept_previous(self) -> None:
        """Allow the learner to accept a synonym after seeing the expected answer."""
        if self.previous is None:
            return
        card, old = self.previous
        self.scores[card.key] = min(2, old + 1)
        self.queue = [c for c in self.queue if c.key != card.key]
        if self.scores[card.key] < 2:
            self.queue.append(card)
        self.previous = None
