from __future__ import annotations

import copy
import tkinter as tk
from tkinter import ttk

from .ui_tokens import COLORS
from .value_rules import compile_generated_labels, validate_value_rules


class SerialEditor(ttk.Frame):
    """A draft-only editor for one generated serial value.

    No template or issuance store is modified until the owning object editor
    validates and commits the draft. Existing rule names remain stable.
    """

    ALPHABETS = {"숫자": "numeric", "영문 대문자": "uppercase", "영문 소문자": "lowercase", "숫자+영문 대문자": "alphanumeric"}

    def __init__(self, master, *, name, existing=None, initial_value='', sample_row=None, headers=(), on_change=None):
        super().__init__(master, style='Surface.TFrame', padding=12)
        self.columnconfigure(1, weight=1)
        self._name = name
        self._existing = copy.deepcopy(existing or {})
        self._sample_row = dict(sample_row or {})
        self._on_change = on_change
        alphabet = str(self._existing.get('alphabet', 'numeric'))
        start = str(self._existing.get('start', initial_value if str(initial_value).isdigit() else '1'))
        digits = int(self._existing.get('digits', max(1, len(start))))
        preserve = bool(self._existing.get('preserve_width', True))
        if self._existing and alphabet == 'numeric' and preserve:
            start = start.zfill(digits)
        self.mode = tk.StringVar(value=('decrease' if self._existing.get('direction') == 'down' else 'increase') if self._existing else 'off')
        self.start = tk.StringVar(value=start)
        self.step = tk.StringVar(value=str(self._existing.get('step', 1)))
        self.digits = tk.StringVar(value=str(digits))
        self.preserve = tk.BooleanVar(value=preserve)
        self.reset = tk.StringVar(value='continue' if self._existing.get('reset') == 'continue' else 'job')
        self.alphabet = tk.StringVar(value=next((label for label, key in self.ALPHABETS.items() if key == alphabet), '숫자'))
        self.prefix = tk.StringVar(value=str(self._existing.get('prefix', '')))
        self.suffix = tk.StringVar(value=str(self._existing.get('suffix', '')))
        self.target_field = tk.StringVar(value=str(self._existing.get('target_field', '')))
        self.target_start = tk.StringVar(value=str(self._existing.get('target_start', 1)))
        self.target_length = tk.StringVar(value=str(self._existing.get('target_length', digits)))
        self.status = tk.StringVar()
        self.preview = tk.StringVar()
        ttk.Label(self, text='일련화', style='HeaderTitle.TLabel').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        choices = ttk.Frame(self, style='Surface.TFrame'); choices.grid(row=1, column=0, columnspan=2, sticky='w')
        for label, value in (('사용 안 함', 'off'), ('증가', 'increase'), ('감소', 'decrease')):
            ttk.Radiobutton(choices, text=label, value=value, variable=self.mode).pack(side='left', padx=(0, 16))
        def row(n, label, widget):
            ttk.Label(self, text=label).grid(row=n, column=0, sticky='w', padx=(0, 12), pady=5)
            widget.grid(row=n, column=1, sticky='ew', pady=5)
        row(2, '시작 번호', ttk.Entry(self, textvariable=self.start))
        row(3, '변화량', ttk.Entry(self, textvariable=self.step))
        widths = ttk.Frame(self, style='Surface.TFrame'); widths.columnconfigure(1, weight=1)
        ttk.Checkbutton(widths, text='자리수 유지', variable=self.preserve).grid(row=0, column=0, sticky='w')
        ttk.Entry(widths, textvariable=self.digits, width=5).grid(row=0, column=1, sticky='w', padx=10)
        ttk.Label(widths, text='자리').grid(row=0, column=2, sticky='w')
        row(4, '자리수', widths)
        row(5, '다음 작업', ttk.Combobox(self, textvariable=self.reset, values=('job', 'continue'), state='readonly'))
        # Display human labels while retaining stable values in the rule.
        reset_box = self.grid_slaves(row=5, column=1)[0]
        reset_labels = {'job': '매번 시작 번호부터', 'continue': '마지막 번호 다음부터'}
        self.reset_label = tk.StringVar(value=reset_labels[self.reset.get()])
        reset_box.configure(textvariable=self.reset_label, values=tuple(reset_labels.values()))
        reset_box.bind('<<ComboboxSelected>>', lambda _e: self.reset.set('continue' if self.reset_label.get() == reset_labels['continue'] else 'job'))
        ttk.Label(self, text='예상 순서 · 번호를 발급하지 않습니다.', style='Hint.TLabel').grid(row=6, column=0, columnspan=2, sticky='w', pady=(12, 3))
        ttk.Label(self, textvariable=self.preview, wraplength=460).grid(row=7, column=0, columnspan=2, sticky='w')
        ttk.Label(self, textvariable=self.status, style='Hint.TLabel', wraplength=460).grid(row=8, column=0, columnspan=2, sticky='w', pady=(4, 4))
        advanced = ttk.Frame(self, style='Surface.TFrame'); advanced.columnconfigure(1, weight=1)
        self._advanced = advanced
        def toggle():
            if advanced.winfo_manager(): advanced.grid_remove()
            else: advanced.grid(row=10, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        ttk.Button(self, text='추가 설정 · 문자 순번 / 앞뒤 문자', command=toggle).grid(row=9, column=0, columnspan=2, sticky='w', pady=(8, 0))
        for n, label, widget in ((0, '순번 문자', ttk.Combobox(advanced, textvariable=self.alphabet, values=tuple(self.ALPHABETS), state='readonly')),
                                 (1, '번호 앞', ttk.Entry(advanced, textvariable=self.prefix)),
                                 (2, '번호 뒤', ttk.Entry(advanced, textvariable=self.suffix)),
                                 (3, 'DB 값 일부 변경', ttk.Combobox(advanced, textvariable=self.target_field, values=('', *headers), state='readonly')),
                                 (4, '바꿀 시작 위치', ttk.Entry(advanced, textvariable=self.target_start)),
                                 (5, '바꿀 글자 수', ttk.Entry(advanced, textvariable=self.target_length))):
            ttk.Label(advanced, text=label).grid(row=n, column=0, sticky='w', padx=(0, 12), pady=4)
            widget.grid(row=n, column=1, sticky='ew', pady=4)
        for v in (self.mode, self.start, self.step, self.digits, self.preserve, self.reset, self.alphabet, self.prefix, self.suffix, self.target_field, self.target_start, self.target_length):
            v.trace_add('write', self._changed)
        self._changed()

    def draft(self):
        if self.mode.get() == 'off':
            return None
        rule = copy.deepcopy(self._existing)
        rule.update(name=self._name, kind='serial', start=self.start.get().strip(), step=self.step.get().strip(),
                    digits=self.digits.get().strip(), direction='down' if self.mode.get() == 'decrease' else 'up',
                    alphabet=self.ALPHABETS[self.alphabet.get()], preserve_width=self.preserve.get(),
                    reset=self.reset.get(), prefix=self.prefix.get(), suffix=self.suffix.get())
        rule.setdefault('copies_per_value', 1)
        rule['target_field'] = self.target_field.get().strip()
        if rule['target_field']:
            rule['target_start'] = self.target_start.get().strip()
            rule['target_length'] = self.target_length.get().strip()
        else:
            rule.pop('target_start', None)
            rule.pop('target_length', None)
        return rule

    def _changed(self, *_args):
        try:
            draft = self.draft()
            if draft is None:
                self.preview.set('일련화 사용 안 함')
                self.status.set('')
            else:
                # Validate the serial itself and demonstrate successive values.
                preview_rule = dict(draft, copies_per_value=1)
                target = preview_rule.get('target_field')
                if target and target not in self._sample_row:
                    validate_value_rules([preview_rule], [str(target)])
                    self.preview.set('데이터 행을 선택하면 예상 순서를 표시합니다.')
                else:
                    values = compile_generated_labels([self._sample_row], [5], [preview_rule])
                    self.preview.set('  ·  '.join(str(v.row[self._name]) for v in values))
                self.status.set('')
        except (ValueError, KeyError) as exc:
            self.preview.set('')
            self.status.set(f'입력 확인: {exc}')
        if self._on_change:
            self._on_change()
