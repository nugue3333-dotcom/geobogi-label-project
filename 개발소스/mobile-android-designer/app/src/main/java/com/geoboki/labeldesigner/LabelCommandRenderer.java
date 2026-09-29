package com.geoboki.labeldesigner;

import java.util.Locale;

final class LabelCommandRenderer {
    private LabelCommandRenderer() {}

    static RenderedCommand render(PrinterSettings settings, LabelTemplate template) {
        validate(settings, template);
        if (PrinterSettings.BRAND_BIXOLON.equals(settings.brand)) {
            return new RenderedCommand(renderSlcs(settings, template), "CP949");
        }
        if (PrinterSettings.BRAND_TSC.equals(settings.brand)) {
            return new RenderedCommand(renderTspl(settings, template), "UTF-8");
        }
        if (PrinterSettings.BRAND_ZEBRA.equals(settings.brand)) {
            return new RenderedCommand(renderZpl(settings, template), "UTF-8");
        }
        if (PrinterSettings.BRAND_SEWOO.equals(settings.brand)) {
            throw new IllegalArgumentException("SEWOO는 승인 모델과 공식 명령 문서가 등록되지 않아 실제 출력을 차단했습니다.");
        }
        throw new IllegalArgumentException("지원하지 않는 프린터 브랜드입니다.");
    }

    static int mmToDots(float mm, int dpi) {
        return Math.round(mm / 25.4f * dpi);
    }

    private static void validate(PrinterSettings settings, LabelTemplate template) {
        if (template.elements.isEmpty()) throw new IllegalArgumentException("라벨에 객체를 먼저 추가하세요.");
        if (settings.dpi != 203 && settings.dpi != 300 && settings.dpi != 600) {
            throw new IllegalArgumentException("DPI는 203, 300, 600 중 하나여야 합니다.");
        }
        if (settings.printQty < 1 || settings.printQty > 100) {
            throw new IllegalArgumentException("출력 매수는 1부터 100 사이여야 합니다.");
        }
        if (PrinterSettings.BRAND_BIXOLON.equals(settings.brand)
                && PrinterSettings.ACTION_PEEL.equals(settings.afterPrint)) {
            throw new IllegalArgumentException("BIXOLON SLCS 필러 명령은 지원하지 않습니다. 뜯어내기 또는 커터를 선택하세요.");
        }
        if (PrinterSettings.BRAND_SEWOO.equals(settings.brand)
                && !PrinterSettings.ACTION_TEAR.equals(settings.afterPrint)) {
            throw new IllegalArgumentException("SEWOO는 승인된 모델별 커터/필러 근거가 없어 모바일에서는 뜯어내기만 지원합니다.");
        }
    }

    private static String renderTspl(PrinterSettings settings, LabelTemplate template) {
        StringBuilder c = new StringBuilder();
        c.append("SIZE ").append(formatMm(template.widthMm)).append(" mm,")
                .append(formatMm(template.heightMm)).append(" mm\n");
        c.append(tsplMedia(settings.mediaType));
        c.append("CODEPAGE UTF-8\nDENSITY 8\nSPEED 4\nDIRECTION 1\nREFERENCE 0,0\nCLS\n");
        for (LabelElement e : template.elements) appendTsplElement(c, settings, e);
        c.append(tsplAfter(settings.afterPrint));
        c.append("PRINT 1,").append(settings.printQty).append("\n");
        return c.toString().replace("\n", "\r\n");
    }

