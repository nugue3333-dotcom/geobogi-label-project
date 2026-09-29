package com.geoboki.labeldesigner;

import java.util.UUID;

final class LabelElement {
    static final String TYPE_TEXT = "text";
    static final String TYPE_BARCODE = "barcode";
    static final String TYPE_QR = "qr";
    static final String TYPE_BOX = "box";
    static final String TYPE_LINE = "line";

    String id;
    String type;
    String sourceType;
    String field;
    String value;
    float xMm;
    float yMm;
    float widthMm;
    float heightMm;
    float textSizeMm;
    int rotation;
    float strokeMm;

    LabelElement(String id, String type, String value, float xMm, float yMm,
                 float widthMm, float heightMm, float textSizeMm, int rotation, float strokeMm) {
        this.id = id == null || id.isEmpty() ? UUID.randomUUID().toString() : id;
        this.type = type;
        this.sourceType = type;
        this.field = "";
        this.value = value == null ? "" : value;
        this.xMm = xMm;
        this.yMm = yMm;
        this.widthMm = widthMm;
        this.heightMm = heightMm;
        this.textSizeMm = textSizeMm;
        this.rotation = normalizeRotation(rotation);
        this.strokeMm = strokeMm;
    }

    static LabelElement text(String value, float xMm, float yMm) {
        return create(TYPE_TEXT, value, xMm, yMm);
    }

    static LabelElement barcode(String value, float xMm, float yMm) {
        return create(TYPE_BARCODE, value, xMm, yMm);
    }

    static LabelElement qr(String value, float xMm, float yMm) {
        return create(TYPE_QR, value, xMm, yMm);
    }

    static LabelElement box(float xMm, float yMm) {
        return create(TYPE_BOX, "", xMm, yMm);
    }

    static LabelElement line(float xMm, float yMm) {
        return create(TYPE_LINE, "", xMm, yMm);
    }

    private static LabelElement create(String type, String value, float xMm, float yMm) {
        if (TYPE_BARCODE.equals(type)) {
            return new LabelElement(null, type, value, xMm, yMm, 38f, 13f, 3f, 0, 0.4f);
        }
        if (TYPE_QR.equals(type)) {
            return new LabelElement(null, type, value, xMm, yMm, 18f, 18f, 3f, 0, 0.4f);
        }
        if (TYPE_BOX.equals(type)) {
            return new LabelElement(null, type, value, xMm, yMm, 30f, 15f, 3f, 0, 0.4f);
        }
        if (TYPE_LINE.equals(type)) {
            return new LabelElement(null, type, value, xMm, yMm, 30f, 1f, 3f, 0, 0.4f);
        }
        return new LabelElement(null, TYPE_TEXT, value, xMm, yMm, 34f, 7f, 4f, 0, 0.4f);
    }

    LabelElement copyOffset() {
        LabelElement copy = new LabelElement(null, type, value, xMm + 3f, yMm + 3f,
                widthMm, heightMm, textSizeMm, rotation, strokeMm);
        copy.sourceType = sourceType;
        copy.field = field;
        return copy;
    }

    void clamp(float labelWidthMm, float labelHeightMm) {
        float minWidth = TYPE_QR.equals(type) ? 8f : TYPE_LINE.equals(type) ? 4f : 6f;
        float minHeight = TYPE_QR.equals(type) ? 8f : TYPE_LINE.equals(type) ? 0.3f : 4f;
        widthMm = Math.max(minWidth, widthMm);
        heightMm = Math.max(minHeight, heightMm);
        xMm = Math.max(0f, Math.min(xMm, Math.max(0f, labelWidthMm - widthMm)));
        yMm = Math.max(0f, Math.min(yMm, Math.max(0f, labelHeightMm - heightMm)));
        textSizeMm = Math.max(1.5f, Math.min(textSizeMm, 12f));
        strokeMm = Math.max(0.1f, Math.min(strokeMm, 3f));
        rotation = normalizeRotation(rotation);
    }

    static int normalizeRotation(int value) {
        int normalized = ((value % 360) + 360) % 360;
        if (normalized < 45) return 0;
        if (normalized < 135) return 90;
        if (normalized < 225) return 180;
        if (normalized < 315) return 270;
        return 0;
    }
}
