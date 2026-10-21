"""Tkinter desktop interface; requires only Python's standard library."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import random
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .core import Library, LearnSession, SEPARATORS, StudySet, parse_text


BG = '#f3f5fa'
INK = '#202841'
MUTED = '#616b82'
ACCENT = '#4255d4'


class App(tk.Tk):
    def __init__(self, library: Library):
        super().__init__()
        self.library = library
        self.selected: StudySet | None = None
        self.mode = 'Flashcards'
        self.reverse = tk.BooleanVar(value=False)
        self.order = []
        self.position = 0
        self.flipped = False
        self.session: LearnSession | None = None
        self.answered = False
        self.title('Quizmax • Offline study')
        self.geometry('1080x760')
        self.minsize(860, 650)
        self.configure(bg=BG)
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 11))
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=INK)
        style.configure('TButton', padding=(14, 9), background='white', foreground=INK)
        style.map('TButton', background=[('active', '#e5e9ff')])
        style.configure('Accent.TButton', background=ACCENT, foreground='white')
        style.map('Accent.TButton', background=[('active', '#3445b8')])
        style.configure('TCheckbutton', background=BG)
        style.configure('Horizontal.TProgressbar', background=ACCENT, troughcolor='#e0e5f1')
        self._layout()
        self.bind('<Left>', lambda e: self.navigate(-1) if self.mode == 'Flashcards' else None)
        self.bind('<Right>', lambda e: self.navigate(1) if self.mode == 'Flashcards' else None)
        self.bind('<space>', self._space)
        self.bind('<Return>', self._enter)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh_library()
        self.render()

    def _layout(self):
        sidebar = tk.Frame(self, bg='#202841', width=245)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='quizmax', bg='#202841', fg='white',
                 font=('Segoe UI', 26, 'bold')).pack(anchor='w', padx=22, pady=(25, 0))
        tk.Label(sidebar, text='YOUR OFFLINE STUDY SPACE', bg='#202841', fg='#b7c1e0',
                 font=('Segoe UI', 9)).pack(anchor='w', padx=24, pady=(4, 25))
        ttk.Button(sidebar, text='+ Import .txt set', command=self.import_set,
                   style='Accent.TButton').pack(fill='x', padx=18)
        tk.Label(sidebar, text='MY SETS', bg='#202841', fg='#b7c1e0',
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=24, pady=(28, 10))
        self.set_list = tk.Listbox(sidebar, bg='#202841', fg='white', bd=0,
                                   highlightthickness=0, selectbackground=ACCENT,
                                   selectforeground='white', activestyle='none',
                                   font=('Segoe UI', 12), exportselection=False)
        self.set_list.pack(fill='both', expand=True, padx=18)
        self.set_list.bind('<<ListboxSelect>>', self.select_set)
        ttk.Button(sidebar, text='Rename set', command=self.rename_set).pack(fill='x', padx=18, pady=(12, 6))
        ttk.Button(sidebar, text='Edit categories', command=self.edit_categories).pack(fill='x', padx=18, pady=(0, 6))
        ttk.Button(sidebar, text='Delete set', command=self.delete_set).pack(fill='x', padx=18, pady=(0, 12))
        tk.Label(sidebar, text='No accounts. No internet.\nYour progress stays on this device.',
                 bg='#202841', fg='#b7c1e0', justify='left', font=('Segoe UI', 9)).pack(
                     anchor='w', padx=20, pady=(8, 22))
        self.main = ttk.Frame(self, padding=28)
        self.main.pack(side='left', fill='both', expand=True)
        self.heading = ttk.Label(self.main, text='Welcome to Quizmax', font=('Segoe UI', 24, 'bold'))
        self.heading.pack(anchor='w')
        self.subheading = ttk.Label(self.main, foreground=MUTED)
        self.subheading.pack(anchor='w', pady=(5, 20))
        toolbar = ttk.Frame(self.main)
        toolbar.pack(fill='x', pady=(0, 16))
        self.mode_buttons = {}
        for mode in ('Flashcards', 'Learn'):
            button = ttk.Button(toolbar, text=mode, command=lambda m=mode: self.set_mode(m))
            button.pack(side='left', padx=(0, 8))
            self.mode_buttons[mode] = button
        ttk.Checkbutton(toolbar, text='Definition first', variable=self.reverse,
                        command=self.direction_changed).pack(side='right')
        self.body = ttk.Frame(self.main)
        self.body.pack(fill='both', expand=True)
        self.status = ttk.Label(self.main, text='', foreground=MUTED, wraplength=700)
        self.status.pack(anchor='w', pady=(14, 0))

    def refresh_library(self):
        self.set_list.delete(0, 'end')
        for i, study_set in enumerate(self.library.sets):
            self.set_list.insert('end', f'{study_set.name}  ({len(study_set.cards)})')
            if self.selected and study_set.id == self.selected.id:
                self.set_list.selection_set(i)

    def select_set(self, event=None):
        selection = self.set_list.curselection()
        if not selection:
            return
        self.selected = self.library.sets[selection[0]]
        self.reset_view()

    def reset_view(self):
        self.order = list(self.selected.cards) if self.selected else []
        self.position, self.flipped = 0, False
        self.session = LearnSession(self.selected, self.reverse.get()) if self.selected else None
        self.render()

    def save(self):
        try:
            self.library.save()
            self.status.configure(text='Saved on this device')
            return True
        except OSError as exc:
            self.status.configure(text='Save failed — keep the app open and retry.')
            messagebox.showerror('Could not save', f'Your changes are still in memory.\n\n{exc}', parent=self)
            return False

    def close(self):
        if self.save():
            self.destroy()

    def import_set(self):
        path = filedialog.askopenfilename(parent=self, title='Import a study set',
                                          filetypes=[('Text files', '*.txt'), ('All files', '*.*')])
        if not path:
            return
        dialog = tk.Toplevel(self)
        dialog.title('Import text file')
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        panel = ttk.Frame(dialog, padding=24)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Name your study set', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        name = ttk.Entry(panel, width=52)
        name.insert(0, Path(path).stem)
        name.pack(fill='x', pady=(10, 18))
        ttk.Label(panel, text='Separate each term and definition with:').pack(anchor='w')
        delimiter = ttk.Combobox(panel, state='readonly', values=['Auto-detect', *SEPARATORS], width=40)
        delimiter.set('Auto-detect')
        delimiter.pack(fill='x', pady=(8, 16))
        categorized = tk.BooleanVar(value=True)
        explained = tk.BooleanVar(value=True)
        ttk.Checkbutton(panel, text='Third column is category (term | definition | category)',
                        variable=categorized, command=lambda: explained.set(False)
                        if not categorized.get() else None).pack(anchor='w', pady=(0, 8))
        ttk.Checkbutton(panel, text='Fourth column is explanation (shown after answering)',
                        variable=explained, command=lambda: categorized.set(True)
                        if explained.get() else None).pack(anchor='w', pady=(0, 12))
        ttk.Label(panel, text='One card per line, for example:\nbonjour | hello\nmerci | thank you\n\n'
                  'For two-column files, uncheck both column options above.\n'
                  'Quizlet tab-separated exports also work.\nBlank lines and lines starting with # are ignored.',
                  foreground=MUTED).pack(anchor='w')

        def finish():
            if not name.get().strip():
                messagebox.showerror('Name required', 'Enter a name for this set.', parent=dialog)
                return
            try:
                raw = Path(path).read_text(encoding='utf-8-sig')
                cards = parse_text(raw, SEPARATORS.get(delimiter.get()), categorized.get(), explained.get())
            except (OSError, UnicodeError, ValueError) as exc:
                messagebox.showerror('Import failed', f'{exc}\n\nSave the file as UTF-8 text.', parent=dialog)
                return
            self.selected = StudySet(name.get().strip(), cards)
            self.library.sets.append(self.selected)
            self.refresh_library()
            self.reset_view()
            self.save()
            dialog.destroy()

        ttk.Button(panel, text='Import set', command=finish, style='Accent.TButton').pack(fill='x', pady=(20, 0))
        name.focus_set()

    def rename_set(self):
        if not self.selected:
            return
        name = simpledialog.askstring('Rename set', 'Set name:', initialvalue=self.selected.name, parent=self)
        if name and name.strip():
            self.selected.name = name.strip()
            self.refresh_library()
            self.heading.configure(text=self.selected.name)
            self.save()

    def edit_categories(self):
        if not self.selected:
            return
        dialog = tk.Toplevel(self)
        dialog.title('Edit card categories')
        dialog.geometry('720x480')
        dialog.transient(self)
        dialog.grab_set()
        panel = ttk.Frame(dialog, padding=20)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Select cards, then assign a category.',
                  font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='Ctrl/Shift selects multiple cards. Leave the category blank to clear it.',
                  foreground=MUTED).pack(anchor='w', pady=(6, 12))
        table_frame = ttk.Frame(panel)
        table_frame.pack(fill='both', expand=True)
        table = ttk.Treeview(table_frame, columns=('term', 'category'), show='headings', selectmode='extended')
        table.heading('term', text='Term')
        table.heading('category', text='Category')
        table.column('term', width=400)
        table.column('category', width=200)
        scrollbar = ttk.Scrollbar(table_frame, command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        table.pack(fill='both', expand=True)
        for i, card in enumerate(self.selected.cards):
            table.insert('', 'end', iid=str(i), values=(card.term, card.category))
        ttk.Label(panel, text='Category').pack(anchor='w', pady=(12, 4))
        entry = ttk.Combobox(panel, values=sorted({c.category for c in self.selected.cards if c.category}))
        entry.pack(fill='x')

        def apply():
            indices = [int(i) for i in table.selection()]
            if not indices:
                return
            category = entry.get().strip()
            for i in indices:
                self.selected.cards[i] = replace(self.selected.cards[i], category=category)
                table.item(str(i), values=(self.selected.cards[i].term, category))
            entry.configure(values=sorted({c.category for c in self.selected.cards if c.category}))
            self.reset_view()
            self.save()

        controls = ttk.Frame(panel)
        controls.pack(fill='x', pady=(12, 0))
        ttk.Button(controls, text='Apply to selected cards', command=apply,
                   style='Accent.TButton').pack(side='left')
        ttk.Button(controls, text='Done', command=dialog.destroy).pack(side='right')

    def delete_set(self):
        if self.selected and messagebox.askyesno('Delete set?',
                f'Delete “{self.selected.name}” and its progress? Your original .txt file will remain.', parent=self):
            self.library.sets.remove(self.selected)
            self.selected = None
            self.refresh_library()
            self.reset_view()
            self.save()

    def set_mode(self, mode):
        self.mode = mode
        self.render()

    def direction_changed(self):
        self.reset_view()

    def render(self):
        for widget in self.body.winfo_children():
            widget.destroy()
        self.answered = False
        self.answer_entry = None
        for mode, button in self.mode_buttons.items():
            button.configure(style='Accent.TButton' if mode == self.mode else 'TButton')
        if not self.selected:
            self.heading.configure(text='Make room for what you know.')
            self.subheading.configure(text='Import a text file and start studying at your own pace.')
            ttk.Label(self.body, text='A simple file. A whole set of possibilities.',
                      font=('Segoe UI', 18, 'bold')).pack(anchor='w', pady=(45, 20))
            ttk.Label(self.body, text='Create a .txt file with one term and definition per line:\n\n'
                      'mitochondria | The powerhouse of the cell\n'
                      'nucleus | Contains the cell’s genetic material\n\n'
                      'Use tabs, pipes, double colons, semicolons, dashes, or colons.\n'
                      'An example set is included in the examples folder.',
                      foreground=MUTED, wraplength=590, justify='left').pack(anchor='w')
            ttk.Button(self.body, text='Import your first set', command=self.import_set,
                       style='Accent.TButton').pack(anchor='w', pady=24)
            return
        self.heading.configure(text=self.selected.name)
        self.subheading.configure(text=f'{len(self.selected.cards)} cards  •  '
                                  + ('Definition → term' if self.reverse.get() else 'Term → definition'))
        if self.mode == 'Flashcards':
            self.render_flashcards()
        else:
            self.render_learn()

    def card_panel(self, label, text, clickable=False):
        panel = tk.Frame(self.body, bg='white', highlightbackground='#dce1ee', highlightthickness=1)
        panel.pack(fill='both', expand=True, pady=(10, 15))
        tk.Label(panel, text=label.upper(), font=('Segoe UI', 10, 'bold'), bg='white',
                 fg=MUTED).pack(pady=(18, 8))
        content = tk.Text(panel, wrap='word', bg='white', fg=INK, font=('Segoe UI', 21),
                          height=4, bd=0, highlightthickness=0, padx=24, pady=12,
                          cursor='hand2' if clickable else 'arrow')
        scrollbar = ttk.Scrollbar(panel, command=content.yview)
        scrollbar.pack(side='right', fill='y')
        content.configure(yscrollcommand=scrollbar.set)
        content.pack(fill='both', expand=True)
        content.tag_configure('center', justify='center')
        content.insert('1.0', text, 'center')
        content.configure(state='disabled')
        if clickable:
            content.bind('<Button-1>', lambda e: self.flip())
            panel.bind('<Button-1>', lambda e: self.flip())
        return panel

    def render_flashcards(self):
        card = self.order[self.position]
        sides = (card.definition, card.term) if self.reverse.get() else (card.term, card.definition)
        labels = ('Definition', 'Term') if self.reverse.get() else ('Term', 'Definition')
        ttk.Label(self.body, text=f'Card {self.position + 1} of {len(self.order)}  •  '
                  f'{card.category or "Uncategorized"}', foreground=MUTED).pack(anchor='w')
        content = sides[int(self.flipped)]
        if self.flipped and card.explanation:
            content += f'\n\nExplanation: {card.explanation}'
        self.card_panel(labels[int(self.flipped)], content, clickable=True)
        ttk.Label(self.body, text='Click the card or press Space to flip. Use ← and → to browse.',
                  foreground=MUTED).pack(pady=(0, 16))
        controls = ttk.Frame(self.body)
        controls.pack()
        ttk.Button(controls, text='← Previous', command=lambda: self.navigate(-1)).pack(side='left', padx=4)
        ttk.Button(controls, text='Flip card', command=self.flip, style='Accent.TButton').pack(side='left', padx=4)
        ttk.Button(controls, text='Next →', command=lambda: self.navigate(1)).pack(side='left', padx=4)
        ttk.Button(self.body, text='Shuffle cards', command=self.shuffle).pack(pady=(16, 0))

    def flip(self):
        if self.selected and self.mode == 'Flashcards':
            self.flipped = not self.flipped
            self.render()

    def navigate(self, amount):
        if self.order and self.grab_current() is None:
            self.position = (self.position + amount) % len(self.order)
            self.flipped = False
            self.render()

    def shuffle(self):
        random.shuffle(self.order)
        self.position, self.flipped = 0, False
        self.render()

    def render_learn(self):
        session = self.session
        top = ttk.Frame(self.body)
        top.pack(fill='x')
        ttk.Label(top, text=f'{session.mastered} / {len(self.selected.cards)} mastered',
                  font=('Segoe UI', 12, 'bold')).pack(side='left')
        ttk.Button(top, text='Reset progress', command=self.reset_progress).pack(side='right')
        ttk.Progressbar(self.body, maximum=len(self.selected.cards), value=session.mastered).pack(fill='x', pady=12)
        card = session.current
        if card is None:
            ttk.Label(self.body, text='Set mastered!', font=('Segoe UI', 30, 'bold')).pack(pady=(70, 16))
            ttk.Label(self.body, text='You recalled every card correctly twice in a row.\n'
                      'Reset your progress any time to practice again.', justify='center', foreground=MUTED).pack()
            ttk.Button(self.body, text='Review flashcards', command=lambda: self.set_mode('Flashcards'),
                       style='Accent.TButton').pack(pady=24)
            return
        choices = session.choices()
        ttk.Label(self.body, text=f'Category: {card.category or "Uncategorized"}',
                  foreground=MUTED).pack(anchor='w')
        ttk.Label(self.body, text='Choose the matching answer' if choices else 'Type the matching answer',
                  foreground=MUTED).pack(anchor='w')
        self.card_panel('Definition' if self.reverse.get() else 'Term', session.sides(card)[0])
        self.response = ttk.Frame(self.body)
        self.response.pack(fill='x')
        if choices:
            for choice in choices:
                button = tk.Button(self.response, text=choice, wraplength=560, anchor='w',
                                   justify='left', bg='white', fg=INK, activebackground='#e5e9ff',
                                   relief='flat', font=('Segoe UI', 11), padx=14, pady=8,
                                   command=lambda answer=choice: self.submit(answer))
                button.pack(fill='x', pady=3)
        else:
            self.answer_entry = ttk.Entry(self.response, font=('Segoe UI', 14))
            self.answer_entry.pack(fill='x', pady=(0, 10))
            self.answer_entry.focus_set()
            ttk.Button(self.response, text='Check answer', command=self.check_answer,
                       style='Accent.TButton').pack(side='left')
        ttk.Button(self.response, text="I don’t know", command=lambda: self.submit('', True)).pack(pady=(8, 0))

    def check_answer(self):
        if self.answer_entry and self.answer_entry.get().strip():
            self.submit(self.answer_entry.get())

    def submit(self, answer, skip=False):
        if self.answered:
            return
        expected = self.session.sides(self.session.current)[1]
        explanation = self.session.current.explanation
        correct = self.session.submit(answer, skip)
        self.answered = True
        self.answer_entry = None
        for widget in self.response.winfo_children():
            widget.destroy()
        ttk.Label(self.response, text='Correct!' if correct else 'Keep practicing — this card will return.',
                  foreground='#237348' if correct else '#a04623', font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        feedback_frame = ttk.Frame(self.response)
        feedback_frame.pack(fill='x', pady=8)
        feedback = tk.Text(feedback_frame, height=5 if explanation else 3, wrap='word', font=('Segoe UI', 11),
                           bg='white', fg=INK, relief='flat', padx=10, pady=8)
        feedback.insert('1.0', f'Answer: {expected}' + (f'\nYour answer: {answer}' if not correct and answer else ''))
        if explanation:
            feedback.insert('end', f'\n\nExplanation: {explanation}')
        feedback.configure(state='disabled')
        scrollbar = ttk.Scrollbar(feedback_frame, command=feedback.yview)
        feedback.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        feedback.pack(fill='x', expand=True)
        controls = ttk.Frame(self.response)
        controls.pack(fill='x')
        ttk.Button(controls, text='Continue →', command=self.render, style='Accent.TButton').pack(side='left')
        if not correct and not skip:
            ttk.Button(controls, text='Accept my answer', command=self.accept_answer).pack(side='right')
        self.save()

    def accept_answer(self):
        self.session.accept_previous()
        self.save()
        self.render()

    def reset_progress(self):
        if messagebox.askyesno('Reset Learn progress?', 'Start this set over in the current direction?', parent=self):
            self.selected.scores(self.reverse.get()).clear()
            self.session = LearnSession(self.selected, self.reverse.get())
            self.save()
            self.render()

    def _space(self, event):
        if self.grab_current() is None and not isinstance(event.widget, (ttk.Entry, ttk.Button, tk.Button)):
            self.flip()
            return 'break'

    def _enter(self, event):
        if self.grab_current() is not None or not self.selected or self.mode != 'Learn':
            return
        if self.answered:
            self.render()
        else:
            self.check_answer()
        return 'break'


def main():
    parser = argparse.ArgumentParser(description='Quizmax offline flashcards and learning')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / '.quizmax',
                        help='Directory for library.json (default: ~/.quizmax)')
    args = parser.parse_args()
    library = Library(args.data_dir)
    try:
        library.load()
    except (OSError, ValueError) as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('Library could not be opened', str(exc), parent=root)
        root.destroy()
        return
    App(library).mainloop()
