"""Offline release acceptance of the actual designer widgets and saved payload.

The hidden CLI entry always uses a fresh fixture folder and never sends a job.
"""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from PIL import ImageGrab


def run_workflow_probe(output_dir: Path) -> int:
    from . import label_designer_app as designer
    from .config import load_config
    from .template_output import render_command, validate_rows
    from .templates import mm_to_dots
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {'passed':False,'boundary':'actual Tk widgets, offline commands only; no printer transmission','checks':[]}
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        report['checks'].append(name)
    def descendants(parent):
        return [child for direct in parent.winfo_children() for child in (direct, *descendants(direct))]
    def settle(app):
        app.update_idletasks(); app.update(); app.update_idletasks()
    def button(parent, text):
        return next(w for w in descendants(parent) if isinstance(w,ttk.Button) and str(w.cget('text'))==text)
    def visible_click(widget):
        ancestor=widget.master
        while ancestor is not None:
            if isinstance(ancestor,tk.Canvas):
                for _ in range(30):
                    top=widget.winfo_rooty()-ancestor.winfo_rooty()
                    if top>=0 and top+widget.winfo_height()<=ancestor.winfo_height():
                        break
                    ancestor.event_generate('<MouseWheel>',delta=120 if top<0 else -120)
                    settle(app)
            ancestor=ancestor.master
        check('visible control '+str(widget.cget('text')),bool(widget.winfo_ismapped()))
        ancestor=widget.master
        while ancestor is not None:
            if isinstance(ancestor,(tk.Canvas,tk.Toplevel)):
                x,y=widget.winfo_rootx(),widget.winfo_rooty()
                check('unclipped control '+str(widget.cget('text')),
                    x>=ancestor.winfo_rootx() and y>=ancestor.winfo_rooty() and
                    x+widget.winfo_width()<=ancestor.winfo_rootx()+ancestor.winfo_width() and
                    y+widget.winfo_height()<=ancestor.winfo_rooty()+ancestor.winfo_height())
            ancestor=ancestor.master
        widget.event_generate('<ButtonPress-1>',x=widget.winfo_width()//2,y=widget.winfo_height()//2)
        widget.event_generate('<ButtonRelease-1>',x=widget.winfo_width()//2,y=widget.winfo_height()//2)
        settle(app)
    startup = designer.LabelDesignerApp._offer_start_dialog
    recovery = designer.LabelDesignerApp._offer_recovery
    askyesno = designer.messagebox.askyesno
    app = None
    try:
        with tempfile.TemporaryDirectory(prefix='designer-workflow-',dir=output_dir) as folder:
            base=Path(folder)
            (base/'config.ini').write_text('[printer]\nbrand=tsc\nmode=network\nlanguage=tspl\nip=127.0.0.1\nport=9100\n[label]\nwidth_mm=60\nheight_mm=35\ndpi=203\n[data]\nexcel_file=print_queue.xlsx\noutput_dir=out\n',encoding='utf-8')
            designer.LabelDesignerApp._offer_start_dialog=lambda _self:None
            designer.LabelDesignerApp._offer_recovery=lambda _self:None
            designer.messagebox.askyesno=lambda *args,**kwargs:True
            app=designer.LabelDesignerApp(base,register_file_association=False)
            app._recovery_prompt_pending=False
            callback_errors=[]
            app.report_callback_exception=lambda *args:callback_errors.append(str(args[1]))
            app.geometry('1200x780+10+10')
            app.add_barcode_element('qr')
            element=app.selected_element()
            app.open_element_editor(element);settle(app)
            editor=next(w for w in descendants(app) if isinstance(w,tk.Toplevel) and w.title()=='바코드 속성')
            editor.geometry('1020x740+30+30');settle(app)
            nav=next(w for w in descendants(editor) if isinstance(w,ttk.Treeview) and w.cget('style')=='EditorNav.Treeview')
            check('focused property navigation', [nav.item(item,'text') for item in nav.get_children()]==['데이터 원본','바코드 종류·크기','표시문자'])
            check('data first',nav.selection()==('data',))
            check('advanced options are opt-in',not any(nav.item(item,'text')=='추가 데이터 옵션' for item in nav.get_children()))
            visible_click(button(editor,'GS1 데이터로 설정…'))
            gs1=editor._barcode_controllers['active']
            selection_label=next(w for w in descendants(gs1) if isinstance(w,ttk.Label) and str(w.cget('text'))=='선택 AI')
            selector=next(w for w in selection_label.master.winfo_children() if isinstance(w,ttk.Combobox) and w.grid_info().get('row')==2)
            selector.set('01 · 상품식별번호 GTIN');selector.event_generate('<<ComboboxSelected>>');settle(app)
            entry=next(w for w in selection_label.master.winfo_children() if isinstance(w,ttk.Entry) and w.grid_info().get('row')==4)
            entry.insert(0,'09506000134376');settle(app)
            check('preview does not insert a composition row',gs1.get_records()==[])
            visible_click(button(gs1,'추가'))
            check('manual GS1 add creates exactly one row',len(gs1.get_records())==1)
            visible_click(button(gs1,'데이터 검증'))
            visible_click(button(editor,'적용'))
            check('manual GS1 value committed',element.get('gs1_elements')==[{'ai':'01','value':'09506000134376','source_field':''}])
            editor.lift();editor.attributes('-topmost',True);editor.focus_force();settle(app);time.sleep(.35)
            x,y=editor.winfo_rootx(),editor.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+editor.winfo_width(),y+editor.winfo_height()),all_screens=True).save(output_dir/'frozen-gs1-input.png')
            visible_click(button(editor,'확인'))
            app.open_element_editor(element);settle(app)
            editor=next(w for w in descendants(app) if isinstance(w,tk.Toplevel) and w.title()=='바코드 속성')
            editor.geometry('1020x740+30+30');settle(app)
            editor._barcode_show_page('data')
            editor._barcode_code_var.set(designer.BARCODE_TYPES['gs1_datamatrix'])
            editor._barcode_code_combo.event_generate('<<ComboboxSelected>>');settle(app)
            check('UDI configuration opens only from additional options',editor._barcode_open_advanced('udi') is not None)
            controller=editor._barcode_controllers['active']
            before=designer.copy.deepcopy(element)
            check('complete UDI example generation',controller.load_complete_example())
            check('UDI apply',controller.validate(True))
            check('draft remains separate until confirmation',element==before and editor._barcode_draft['barcode_type']=='gs1_datamatrix')
            check('optional UDI source selected explicitly',editor._barcode_source_kind_var.get()=='udi')
            settle(app)
            editor._barcode_preview_panel.original.save(output_dir/'barcode-preview-original.png')
            def capture(name):
                editor.lift()
                editor.attributes('-topmost',True)
                editor.focus_force()
                settle(app)
                time.sleep(.35)
                x,y=editor.winfo_rootx(),editor.winfo_rooty()
                ImageGrab.grab(bbox=(x,y,x+editor.winfo_width(),y+editor.winfo_height()),all_screens=True).save(output_dir/name)
            capture('frozen-udi-content.png')
            editor._barcode_show_page('size')
            fit=button(editor,'현재 라벨에 맞추기')
            fit.invoke();settle(app)
            settle(app)
            capture('frozen-udi-size.png')
            # General data checks remain in the main output flow. The editor only
            # validates its active source and commits the staged element.
            button(editor,'확인').invoke();settle(app)
            check('editor closes after committing draft',not editor.winfo_exists())
            check('UDI profile committed only after confirmation',element.get('udi_profile')=='GS1' and element['barcode_type']=='gs1_datamatrix')
            check('all DB rows validate in the main output workflow',validate_rows(app.template_payload(),[app.preview_row],app.base_dir,dpi=203)==[])
            # Validate, close, and resize via the actual canvas event handlers.
            before=element['barcode_layout']['symbol_width_mm']
            before_ratio=before/element['barcode_layout']['symbol_height_mm']
            bounds=app._barcode_canvas_bounds(element)
            app.on_canvas_press(SimpleNamespace(x=bounds[2],y=bounds[3],state=0))
            app.on_canvas_drag(SimpleNamespace(x=bounds[2]-app.scale,y=bounds[3],state=0))
            app.on_canvas_release(SimpleNamespace(x=bounds[2],y=bounds[3],state=0))
            check('horizontal mouse resize changes both code targets',element['barcode_layout']['symbol_width_mm']<before and abs(element['barcode_layout']['symbol_width_mm']/element['barcode_layout']['symbol_height_mm']-before_ratio)<1e-5)
            app._validate_output_row({},row_number=1)
            path=base/'saved.cllabel';path.write_text(json.dumps(app.template_payload(),ensure_ascii=False),encoding='utf-8')
            reopened=designer.load_template_file(path)
            value=designer._designer_code_value(reopened['elements'][0],{})
            check('saved UDI profile preserved',reopened['elements'][0]['udi_profile']=='GS1')
            check('saved payload preserved',value==designer._designer_code_value(element,{}))
            config=load_config(base/'config.ini')
            command=render_command(reopened,{},config,base,2)
            check('repeat command is stable',command==render_command(reopened,{},config,base,2))
            (output_dir/'verified-repeat.tspl').write_bytes(command)
            obj=reopened['elements'][0]
            image=app._render_element_bitmap(obj,{},mm_to_dots(obj['width'],203),mm_to_dots(obj['height'],203),transparent=False)
            check('HRI retains all AI groups',''.join(image.info['hri_lines'])==value)
            image.save(output_dir/'verified-saved-udi.png')
            check('no Tk callback errors',not callback_errors)
            check('right sidebar stays DB only',not any(str(w.cget('text'))=='개체 속성' for w in descendants(app) if isinstance(w,ttk.Label)))
            app.destroy();app=None
        report.update(passed=True,status='passed',check_count=len(report['checks']))
    except (ValueError,AssertionError,StopIteration,tk.TclError,OSError) as exc:
        report.update(status='failed',error=str(exc),check_count=len(report['checks']))
    finally:
        if app is not None:
            app.destroy()
        designer.LabelDesignerApp._offer_start_dialog=startup
        designer.LabelDesignerApp._offer_recovery=recovery
        designer.messagebox.askyesno=askyesno
        (output_dir/'workflow-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['passed'] else 1


def run_manager_workflow_probe(output_dir: Path) -> int:
    """Follow real DB/inline-edit/selection/queue paths without a transport."""
    from .data_store import DB_HEADERS, save_db_rows, save_label_rows, load_db_source
    from .label_manager_app import LabelManagerApp, _printable_rows_from_label_rows
    from .label_designer_app import _element, _render_engine_barcode_box
    from .hibc import compose_hibc, resolve_hibc
    from .templates import mm_to_dots
    output_dir.mkdir(parents=True, exist_ok=True)
    report={'passed':False,'checks':[],'boundary':'actual manager Tk widgets and temporary queue; no printer transmission'}
    app=None
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        report['checks'].append(name)
    try:
        with tempfile.TemporaryDirectory(prefix='manager-workflow-',dir=output_dir) as folder:
            base=Path(folder)
            value=next(compose_hibc('A123',str(i),'0') for i in range(1000) if compose_hibc('A123',str(i),'0').endswith(' '))
            row=dict.fromkeys(DB_HEADERS,'')
            row.update(barcode=value,item_code='0001',item_name='HIBC trial',qty='1',print_qty='2',complete_hibc=value)
            save_db_rows(base/'barcode_db.xlsx',[row])
            (base/'config.ini').write_text('[printer]\nbrand=tsc\nmode=network\nlanguage=tspl\nip=127.0.0.1\nport=9100\n[label]\nwidth_mm=60\nheight_mm=35\ndpi=203\n[data]\nexcel_file=print_queue.xlsx\noutput_dir=out\n',encoding='utf-8')
            app=LabelManagerApp(base)
            app.geometry('1200x780+10+10');app.update_idletasks();app.update()
            check('DB load preserves checksum space',app.db_rows[0]['barcode']==value)
            check('DB to label rows preserves checksum space',app.label_rows[0]['barcode']==value)
            app.scan_var.set(value);app.scan_barcode();app.update_idletasks();app.update()
            check('scan lookup selects original row',0 in app.selected_label_indexes)
            app.tabs.select(app.tabs.tabs()[0]);app.update_idletasks();app.update()
            item=app.labels_tree.get_children()[0]
            column=app.label_display_headers.index('barcode')+1
            box=app.labels_tree.bbox(item,f'#{column}')
            check('barcode inline cell is accessible',bool(box))
            app.begin_edit(app.labels_tree,SimpleNamespace(x=box[0]+box[2]/2,y=box[1]+box[3]/2))
            app.update_idletasks();app.update()
            check('inline editor shows complete original',app.active_editor.get()==value)
            app.active_editor.delete(0,'end');app.active_editor.insert(0,value)
            app.active_editor.event_generate('<Return>');app.update_idletasks();app.update()
            check('inline commit preserves checksum space',app.label_rows[0]['barcode']==value)
            printable=_printable_rows_from_label_rows(app.label_rows,app.label_headers)
            check('queue conversion preserves barcode',printable[0]['barcode']==value)
            check('queue conversion preserves custom binding',printable[0]['complete_hibc']==value)
            queue=output_dir/'manager-verified-queue.xlsx';save_label_rows(queue,printable)
            loaded,_=load_db_source(queue)
            check('saved queue retains original',loaded[0]['barcode']==loaded[0]['complete_hibc']==value)
            check('completed HIBC remains valid',resolve_hibc(loaded[0]['barcode'],'complete')==value)
            obj=_element('barcode',value,0,0,55,25,barcode_type='hibcdatamatrix')
            obj['barcode_options'].update(human_readable=True,hibc_input_mode='complete')
            image=_render_engine_barcode_box('hibcdatamatrix',value,mm_to_dots(55,203),mm_to_dots(25,203),dict(obj,_render_dpi=203))
            image.save(output_dir/'manager-verified-hibc.png')
            check('encoded payload and HRI retain checksum',image.info['encoded_value']==value and image.info['hri_value'].endswith('_'))
            app.destroy();app=None
            report.update(passed=True,status='passed',check_count=len(report['checks']),encoded_bytes=value.encode('ascii').hex())
    except (ValueError,AssertionError,StopIteration,tk.TclError,OSError) as exc:
        report.update(status='failed',error=str(exc),check_count=len(report['checks']))
    finally:
        if app is not None:
            app.destroy()
        (output_dir/'manager-workflow-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['passed'] else 1
