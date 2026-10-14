"""Real DB → inline edit → selected row → saved queue acceptance."""
import json
from pathlib import Path
import zxingcpp
from PIL import Image
from barcode_label_automation.workflow_probe import run_manager_workflow_probe

def test_actual_manager_preserves_complete_hibc_space_into_queue(tmp_path):
    assert run_manager_workflow_probe(tmp_path)==0
    result=json.loads((tmp_path/"manager-workflow-result.json").read_text(encoding="utf-8"))
    assert result["passed"] and result["check_count"]==11
    decoded=zxingcpp.read_barcode(Image.open(tmp_path/"manager-verified-hibc.png").convert("L"))
    assert decoded and decoded.bytes.hex()==result["encoded_bytes"]