    private static void appendTsplElement(StringBuilder c, PrinterSettings s, LabelElement e) {
        int x = mmToDots(e.xMm, s.dpi);
        int y = mmToDots(e.yMm, s.dpi);
        if (LabelElement.TYPE_TEXT.equals(e.type)) {
            c.append("TEXT ").append(x).append(',').append(y).append(",\"")
                    .append(tsplFont(e.textSizeMm)).append("\",").append(e.rotation)
                    .append(",1,1,\"").append(sanitizeTspl(e.value)).append("\"\n");
        } else if (LabelElement.TYPE_BARCODE.equals(e.type)) {
            String value = sanitizeBarcode(e.value);
            int module = code128ModuleWidth(value, mmToDots(e.widthMm, s.dpi));
            c.append("BARCODE ").append(x).append(',').append(y).append(",\"128\",")
                    .append(mmToDots(e.heightMm, s.dpi)).append(",1,").append(e.rotation)
                    .append(',').append(module).append(',').append(Math.max(2, module * 2)).append(",\"")
                    .append(value).append("\"\n");
        } else if (LabelElement.TYPE_QR.equals(e.type)) {
            c.append("QRCODE ").append(x).append(',').append(y).append(",L,")
                    .append(qrCellSize(e, s.dpi)).append(",A,")
                    .append(e.rotation).append(",M2,S7,\"").append(sanitizeTspl(e.value)).append("\"\n");
        } else if (LabelElement.TYPE_BOX.equals(e.type)) {
            c.append("BOX ").append(x).append(',').append(y).append(',')
                    .append(mmToDots(e.xMm + e.widthMm, s.dpi)).append(',')
                    .append(mmToDots(e.yMm + e.heightMm, s.dpi)).append(',')
                    .append(Math.max(1, mmToDots(e.strokeMm, s.dpi))).append("\n");
        } else if (LabelElement.TYPE_LINE.equals(e.type)) {
            int w = e.rotation == 90 || e.rotation == 270 ? Math.max(1, mmToDots(e.strokeMm, s.dpi)) : mmToDots(e.widthMm, s.dpi);
            int h = e.rotation == 90 || e.rotation == 270 ? mmToDots(e.widthMm, s.dpi) : Math.max(1, mmToDots(e.strokeMm, s.dpi));
            c.append("BAR ").append(x).append(',').append(y).append(',').append(w).append(',').append(h).append("\n");
        }
    }

    private static String renderZpl(PrinterSettings settings, LabelTemplate template) {
        StringBuilder c = new StringBuilder("^XA\n^CI28\n");
        c.append(zplAfter(settings.afterPrint)).append(zplMedia(settings.mediaType));
        c.append("^PW").append(mmToDots(template.widthMm, settings.dpi)).append("\n");
        c.append("^LL").append(mmToDots(template.heightMm, settings.dpi)).append("\n");
        for (LabelElement e : template.elements) appendZplElement(c, settings, e);
        c.append("^PQ").append(settings.printQty).append("\n^XZ\n");
        return c.toString();
    }

    private static void appendZplElement(StringBuilder c, PrinterSettings s, LabelElement e) {
        int x = mmToDots(e.xMm, s.dpi);
        int y = mmToDots(e.yMm, s.dpi);
        String o = zplOrientation(e.rotation);
        if (LabelElement.TYPE_TEXT.equals(e.type)) {
            int size = Math.max(14, mmToDots(e.textSizeMm, s.dpi));
            c.append("^FO").append(x).append(',').append(y).append("^A0").append(o).append(',')
                    .append(size).append(',').append(size).append("^FD").append(sanitizeZpl(e.value)).append("^FS\n");
        } else if (LabelElement.TYPE_BARCODE.equals(e.type)) {
            String value = sanitizeBarcode(e.value);
            int height = Math.max(12, mmToDots(e.heightMm, s.dpi));
            int module = code128ModuleWidth(value, mmToDots(e.widthMm, s.dpi));
            c.append("^FO").append(x).append(',').append(y).append("^BY").append(module).append(",2,")
                    .append(height).append("^BC").append(o).append(',').append(height)
                    .append(",Y,N,N^FD").append(value).append("^FS\n");
        } else if (LabelElement.TYPE_QR.equals(e.type)) {
            if (e.rotation != 0) {
                throw new IllegalArgumentException("Zebra QR 코드는 공식 명령 기준으로 0도 회전만 지원합니다.");
            }
            c.append("^FO").append(x).append(',').append(y).append("^BQ").append(o).append(",2,")
                    .append(qrCellSize(e, s.dpi)).append("^FDLA,")
                    .append(sanitizeZpl(e.value)).append("^FS\n");
        } else if (LabelElement.TYPE_BOX.equals(e.type)) {
            c.append("^FO").append(x).append(',').append(y).append("^GB")
                    .append(mmToDots(e.widthMm, s.dpi)).append(',').append(mmToDots(e.heightMm, s.dpi)).append(',')
                    .append(Math.max(1, mmToDots(e.strokeMm, s.dpi))).append("^FS\n");
        } else if (LabelElement.TYPE_LINE.equals(e.type)) {
            int w = e.rotation == 90 || e.rotation == 270 ? Math.max(1, mmToDots(e.strokeMm, s.dpi)) : mmToDots(e.widthMm, s.dpi);
            int h = e.rotation == 90 || e.rotation == 270 ? mmToDots(e.widthMm, s.dpi) : Math.max(1, mmToDots(e.strokeMm, s.dpi));
            c.append("^FO").append(x).append(',').append(y).append("^GB").append(w).append(',').append(h).append(',').append(Math.min(w, h)).append("^FS\n");
        }
    }

