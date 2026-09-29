package com.geoboki.labeldesigner;

import java.util.ArrayList;
import java.util.List;

final class LabelTemplate {
    float widthMm = 58f;
    float heightMm = 40f;
    final List<LabelElement> elements = new ArrayList<>();
    String selectedId;

    LabelElement add(String type, String value) {
        float offset = Math.min(12f, elements.size() * 2f);
        LabelElement element;
        if (LabelElement.TYPE_BARCODE.equals(type)) element = LabelElement.barcode(value, 8f, 10f + offset);
        else if (LabelElement.TYPE_QR.equals(type)) element = LabelElement.qr(value, 8f, 10f + offset);
        else if (LabelElement.TYPE_BOX.equals(type)) element = LabelElement.box(5f, 5f + offset);
        else if (LabelElement.TYPE_LINE.equals(type)) element = LabelElement.line(5f, 8f + offset);
        else element = LabelElement.text(value, 5f, 5f + offset);
        elements.add(element);
        selectedId = element.id;
        normalize();
        return element;
    }

    LabelElement addText(String value) { return add(LabelElement.TYPE_TEXT, value); }
    LabelElement addBarcode(String value) { return add(LabelElement.TYPE_BARCODE, value); }
    LabelElement addQr(String value) { return add(LabelElement.TYPE_QR, value); }
    LabelElement addBox() { return add(LabelElement.TYPE_BOX, ""); }
    LabelElement addLine() { return add(LabelElement.TYPE_LINE, ""); }

    LabelElement selected() {
        if (selectedId == null) return null;
        for (LabelElement element : elements) if (element.id.equals(selectedId)) return element;
        return null;
    }

    void clear() {
        elements.clear();
        selectedId = null;
    }

    void replaceWith(LabelTemplate source) {
        widthMm = source.widthMm;
        heightMm = source.heightMm;
        elements.clear();
        elements.addAll(source.elements);
        selectedId = null;
        normalize();
    }

    void deleteSelected() {
        if (selectedId == null) return;
        elements.removeIf(item -> item.id.equals(selectedId));
        selectedId = null;
    }

    void duplicateSelected() {
        LabelElement selected = selected();
        if (selected == null) return;
        LabelElement copy = selected.copyOffset();
        elements.add(copy);
        selectedId = copy.id;
        normalize();
    }

    void centerSelected() {
        LabelElement selected = selected();
        if (selected == null) return;
        selected.xMm = (widthMm - selected.widthMm) / 2f;
        selected.clamp(widthMm, heightMm);
    }

    void resize(float widthMm, float heightMm) {
        this.widthMm = Math.max(10f, Math.min(widthMm, 300f));
        this.heightMm = Math.max(10f, Math.min(heightMm, 300f));
        normalize();
    }

    void normalize() {
        for (LabelElement element : elements) element.clamp(widthMm, heightMm);
    }
}
