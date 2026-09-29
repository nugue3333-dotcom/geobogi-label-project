from barcode_label_automation.ui_window import WorkArea, calculate_window_placement


def test_window_placement_uses_preferred_size_inside_work_area() -> None:
    placement = calculate_window_placement(
        WorkArea(0, 0, 1920, 1040),
        preferred_width=1400,
        preferred_height=860,
        minimum_width=1060,
        minimum_height=680,
    )

    assert (placement.width, placement.height) == (1400, 860)
    assert placement.x >= 0
    assert placement.y >= 0
    assert placement.x + placement.width <= 1920
    assert placement.y + placement.height <= 1040


def test_window_placement_shrinks_to_laptop_work_area_without_clipping() -> None:
    placement = calculate_window_placement(
        WorkArea(0, 0, 1366, 728),
        preferred_width=1480,
        preferred_height=920,
        minimum_width=1100,
        minimum_height=680,
    )

    assert (placement.width, placement.height) == (1318, 680)
    assert placement.minimum_width == 1100
    assert placement.minimum_height == 680
    assert placement.x + placement.width <= 1366
    assert placement.y + placement.height <= 728


def test_window_placement_reduces_minimum_on_small_work_area() -> None:
    placement = calculate_window_placement(
        WorkArea(0, 0, 900, 650),
        preferred_width=1360,
        preferred_height=920,
        minimum_width=980,
        minimum_height=680,
    )

    assert (placement.width, placement.height) == (852, 602)
    assert placement.minimum_width == 852
    assert placement.minimum_height == 602
    assert placement.geometry.startswith("852x602+")
