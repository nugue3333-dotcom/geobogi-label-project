package com.geoboki.labeldesigner;

final class RendererContractCheck {
    private RendererContractCheck() {}

    public static void main(String[] args) {
        LabelTemplate template = new LabelTemplate();
        template.resize(100, 100);
        template.addText("상품명").rotation = 90;
        template.addBarcode("001234567890");
        template.addQr("https://chaeumlab.example");
        template.addBox();
        template.addLine();

        for (int dpi : new int[]{203, 300, 600}) {
            require(LabelCommandRenderer.mmToDots(25.4f, dpi) == dpi, "mm/dot conversion " + dpi);
            check(PrinterSettings.BRAND_TSC, dpi, "UTF-8", "BARCODE ", "QRCODE ", PrinterSettings.ACTION_PEEL);
            check(PrinterSettings.BRAND_BIXOLON, dpi, "CP949", "B1", "B2", PrinterSettings.ACTION_CUT);
            check(PrinterSettings.BRAND_ZEBRA, dpi, "UTF-8", "^BC", "^BQ", PrinterSettings.ACTION_PEEL);
            expectFailure(PrinterSettings.BRAND_SEWOO, PrinterSettings.ACTION_TEAR, "SEWOO unverified protocol blocked");
        }

        expectFailure(PrinterSettings.BRAND_BIXOLON, PrinterSettings.ACTION_PEEL, "BIXOLON peeler blocked");
        expectFailure(PrinterSettings.BRAND_SEWOO, PrinterSettings.ACTION_CUT, "SEWOO cutter blocked");
        expectFailure(PrinterSettings.BRAND_SEWOO, PrinterSettings.ACTION_PEEL, "SEWOO peeler blocked");
        expectZebraRotatedQrFailure();
        CsvTable csv = CsvTable.parse("품목명,바코드,가격\n귀걸이,00123,5300\n목걸이,00999,12000\n");
        require("00123".equals(csv.rows.get(0).get("바코드")), "CSV leading zero preservation");
        require(csv.search("00999").size() == 1, "CSV all-column value search");
        require(csv.search("품목명").size() == 2, "CSV header search");
        expectUnresolvedFieldFailure();
        System.out.println("RENDERER_CONTRACT_OK");
    }

    private static void check(String brand, int dpi, String charset, String barcodeMarker, String qrMarker, String action) {
        LabelTemplate template = new LabelTemplate();
        template.addText("제품");
        template.addBarcode("001234567890").rotation = 90;
        template.addQr("QR-001");
        RenderedCommand rendered = LabelCommandRenderer.render(
                new PrinterSettings(brand, "127.0.0.1", 9100, dpi, 3, PrinterSettings.MEDIA_BLACK_MARK, action), template);
        require(charset.equals(rendered.charsetName), brand + " charset");
        require(rendered.command.contains(barcodeMarker), brand + " Code128 command");
        require(rendered.command.contains(qrMarker), brand + " QR command");
        require(rendered.command.contains("001234567890"), brand + " leading zero value");
        require(rendered.command.contains("3"), brand + " print quantity");
        if (PrinterSettings.BRAND_BIXOLON.equals(brand)) {
            require(rendered.command.contains("\r\n"), "BIXOLON CRLF command endings");
            require(rendered.command.endsWith("P3\r"), "BIXOLON final print command CR ending");
            require(!rendered.command.substring(0, rendered.command.length() - 3).replace("\r\n", "").contains("\n"), "BIXOLON no bare LF");
            require(rendered.command.contains(",1,1,'001234567890'"), "BIXOLON rotation code");
        }
        if (PrinterSettings.BRAND_TSC.equals(brand)) {
            require(rendered.command.contains("\r\n"), "TSC CRLF command endings");
            require(!rendered.command.replace("\r\n", "").contains("\n"), "TSC no bare LF");
        }
    }

    private static void expectZebraRotatedQrFailure() {
        LabelTemplate template = new LabelTemplate();
        template.addQr("QR-ROTATED").rotation = 90;
        try {
            LabelCommandRenderer.render(new PrinterSettings(PrinterSettings.BRAND_ZEBRA, "127.0.0.1", 9100, 203, 1,
                    PrinterSettings.MEDIA_GAP, PrinterSettings.ACTION_TEAR), template);
            throw new AssertionError("Zebra rotated QR must be blocked");
        } catch (IllegalArgumentException expected) {
            require(expected.getMessage().contains("0도"), "Zebra QR rotation error message");
        }
    }

    private static void expectUnresolvedFieldFailure() {
        LabelTemplate template = new LabelTemplate();
        template.addBarcode("{{바코드}}");
        try {
            LabelCommandRenderer.render(new PrinterSettings(PrinterSettings.BRAND_TSC, "127.0.0.1", 9100, 203, 1,
                    PrinterSettings.MEDIA_GAP, PrinterSettings.ACTION_TEAR), template);
            throw new AssertionError("Unresolved barcode field must be blocked");
        } catch (IllegalArgumentException expected) {
            require(expected.getMessage().contains("연결되지 않은 데이터 열"), "Unresolved field error message");
        }
    }

    private static void expectFailure(String brand, String action, String message) {
        LabelTemplate template = new LabelTemplate();
        template.addText("test");
        try {
            LabelCommandRenderer.render(new PrinterSettings(brand, "127.0.0.1", 9100, 203, 1,
                    PrinterSettings.MEDIA_GAP, action), template);
            throw new AssertionError(message);
        } catch (IllegalArgumentException expected) {
            // Contract rejection is the expected result.
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