    private static String renderSlcs(PrinterSettings settings, LabelTemplate template) {
        StringBuilder c = new StringBuilder("CB\nSS3\nSD20\nCS13,0\nSTd\n");
        c.append("SW").append(mmToDots(template.widthMm, settings.dpi)).append("\n");
        int height = mmToDots(template.heightMm, settings.dpi);
        int gap = mmToDots(3f, settings.dpi);
        if (PrinterSettings.MEDIA_BLACK_MARK.equals(settings.mediaType)) c.append("SL").append(height).append(',').append(gap).append(",B\n");
        else if (PrinterSettings.MEDIA_CONTINUOUS.equals(settings.mediaType)) c.append("SL").append(height).append(",0,C\n");
        else c.append("SL").append(height).append(',').append(gap).append(",G\n");
        c.append("SOT\n");
        for (LabelElement e : template.elements) appendSlcsElement(c, settings, e);
        c.append(PrinterSettings.ACTION_CUT.equals(settings.afterPrint) ? "CUTy\n" : "CUTn\n");
        return c.toString().replace("\n", "\r\n") + "P" + settings.printQty + "\r";
    }

    private static void appendSlcsElement(StringBuilder c, PrinterSettings s, LabelElement e) {
        int x = mmToDots(e.xMm, s.dpi);
        int y = mmToDots(e.yMm, s.dpi);
        if (LabelElement.TYPE_TEXT.equals(e.type)) {
            c.append('T').append(x).append(',').append(y).append(",c,1,1,").append(slcsRotation(e.rotation))
                    .append(",0,N,N,'").append(sanitizeSlcs(e.value)).append("'\n");
        } else if (LabelElement.TYPE_BARCODE.equals(e.type)) {
            String value = sanitizeBarcode(e.value);
            int module = code128ModuleWidth(value, mmToDots(e.widthMm, s.dpi));
            c.append("B1").append(x).append(',').append(y).append(",1,")
                    .append(module).append(',').append(Math.max(2, module * 3)).append(',')
                    .append(Math.max(12, mmToDots(e.heightMm, s.dpi))).append(',')
                    .append(slcsRotation(e.rotation)).append(",1,'").append(value).append("'\n");
        } else if (LabelElement.TYPE_QR.equals(e.type)) {
            c.append("B2").append(x).append(',').append(y).append(",Q,2,M,")
                    .append(qrCellSize(e, s.dpi)).append(',').append(slcsRotation(e.rotation)).append(",'")
                    .append(sanitizeSlcs(e.value)).append("'\n");
        } else if (LabelElement.TYPE_BOX.equals(e.type)) {
            c.append("R").append(x).append(',').append(y).append(',')
                    .append(mmToDots(e.xMm + e.widthMm, s.dpi)).append(',')
                    .append(mmToDots(e.yMm + e.heightMm, s.dpi)).append(',')
                    .append(Math.max(1, mmToDots(e.strokeMm, s.dpi))).append("\n");
        } else if (LabelElement.TYPE_LINE.equals(e.type)) {
            int x2 = x + (e.rotation == 90 || e.rotation == 270 ? 0 : mmToDots(e.widthMm, s.dpi));
            int y2 = y + (e.rotation == 90 || e.rotation == 270 ? mmToDots(e.widthMm, s.dpi) : 0);
            c.append("L").append(x).append(',').append(y).append(',').append(x2).append(',').append(y2).append(',')
                    .append(Math.max(1, mmToDots(e.strokeMm, s.dpi))).append("\n");
        }
    }

