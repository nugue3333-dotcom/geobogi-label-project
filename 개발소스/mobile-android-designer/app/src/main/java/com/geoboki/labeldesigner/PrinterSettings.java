package com.geoboki.labeldesigner;

final class PrinterSettings {
    static final String BRAND_BIXOLON = "bixolon";
    static final String BRAND_TSC = "tsc";
    static final String BRAND_ZEBRA = "zebra";
    static final String BRAND_SEWOO = "sewoo";

    static final String MEDIA_GAP = "gap";
    static final String MEDIA_BLACK_MARK = "black_mark";
    static final String MEDIA_CONTINUOUS = "continuous";

    static final String ACTION_TEAR = "tear";
    static final String ACTION_CUT = "cut";
    static final String ACTION_PEEL = "peel";

    final String brand;
    final String ipAddress;
    final int port;
    final int dpi;
    final int printQty;
    final String mediaType;
    final String afterPrint;

    PrinterSettings(String brand, String ipAddress, int port, int dpi, int printQty) {
        this(brand, ipAddress, port, dpi, printQty, MEDIA_GAP, ACTION_TEAR);
    }

    PrinterSettings(String brand, String ipAddress, int port, int dpi, int printQty,
                    String mediaType, String afterPrint) {
        this.brand = brand;
        this.ipAddress = ipAddress;
        this.port = port;
        this.dpi = dpi;
        this.printQty = printQty;
        this.mediaType = mediaType;
        this.afterPrint = afterPrint;
    }
}
