package com.geoboki.labelprinter;

import java.util.Locale;

final class LabelCommandRenderer {
    private LabelCommandRenderer() {
    }

    static RenderedCommand render(PrinterSettings settings, LabelData row) {
        if (PrinterSettings.BRAND_BIXOLON.equals(settings.brand)) {
            return new RenderedCommand(renderSlcs(settings, row), "MS949");
        }
        if (PrinterSettings.BRAND_TSC.equals(settings.brand)) {
            return new RenderedCommand(renderTspl(settings, row), "MS949");
        }
        if (PrinterSettings.BRAND_ZEBRA.equals(settings.brand)) {
            return new RenderedCommand(renderZpl(settings, row), "UTF-8");
        }
        throw new IllegalArgumentException("지원하지 않는 프린터 브랜드입니다.");
    }

    static int mmToDots(float mm, int dpi) {
        return Math.round(mm / 25.4f * dpi);
    }

    private static String renderSlcs(PrinterSettings settings, LabelData row) {
        int widthDot = mmToDots(settings.widthMm, settings.dpi);
        int heightDot = mmToDots(settings.heightMm, settings.dpi);
        int gapDot = mmToDots(settings.gapMm, settings.dpi);

        String itemName = sanitizeSlcs(row.itemName);
        String itemCode = sanitizeSlcs(row.itemCode);
        String barcode = sanitizeBarcode(row.barcode);
        String lotNo = sanitizeSlcs(row.lotNo);

        return "CB\n"
                + "SS3\n"
                + "SD20\n"
                + "CS13,0\n"
                + slcsPrintMethod(settings.printMethod)
                + "SW" + widthDot + "\n"
                + "SL" + heightDot + "," + gapDot + ",G\n"
                + "SOT\n"
                + "T30,30,b,1,1,0,0,N,N,'ITEM: " + itemName + "'\n"
                + "T30,75,c,1,1,0,0,N,N,'CODE: " + itemCode + "'\n"
                + "B130,115,1,2,6,80,0,1,'" + barcode + "'\n"
                + "T30,225,c,1,1,0,0,N,N,'LOT: " + lotNo + " / QTY: " + row.qty + "'\n"
                + "P" + row.printQty + "\n";
    }

    private static String renderTspl(PrinterSettings settings, LabelData row) {
        String itemName = sanitizeTspl(row.itemName);
        String itemCode = sanitizeTspl(row.itemCode);
        String barcode = sanitizeBarcode(row.barcode);
        String lotNo = sanitizeTspl(row.lotNo);

        return "SIZE " + settings.widthMm + " mm," + settings.heightMm + " mm\n"
                + "GAP " + formatMm(settings.gapMm) + " mm,0 mm\n"
                + "CODEPAGE 949\n"
                + "DENSITY 8\n"
                + "SPEED 4\n"
                + tsplPrintMethod(settings.printMethod)
                + "DIRECTION 1\n"
                + "REFERENCE 0,0\n"
                + "CLS\n"
                + "TEXT 30,30,\"3\",0,1,1,\"ITEM: " + itemName + "\"\n"
                + "TEXT 30,75,\"2\",0,1,1,\"CODE: " + itemCode + "\"\n"
                + "BARCODE 130,115,\"128\",80,1,0,2,2,\"" + barcode + "\"\n"
                + "TEXT 30,225,\"2\",0,1,1,\"LOT: " + lotNo + " / QTY: " + row.qty + "\"\n"
                + "PRINT 1," + row.printQty + "\n";
    }

    private static String renderZpl(PrinterSettings settings, LabelData row) {
        int widthDot = mmToDots(settings.widthMm, settings.dpi);
        int heightDot = mmToDots(settings.heightMm, settings.dpi);

        String itemName = sanitizeZpl(row.itemName);
        String itemCode = sanitizeZpl(row.itemCode);
        String barcode = sanitizeBarcode(row.barcode);
        String lotNo = sanitizeZpl(row.lotNo);

        return "^XA\n"
                + "^CI28\n"
                + zplPrintMethod(settings.printMethod)
                + "^PW" + widthDot + "\n"
                + "^LL" + heightDot + "\n"
                + "^FO30,30^A0N,28,28^FDITEM: " + itemName + "^FS\n"
                + "^FO30,75^A0N,24,24^FDCODE: " + itemCode + "^FS\n"
                + "^FO130,115^BY2,2,80^BCN,80,Y,N,N^FD" + barcode + "^FS\n"
                + "^FO30,225^A0N,24,24^FDLOT: " + lotNo + " / QTY: " + row.qty + "^FS\n"
                + "^PQ" + row.printQty + "\n"
                + "^XZ\n";
    }

    private static String slcsPrintMethod(String printMethod) {
        if (PrinterSettings.METHOD_THERMAL_TRANSFER.equals(printMethod)) {
            return "STt\n";
        }
        return "STd\n";
    }

    private static String tsplPrintMethod(String printMethod) {
        if (PrinterSettings.METHOD_THERMAL_TRANSFER.equals(printMethod)) {
            return "SET RIBBON ON\n";
        }
        return "SET RIBBON OFF\n";
    }

    private static String zplPrintMethod(String printMethod) {
        if (PrinterSettings.METHOD_THERMAL_TRANSFER.equals(printMethod)) {
            return "^MTT\n";
        }
        return "^MTD\n";
    }

    private static String sanitizeBarcode(String value) {
        String text = value == null ? "" : value.trim();
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c >= 32 && c <= 126) {
                result.append(c);
            }
        }
        String sanitized = result.toString().trim();
        if (sanitized.isEmpty()) {
            throw new IllegalArgumentException("바코드 값이 비어 있습니다.");
        }
        return sanitized;
    }

    private static String sanitizeSlcs(String value) {
        return safeText(value).replace("'", "");
    }

    private static String sanitizeTspl(String value) {
        return safeText(value).replace("\"", "");
    }

    private static String sanitizeZpl(String value) {
        return safeText(value).replace("^", "").replace("~", "");
    }

    private static String safeText(String value) {
        return value == null ? "" : value.trim();
    }

    private static String formatMm(float value) {
        if (value == Math.round(value)) {
            return String.format(Locale.US, "%d", Math.round(value));
        }
        return String.format(Locale.US, "%.2f", value);
    }
}
