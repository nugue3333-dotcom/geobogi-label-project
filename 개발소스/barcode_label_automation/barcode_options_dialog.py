"""Capability-driven editor, validated through the actual output renderer."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from collections.abc import Callable, Mapping
from PIL import Image, ImageTk
from .barcode_catalog import BARCODE_TYPES, SAMPLE_VALUES, option_definitions
from .barcode_engine import render_barcode
from .brand_assets import apply_window_icon, load_header_logo
from .ui_tokens import COLORS
from .ui_window import set_initial_window_size


def edit_barcode_options(parent: tk.Misc, code_type: str, options: Mapping[str, object],
                         callback: Callable[[dict[str, object]], None], *,
                         preview_value: str | None = None,
                         preview_renderer: Callable[[dict[str, object]], Image.Image] | None = None,
                         dpi: int = 203) -> tk.Toplevel:
    window = tk.Toplevel(parent)
    window.title(f'{BARCODE_TYPES.get(code_type, code_type)} · 바코드 세부 옵션')
    window.configure(bg=COLORS.surface); window.transient(parent)
    set_initial_window_size(window, preferred_width=720, preferred_height=720, minimum_width=500, minimum_height=500)
    apply_window_icon(window)
    window.columnconfigure(0, weight=1); window.rowconfigure(1, weight=1)
    header = ttk.Frame(window, style='Surface.TFrame', padding=(18, 12))
    header.grid(row=0, column=0, sticky='ew'); header.columnconfigure(0, weight=1)
    title_bar = ttk.Frame(header,style='Surface.TFrame');title_bar.grid(row=0,column=0,sticky='ew')
    logo = load_header_logo(window,max_width=150,max_height=40)
    if logo is not None:
        window._barcode_logo = logo
        ttk.Label(title_bar,image=logo,style='Surface.TLabel').pack(side='left',padx=(0,16))
    ttk.Label(title_bar, text=BARCODE_TYPES.get(code_type, code_type), style='PanelTitle.TLabel').pack(side='left')
    sample = preview_value is None
    value = SAMPLE_VALUES.get(code_type, '123456') if sample else preview_value
    ttk.Label(header, text='형식 예제로 확인 · 실제 DB 값과 인쇄 영역은 출력 전 별도 검증' if sample else
              '현재 데이터로 확인 · 적용할 때 새 옵션으로 다시 생성합니다.', wraplength=660,
              style='Status.TLabel').grid(row=1, column=0, sticky='w', pady=(6, 0))
    value_var = tk.StringVar(value=value)
    window._barcode_preview_value = value_var
    ttk.Entry(header, textvariable=value_var, state='readonly').grid(row=2, column=0, sticky='ew', pady=(6, 0))
    notebook = ttk.Notebook(window); notebook.grid(row=1, column=0, sticky='nsew', padx=18)
    specs = option_definitions(code_type); variables = {}; widgets = {}
    basic = {'cell_size', 'module_width', 'quiet_zone', 'human_readable', 'qr_ecc', 'bar_height', 'check_digit'}
    groups = {}
    for title in ('일반', '고급'):
        panel = ttk.Frame(notebook); panel.columnconfigure(0, weight=1); panel.rowconfigure(0, weight=1)
        notebook.add(panel, text=title)
        canvas = tk.Canvas(panel, bg=COLORS.surface, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(panel, orient='vertical', command=canvas.yview)
        scroll.grid(row=0, column=1, sticky='ns'); canvas.configure(yscrollcommand=scroll.set)
        body = ttk.Frame(canvas, style='Surface.TFrame', padding=(8, 8)); body.columnconfigure(1, weight=1)
        body_id = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda _event, c=canvas:c.configure(scrollregion=c.bbox('all')))
        canvas.bind('<Configure>', lambda event, c=canvas, i=body_id:c.itemconfigure(i, width=event.width))
        canvas.bind('<MouseWheel>', lambda event, c=canvas:c.yview_scroll(-1 if event.delta > 0 else 1, 'units'))
        groups[title] = [body, 0]
    status = tk.StringVar(value='미리보기 및 생성 검증을 누르세요. 입력을 변경하면 이전 검증은 무효화됩니다.')
    size_help = tk.StringVar()
    image_label = ttk.Label(window, style='Surface.TLabel', anchor='center')

    def update_help(*_args: object) -> None:
        size_key = 'cell_size' if 'cell_size' in variables else 'module_width'
        try:
            dots = int(variables[size_key].get())
            size_help.set(f'모듈 {dots}도트 = {dots * 25.4 / max(1, dpi):.3f}mm ({dpi} DPI)' if dots else
                          f'모듈 크기 자동 · 실제 인쇄 영역과 {dpi} DPI에 맞춰 정수 도트로 계산')
            if code_type in {'qr', 'gs1_qr', 'hibcqr'} and 'version' in variables:
                version = int(variables['version'].get())
                size_help.set(size_help.get() + (f' · QR 버전 {version}: {17 + 4 * version}×{17 + 4 * version}모듈 (여백 제외)' if version else ' · QR 버전 자동'))
        except (ValueError, tk.TclError):
            size_help.set('모듈 크기와 버전은 숫자로 입력하세요.')

    def invalidate(*_args: object) -> None:
        status.set('옵션이 변경되었습니다. 새 옵션으로 다시 생성해 확인하세요.')
        image_label.configure(image=''); window._barcode_preview_image = None
        update_help()

    for key, spec in specs.items():
        body, index = groups['일반' if key in basic else '고급']
        raw = options.get(key, spec.get('default', ''))
        variable = tk.BooleanVar(value=bool(raw)) if spec.get('type') == 'bool' else tk.StringVar(value=str(raw))
        variables[key] = variable
        ttk.Label(body, text=str(spec['label']), wraplength=220).grid(row=index, column=0, sticky='w', padx=(0, 12), pady=6)
        if spec.get('type') == 'bool':
            widget = ttk.Checkbutton(body, variable=variable)
        elif 'choices' in spec:
            widget = ttk.Combobox(body, textvariable=variable, values=tuple(spec['choices']), state='readonly')
        else:
            widget = ttk.Entry(body, textvariable=variable)
        widget.grid(row=index, column=1, sticky='ew', pady=6)
        widgets[key] = widget
        groups['일반' if key in basic else '고급'][1] += 1
        variable.trace_add('write', invalidate)
    footer = ttk.Frame(window, style='Surface.TFrame', padding=(18, 12))
    footer.grid(row=3, column=0, sticky='ew')
    image_label.grid(row=2, column=0, sticky='ew', padx=18, pady=4)
    help_body, help_row = groups['일반']
    ttk.Label(help_body, textvariable=size_help, wraplength=400, style='Status.TLabel').grid(row=help_row,column=0,columnspan=2,sticky='ew',pady=8)
    ttk.Label(help_body, text='규격 여백을 유지합니다. 바코드를 임의 축소하지 않습니다. 고급 크기 번호의 적합성은 생성 결과로 확인합니다.',
              wraplength=400, style='Status.TLabel').grid(row=help_row+1,column=0,columnspan=2,sticky='ew',pady=4)
    status_frame = ttk.Frame(footer, style='Surface.TFrame')
    status_frame.pack(fill='x',pady=(0,8)); status_frame.columnconfigure(0,weight=1)
    status_text = tk.Text(status_frame,height=2,wrap='word',state='disabled',relief='flat',
                          background=COLORS.surface,foreground=COLORS.text_primary)
    status_text.grid(row=0,column=0,sticky='ew')
    status_scroll = ttk.Scrollbar(status_frame,orient='vertical',command=status_text.yview)
    status_scroll.grid(row=0,column=1,sticky='ns'); status_text.configure(yscrollcommand=status_scroll.set)
    def status_changed(*_args: object) -> None:
        status_text.configure(state='normal');status_text.delete('1.0','end')
        status_text.insert('1.0',status.get());status_text.configure(state='disabled')
    status.trace_add('write',status_changed);status_changed()

    def read_options() -> dict[str, object]:
        result = {}
        for key, spec in specs.items():
            try:
                raw = variables[key].get()
                if spec.get('type') == 'bool':
                    parsed = bool(raw)
                elif 'choices' in spec:
                    parsed = str(raw)
                    if parsed not in spec['choices']:
                        raise ValueError('허용값을 선택하세요.')
                elif spec.get('type') == 'text':
                    parsed = str(raw)
                else:
                    parsed = float(str(raw)) if spec.get('type') == 'float' else int(str(raw))
                    if not float(spec['min']) <= parsed <= float(spec['max']):
                        raise ValueError(f'{spec["min"]}~{spec["max"]} 범위입니다.')
                result[key] = parsed
            except (ValueError, TypeError, tk.TclError) as exc:
                notebook.select(0 if key in basic else 1)
                window.update_idletasks()
                invalid_body = widgets[key].master
                invalid_canvas = invalid_body.master
                invalid_canvas.yview_moveto(max(0, widgets[key].winfo_y()-8)/max(1,invalid_body.winfo_height()))
                widgets[key].focus_set()
                raise ValueError(f'{spec["label"]}: {exc}') from exc
        return result

    def verify(apply: bool = False) -> None:
        try:
            result = read_options()
            if preview_renderer is not None:
                image = preview_renderer(result)
            else:
                image = render_barcode(code_type, str(value), result)
            if not isinstance(image, Image.Image):
                raise ValueError('미리보기 생성 결과가 올바르지 않습니다.')
            display = image.convert('RGB')
            # Screen illustration may shrink; the supplied output renderer must
            # reject an undersized print box rather than shrink symbol modules.
            display.thumbnail((580, 100), Image.Resampling.NEAREST)
            window._barcode_preview_image = ImageTk.PhotoImage(display, master=window)
            image_label.configure(image=window._barcode_preview_image)
            status.set(('형식 예제의 생성 검증을 통과했습니다. 실제 DB 값과 인쇄 영역은 아직 검증하지 않았습니다.' if sample else
                        '현재 데이터와 옵션의 생성 검증을 통과했습니다.' + (' 인쇄 영역도 확인했습니다.' if preview_renderer else ' 인쇄 영역은 출력 전에 확인합니다.'))
                       + f' 생성 이미지: {image.width}×{image.height}도트.')
            if apply:
                callback(result); window.destroy()
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            image_label.configure(image=''); window._barcode_preview_image = None
            status.set(f'옵션을 적용할 수 없습니다: {exc}')

    actions = ttk.Frame(footer,style='Surface.TFrame');actions.pack(fill='x')
    action_buttons = [ttk.Button(actions,text='미리보기 및 생성 검증',command=verify),
                      ttk.Button(actions,text='적용',command=lambda:verify(True),style='Primary.TButton'),
                      ttk.Button(actions,text='취소',command=window.destroy)]
    def wrap_actions(event: object = None) -> None:
        width = getattr(event,'width',actions.winfo_width())
        columns=max(1,min(3,int(width)//max(button.winfo_reqwidth()+8 for button in action_buttons)))
        for index,button in enumerate(action_buttons):
            button.grid(row=index//columns,column=index%columns,sticky='ew',padx=3,pady=3)
        for column in range(3):
            actions.columnconfigure(column,weight=1 if column<columns else 0)
    actions.bind('<Configure>',wrap_actions);window.after_idle(wrap_actions)
    update_help()
    def resized(event: tk.Event) -> None:
        if event.widget is window:
            for container in (header, footer, help_body):
                for label in container.winfo_children():
                    if isinstance(label, ttk.Label):
                        label.configure(wraplength=max(240, event.width-90))
    window.bind('<Configure>', resized, add='+')
    window.bind('<Escape>', lambda _event:window.destroy())
    window.grab_set()
    return window
