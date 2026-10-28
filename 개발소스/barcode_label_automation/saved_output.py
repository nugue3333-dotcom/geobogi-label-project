"""Prepare a complete saved-design job before any printer transmission."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .data_store import load_db_source
from .excel_reader import LabelRow
from .job_profile import file_fingerprint
from .print_quantity import parse_print_quantity
from .print_progress import DESIGNER_PROGRESS_FILE_NAME, NewPrintJobRequired, PrintProgress, UnknownPrintItemsError
from .template_output import render_command, validate_rows, template_digest
from .value_rules import compile_generated_labels
from .value_jobs import ValueJobStore, effective_job_rules


def prepare_saved_output(args, config, *, dry_run: bool):
    from .label_designer_app import load_template_file, _designer_print_job_context
    source = Path(args.template).resolve()
    if args.template_hash and file_fingerprint(source) != args.template_hash:
        raise ValueError("출력 도안이 변경되었습니다. 도안을 다시 선택하고 검증하세요.")
    template = load_template_file(source)
    label = template["label"]
    if float(label["width_mm"]) != config.label.width_mm or float(label["height_mm"]) != config.label.height_mm:
        raise ValueError("도안과 공유 용지 설정의 크기가 다릅니다. 용지 설정과 실제 라벨을 확인하세요.")
    base_dir = Path(args.config).resolve().parent
    rules = template.get("value_rules", [])
    copies_per_serial = getattr(args, "copies_per_serial", None)
    effective_rules = effective_job_rules(rules, copies_per_serial)
    key = str(template.get("value_profile_id") or source)
    context = _designer_print_job_context(config)
    store = ValueJobStore(base_dir)
    if args.value_job:
        job = store.load_job(args.value_job)
        if job.template_key != key:
            raise ValueError("재인쇄 기록의 도안이 다릅니다. 원래 도안을 선택하세요.")
        recorded_hash = job.context.get("template_digest") or job.context.get("template_hash")
        current_hash = template_digest(template) if job.context.get("template_digest") else file_fingerprint(source)
        if recorded_hash and recorded_hash != current_hash:
            raise ValueError("재인쇄 기록 이후 도안이 변경되었습니다. 원래 버전의 도안을 복원하세요.")
        generated = job.labels
    else:
        if getattr(args, "no_data", False):
            rows = [{}]
        else:
            if not config.data.excel_file.is_file():
                raise FileNotFoundError("출력 데이터 엑셀을 찾을 수 없습니다. 다시 연결하세요.")
            rows, _headers = load_db_source(config.data.excel_file)
        if args.limit:
            rows = rows[:args.limit]
        quantities = [parse_print_quantity(args.force_print_qty if args.force_print_qty is not None else row.get("print_qty", "1") or "1") for row in rows]
        request = {"template": template, "rows": rows, "quantities": quantities, "printer": context}
        if copies_per_serial is not None:
            request["copies_per_serial"] = copies_per_serial
        request_key = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        job = None
        progress_path = config.data.output_dir / DESIGNER_PROGRESS_FILE_NAME
        progress = PrintProgress.load(progress_path) if rules and not dry_run and progress_path.exists() else None
        if progress and progress.unknown_indexes:
            raise UnknownPrintItemsError(progress.unknown_indexes)
        if rules and not getattr(args, "new_job", False):
            latest = store.latest_job(key)
            if latest and latest.request_key == request_key:
                if not progress_path.exists():
                    job = latest
                elif progress is not None:
                    if (progress.pending_indexes or progress.unknown_indexes) and progress.context.get("snapshot_id") == latest.snapshot_id:
                        job = latest
            # Opening print progress happens after value reservation in the CLI.
            # Detect a conflicting previous job before consuming any new numbers.
            if progress is not None and job is None:
                raise NewPrintJobRequired()
        generated = job.labels if job else compile_generated_labels(rows, quantities, effective_rules, start_overrides=store.peek_start_overrides(key, rules))
    issues = validate_rows(template, [item.row for item in generated], base_dir, dpi=config.label.dpi)
    if issues:
        message = "\n".join(f"{item.row}행 · {item.element}번 개체: {item.message}" for item in issues[:50])
        raise ValueError(f"출력 전 검증에서 수정할 항목 {len(issues)}건 발견. 전송하지 않았습니다.\n{message}")
    if rules and not dry_run and not args.value_job:
        if job is None:
            job = store.prepare_job(rows, quantities, rules, template_key=key,
                                    context={"request_key": request_key, "template_digest": template_digest(template)},
                                    copies_per_serial=copies_per_serial)
        generated = job.labels
    commands = [render_command(template, item.row, config, base_dir, item.copies) for item in generated]
    labels = [LabelRow(item_code=str(item.row.get("item_code", "")), item_name=str(item.row.get("item_name", "")),
                       barcode=str(item.row.get("barcode", "")), lot_no=str(item.row.get("lot_no", "")),
                       qty=1, print_qty=item.copies) for item in generated]
    if job:
        context["snapshot_id"] = job.snapshot_id
        print(f"값 발급 작업 기록: {job.snapshot_id} · 기준일 {job.job_date}")
    return labels, commands, context