    private static String tsplMedia(String type) {
        if (PrinterSettings.MEDIA_BLACK_MARK.equals(type)) return "BLINE 3 mm,0 mm\n";
        if (PrinterSettings.MEDIA_CONTINUOUS.equals(type)) return "GAP 0,0\n";
        return "GAP 3 mm,0 mm\n";
    }

    private static String tsplAfter(String action) {
        if (PrinterSettings.ACTION_CUT.equals(action)) return "SET PEEL OFF\nSET CUTTER 1\n";
        if (PrinterSettings.ACTION_PEEL.equals(action)) return "SET CUTTER OFF\nSET PEEL ON\n";
        return "SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n";
    }

    private static String zplMedia(String type) {
        if (PrinterSettings.MEDIA_BLACK_MARK.equals(type)) return "^MNM,0\n";
        if (PrinterSettings.MEDIA_CONTINUOUS.equals(type)) return "^MNN\n";
        return "^MNY\n";
    }

    private static String zplAfter(String action) {
        if (PrinterSettings.ACTION_CUT.equals(action)) return "^MMC\n";
        if (PrinterSettings.ACTION_PEEL.equals(action)) return "^MMP\n";
        return "^MMT\n";
    }

    private static String zplOrientation(int rotation) {
        if (rotation == 90) return "R";
        if (rotation == 180) return "I";
        if (rotation == 270) return "B";
        return "N";
    }

    private static int slcsRotation(int rotation) {
        if (rotation == 90) return 1;
        if (rotation == 180) return 2;
        if (rotation == 270) return 3;
        return 0;
    }

    private static int code128ModuleWidth(String value, int availableDots) {
        int modules = Math.max(1, value.length() * 11 + 35);
        return Math.max(1, Math.min(10, availableDots / modules));
    }

    private static int qrCellSize(LabelElement element, int dpi) {
        int available = Math.min(mmToDots(element.widthMm, dpi), mmToDots(element.heightMm, dpi));
        return Math.max(1, Math.min(10, available / 29));
    }

    private static String tsplFont(float size) { return size >= 5.5f ? "4" : size >= 4f ? "3" : "2"; }
    private static String sanitizeBarcode(String value) {
        String text = value == null ? "" : value.trim();
        rejectUnresolvedField(text, "바코드");
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch >= 32 && ch <= 126) result.append(ch);
        }
        if (result.length() == 0) throw new IllegalArgumentException("바코드 값이 비어 있습니다.");
        return result.toString();
    }
    private static String sanitizeTspl(String v) {
        String text = safe(v);
        rejectUnresolvedField(text, "QR 코드");
        return text.replace("\"", "");
    }
    private static String sanitizeZpl(String v) {
        String text = safe(v);
        rejectUnresolvedField(text, "QR 코드");
        return text.replace("^", "").replace("~", "");
    }
    private static String sanitizeSlcs(String v) {
        String text = safe(v);
        rejectUnresolvedField(text, "QR 코드");
        return text.replace("'", "");
    }
    private static void rejectUnresolvedField(String value, String objectName) {
        if (value.contains("{{") || value.contains("}}")) {
            throw new IllegalArgumentException(objectName + "에 연결되지 않은 데이터 열이 있습니다: " + value);
        }
    }
    private static String safe(String v) { return v == null ? "" : v.trim(); }
    private static String formatMm(float v) {
        return v == Math.round(v) ? String.format(Locale.US, "%d", Math.round(v)) : String.format(Locale.US, "%.2f", v);
    }
}
