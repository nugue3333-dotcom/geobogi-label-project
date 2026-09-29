package com.geoboki.labeldesigner;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.Map;

final class TemplateJson {
    private TemplateJson() {}

    static String encode(LabelTemplate template) throws JSONException {
        JSONObject root = new JSONObject();
        root.put("format", "chaeumlab-label-template");
        root.put("version", 1);
        root.put("width_mm", template.widthMm);
        root.put("height_mm", template.heightMm);
        JSONObject label = new JSONObject();
        label.put("width_mm", template.widthMm);
        label.put("height_mm", template.heightMm);
        root.put("label", label);
        JSONArray elements = new JSONArray();
        for (LabelElement item : template.elements) {
            JSONObject value = new JSONObject();
            value.put("id", item.id);
            value.put("type", item.sourceType == null ? item.type : item.sourceType);
            if (LabelElement.TYPE_BARCODE.equals(item.type)) value.put("barcode_type", "code128");
            if (LabelElement.TYPE_QR.equals(item.type)) value.put("barcode_type", "qr");
            value.put("value", item.value);
            value.put("text", item.value);
            value.put("field", item.field);
            value.put("x_mm", item.xMm);
            value.put("y_mm", item.yMm);
            value.put("width_mm", item.widthMm);
            value.put("height_mm", item.heightMm);
            value.put("x", item.xMm);
            value.put("y", item.yMm);
            value.put("width", item.widthMm);
            value.put("height", item.heightMm);
            value.put("text_size_mm", item.textSizeMm);
            value.put("rotation", item.rotation);
            value.put("stroke_mm", item.strokeMm);
            elements.put(value);
        }
        root.put("elements", elements);
        return root.toString(2);
    }

    static LabelTemplate decode(String json) throws JSONException {
        JSONObject root = new JSONObject(json);
        LabelTemplate template = new LabelTemplate();
        JSONObject label = root.optJSONObject("label");
        template.widthMm = (float) (label == null ? root.optDouble("width_mm", 58) : label.optDouble("width_mm", 58));
        template.heightMm = (float) (label == null ? root.optDouble("height_mm", 40) : label.optDouble("height_mm", 40));
        JSONArray elements = root.optJSONArray("elements");
        if (elements != null) {
            for (int i = 0; i < elements.length(); i++) {
                JSONObject item = elements.getJSONObject(i);
                String sourceType = item.optString("type", "text");
                String type = normalizeType(sourceType, item.optString("barcode_type"));
                String text = item.has("text") ? item.optString("text") : item.optString("value");
                String field = item.optString("field");
                if (text.isEmpty() && !field.isEmpty()) text = "{{" + field + "}}";
                LabelElement element = new LabelElement(
                        item.optString("id"), type, text,
                        number(item, "x_mm", "x", 5), number(item, "y_mm", "y", 5),
                        number(item, "width_mm", "width", 20), number(item, "height_mm", "height", 5),
                        (float) item.optDouble("text_size_mm", Math.max(1.5, item.optDouble("font_size", 10) * 0.35)),
                        item.optInt("rotation", 0),
                        (float) item.optDouble("stroke_mm", item.optDouble("stroke_width", 0.4))
                );
                element.sourceType = sourceType;
                element.field = field;
                template.elements.add(element);
            }
        }
        template.normalize();
        return template;
    }

    static LabelTemplate resolve(LabelTemplate source, Map<String, String> row) {
        LabelTemplate resolved = new LabelTemplate();
        resolved.widthMm = source.widthMm;
        resolved.heightMm = source.heightMm;
        for (LabelElement item : source.elements) {
            String value = item.value;
            if (value.isEmpty() && !item.field.isEmpty()) value = "{{" + item.field + "}}";
            for (Map.Entry<String, String> entry : row.entrySet()) {
                value = value.replace("{{" + entry.getKey() + "}}", entry.getValue());
            }
            LabelElement copy = new LabelElement(item.id, item.type, value, item.xMm, item.yMm,
                    item.widthMm, item.heightMm, item.textSizeMm, item.rotation, item.strokeMm);
            copy.sourceType = item.sourceType;
            copy.field = item.field;
            resolved.elements.add(copy);
        }
        resolved.normalize();
        return resolved;
    }

    private static float number(JSONObject value, String mobileKey, String pcKey, double fallback) {
        return (float) (value.has(mobileKey) ? value.optDouble(mobileKey, fallback) : value.optDouble(pcKey, fallback));
    }

    private static String normalizeType(String type, String barcodeType) {
        String normalizedBarcodeType = barcodeType == null ? "" : barcodeType.toLowerCase(java.util.Locale.US);
        if ("barcode".equals(type) && ("qr".equals(normalizedBarcodeType) || "qrcode".equals(normalizedBarcodeType))) {
            return LabelElement.TYPE_QR;
        }
        if ("qrcode".equals(type) || "qr_code".equals(type) || "barcode_2d".equals(type)) {
            return LabelElement.TYPE_QR;
        }
        if ("field".equals(type) || "multiline_text".equals(type)) return LabelElement.TYPE_TEXT;
        if (LabelElement.TYPE_TEXT.equals(type) || LabelElement.TYPE_BARCODE.equals(type)
                || LabelElement.TYPE_QR.equals(type) || LabelElement.TYPE_BOX.equals(type)
                || LabelElement.TYPE_LINE.equals(type)) return type;
        return LabelElement.TYPE_TEXT;
    }
}
