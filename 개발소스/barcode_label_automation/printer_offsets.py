"""Manufacturer media offsets, separate from the host image position.

References: SLCS X-series pp.48,57; Zebra ZPL guide p.324; TSPL OFFSET.
No transport or printer settings writes happen in this module.
"""
from __future__ import annotations

import math


def offset_dots(mm: float, dpi: int) -> int:
    return round(float(mm) * dpi / 25.4)


def zebra_tear_steps(mm: float, dpi: int) -> int:
    # The ZPL ~TA step is two dot rows on 600 dpi heads (guide p.324).
    return round(float(mm) * dpi / 25.4 / (2 if dpi == 600 else 1))


def validate_offsets(language, media_type, height_mm, dpi, gap_offset, feed_offset,
                     *, brand=None, model="") -> None:
    for value in (gap_offset, feed_offset):
        if value is not None and (isinstance(value, bool) or not math.isfinite(float(value))):
            raise ValueError("고급 보정은 유한한 숫자 또는 현재 프린터 설정 사용을 선택하세요.")
    if gap_offset is not None:
        if language == "slcs":
            # SL p4 is the physical mark-to-perforation distance. Its range is
            # independent of SA/TA's ±100-dot ranges. The checked manual gives
            # a 200-dot p4 example but no p4 maximum; the app applies a
            # conservative one-label/page-length bound, not a vendor limit.
            p4_limit = min(round(float(height_mm) * dpi / 25.4), 2432)
            requested = abs(offset_dots(gap_offset, dpi))
            if requested > p4_limit:
                limit_mm = p4_limit * 25.4 / dpi
                raise ValueError(
                    f"마크와 절취선 거리는 용지 길이 이내로 입력하세요(현재 최대 {limit_mm:.2f}mm)."
                )
            if media_type == "continuous" and gap_offset:
                raise ValueError("연속 용지는 센서·절취선 보정을 사용할 수 없습니다. 현재 프린터 설정 사용으로 두세요.")
        elif language == "tspl":
            if media_type == "continuous" and gap_offset != 0:
                raise ValueError("연속 용지는 추가 이송을 사용할 수 없습니다.")
            if media_type != "continuous" and not 0 <= gap_offset <= height_mm:
                raise ValueError("갭·블랙마크 추가 이송은 0~용지 길이 사이여야 합니다.")
        elif gap_offset:
            raise ValueError("이 제조사의 센서 보정은 현재 프린터 설정 사용으로 두세요. 내용 위치는 좌우·상하 보정으로 조정합니다.")
    if feed_offset is None:
        return
    if brand == "sewoo":
        raise ValueError("세우테크 배출 보정은 모델별 명령 확인이 필요합니다. 현재 프린터 설정 사용으로 두세요.")
    if language == "slcs":
        if abs(float(feed_offset) * dpi / 25.4) > 100 + 1e-9:
            raise ValueError(f"빅솔론 TA 절취·커터 정지 보정은 ±100도트(현재 DPI에서 ±{100*25.4/dpi:.3f}mm) 이내로 입력하세요.")
    elif language == "tspl":
        if abs(feed_offset) > 25.4:
            raise ValueError("TSC 공급 오프셋은 -25.4~25.4mm 범위여야 합니다.")
    elif language == "zpl":
        steps = float(feed_offset) * dpi / 25.4 / (2 if dpi == 600 else 1)
        if abs(steps) > 120 + 1e-9:
            raise ValueError("Zebra 배출 보정은 -120~120단계 이내로 입력하세요. 600 DPI는 1단계가 2도트입니다.")
        if str(model).upper().replace(" ", "").startswith("HC100") and feed_offset < 0:
            raise ValueError("Zebra HC100 배출 보정은 0~120단계만 지원합니다.")
    else:
        raise ValueError("지원하지 않는 제조사 보정 명령입니다.")


def slcs_media_commands(height, gap, media_type, dpi, gap_offset=None, feed_offset=None):
    validate_offsets("slcs", media_type, height * 25.4 / dpi, dpi, gap_offset, feed_offset)
    kind = {"gap": "G", "black_mark": "B", "continuous": "C"}.get(media_type)
    if kind is None:
        raise ValueError("지원하지 않는 용지 종류입니다.")
    command = f"SL{height},{0 if kind == 'C' else gap},{kind}"
    if gap_offset is not None and kind != "C":
        # SL p4 applies the sensor/perforation offset without SA's permanent save.
        command += f",{offset_dots(gap_offset, dpi)}"
    command += "\n"
    if kind in {"G", "B"} and gap_offset is not None:
        # Explicit media-distance settings also enable documented back-feed
        # before the next print. None retains the device's existing sequence.
        command += "SF1\n"
    if feed_offset is not None:
        # TA is absolute and permanently stored by the printer, as the UI states.
        command += f"TA{offset_dots(feed_offset, dpi)}\n"
    return command


def zebra_feed_command(dpi, feed_offset=None, *, brand=None, model=""):
    validate_offsets("zpl", "gap", 300, dpi, None, feed_offset, brand=brand, model=model)
    if feed_offset is None:
        return ""
    value = zebra_tear_steps(feed_offset, dpi)
    # At least three magnitude digits are required; keep an explicit minus sign.
    return f"~TA{'-' if value < 0 else ''}{abs(value):03d}\n"
