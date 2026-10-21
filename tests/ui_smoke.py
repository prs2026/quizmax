"""Optional desktop smoke test: python -m tests.ui_smoke (requires a display)."""

from pathlib import Path
from dataclasses import replace
import tempfile
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch

from quizmax.app import App
from quizmax.core import Library, StudySet, parse_text


def main():
    with tempfile.TemporaryDirectory() as directory:
        library = Library(Path(directory))
        library.sets.append(StudySet('Biology', parse_text(Path('examples/biology.txt').read_text())))
        library.sets[0].cards = [replace(c, explanation='Explanation smoke marker') for c in library.sets[0].cards]
        app = App(library)
        try:
            app.update()
            app.set_list.selection_set(0)
            app.select_set()
            app.update()
            app.edit_categories()
            dialog = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))

            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)

            def visible_text():
                return '\n'.join(w.get('1.0', 'end') for w in descendants(app.body) if isinstance(w, tk.Text))

            widgets = list(descendants(dialog))
            table = next(w for w in widgets if isinstance(w, ttk.Treeview))
            category = next(w for w in widgets if isinstance(w, ttk.Combobox))
            table.selection_set('0', '1')
            category.set('Structures')
            next(w for w in widgets if isinstance(w, ttk.Button)
                 and w.cget('text') == 'Apply to selected cards').invoke()
            assert all(c.category == 'Structures' for c in app.selected.cards[:2])
            dialog.destroy()
            app.update()
            app.flip()
            assert app.flipped
            assert 'Explanation smoke marker' in visible_text()
            app.navigate(1)
            assert app.position == 1 and not app.flipped
            assert 'Explanation smoke marker' not in visible_text()
            app.shuffle()
            app.set_mode('Learn')
            app.update()
            assert 'Explanation smoke marker' not in visible_text()
            app.submit('incorrect')
            assert app.answered
            assert 'Explanation smoke marker' in visible_text()
            app.accept_answer()
            while app.session.current:
                app.submit(app.session.sides(app.session.current)[1])
                assert 'Explanation smoke marker' in visible_text()
                app.update()
                app.render()
            assert app.session.mastered == len(app.selected.cards)
            app.update()
            app.reverse.set(True)
            app.direction_changed()
            assert app.session.mastered == 0
            app.submit('', True)
            assert 'Explanation smoke marker' in visible_text()
            app.render()
            with patch('quizmax.app.messagebox.askyesno', return_value=True):
                app.reset_progress()
            app.update()
            loaded = Library(Path(directory))
            loaded.load()
            assert len(loaded.sets) == 1
            assert len(loaded.sets[0].scores()) == 8
            assert loaded.sets[0].cards[0].explanation == 'Explanation smoke marker'
            print('Desktop smoke test passed: flashcards, Learn, feedback, mastery, reverse, reset, save.')
        finally:
            app.destroy()


if __name__ == '__main__':
    main()
