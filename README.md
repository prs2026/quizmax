# Quizmax

A Python desktop app for practicing flashcards offline. No account, server, internet connection, or pip packages are needed.

## Run

Install Python 3.10 or newer with Tkinter, then run from this repository:

```sh
python main.py
```

You can also use `python -m quizmax`. Windows and macOS Python installers generally include Tkinter. On Debian/Ubuntu, install `python3-tk` if it is missing. A graphical desktop is required.

## Import a set

Click **Import .txt set**, select a UTF-8 text file, and name the set. Category and explanation columns are enabled by default. The default format is:

```text
Is HF a strong acid? | No | Acid strength | HF only partially ionizes in water.
What is the charge of nitrate? | -1 | Polyatomic ions | Nitrate is NO3-, with a net charge of -1.
```

The columns are **question | answer | category | explanation**. Category and explanation may be blank, but their separators must still be present. Explanations appear after a Learn answer (correct, incorrect, or skipped) and on the revealed side of flashcards, never in answer choices. Explanation changes preserve existing progress; changing the answer changes the card's study identity.

For a two-column file, uncheck both column options. Put one term and definition on each line:

```text
bonjour | hello
merci | thank you
au revoir | goodbye
```

Tabs (including Quizlet text exports), pipes (`|`), double colons (`::`), semicolons (`;`), spaced dashes (` - `), and colons (`:`) are supported. Auto-detection picks the separator present on the most lines; choose it explicitly for ambiguous files. In four-column mode, the first three separators split the fields, and extra separators belong to the explanation. In two-column mode, only the first separator splits the card. Multiline fields are not supported.

Blank lines and lines beginning with `#` are ignored. Exact duplicate pairs are collapsed. Invalid lines are reported with line numbers and the entire import is rejected so cards are never silently lost. Try `examples/biology.txt` to get started.

## Practice

### Categories / answer families

Click **Edit categories** in the sidebar to assign categories to existing cards. Select multiple cards with Ctrl/Shift and apply a category to all of them. Changes are saved immediately and preserve Learn progress. A blank category means **Uncategorized**.

You can also import categories without explanations: leave **Third column is category** enabled and uncheck **Fourth column is explanation**, then use:

```text
cat | gato | Animals
dog | perro | Animals
red | rojo | Colors
blue | azul | Colors
```

In this three-column mode, the first separator ends the term and the last separator starts the category. All rows need a third column, which may be blank. Leave both column options off for existing two-column files. See `examples/categories.txt`. The chemistry set `chem1210_flashcards_quizlet.txt` uses all four columns and imports with the default options.

Learn only offers answers from the current card's category, including when studying definition first. Category names ignore case and extra whitespace. Uncategorized cards draw answers only from other uncategorized cards. If a category has no distinct wrong answers, Learn uses typed recall instead of offering unrelated answers. Small categories offer fewer choices.

- **Flashcards:** click a card or press Space to flip it. Use Previous/Next or the arrow keys to browse. Shuffle changes the order for this visit.
- **Learn:** unlearned cards start with multiple choice when distinct wrong answers are available, then move to typed recall. Two consecutive correct answers master a card. A miss resets its streak and puts it at the end of the practice queue. A one-card set uses typed recall throughout.
- Answers ignore case and extra whitespace. Punctuation and accents matter. Use **Accept my answer** after a miss to credit a valid synonym or typo at your discretion.
- Press Enter to check a typed answer or continue after feedback. **I don’t know** reveals the answer and schedules another attempt.
- **Definition first** swaps the question and answer. Learn progress is saved separately for each direction.
- Reset Learn progress to practice a mastered set again. Rename and delete sets in the sidebar; deleting never changes your source text file.

## Local data

Imported cards and Learn progress are saved after each change to `~/.quizmax/library.json` (on Windows, `%USERPROFILE%\.quizmax\library.json`). Original text files are no longer needed after import. Back up or copy this JSON file to move your library between computers.

For a portable library, run:

```sh
python main.py --data-dir .quizmax
```

Run only one instance per data directory at a time. Saves replace the library file atomically. If the library is malformed, the app reports the error and leaves it untouched; restore a backup or move the file aside to start fresh.

## Verify

```sh
python -m unittest discover -s tests -v
```

Quizmax is an independent study app, not affiliated with Quizlet. Its Learn mode uses the transparent practice rules described above.
