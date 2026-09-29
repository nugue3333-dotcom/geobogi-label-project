package com.geoboki.labelprinter;

final class PrinterSettings {
    static final String BRAND_BIXOLON = "bixolon";
    static final String BRAND_TSC = "tsc";
    static final String BRAND_ZEBRA = "zebra";
    static final String BRAND_SEWOO = "sewoo";

    static final String METHOD_DIRECT_THERMAL = "direct_thermal";
    static final String METHOD_THERMAL_TRANSFER = "thermal_transfer";

    static final String HANDLING_TEAR_OFF = "tear_off";
    static final String HANDLING_CUTTER = "cutter";
    static final String HANDLING_PEELER = "peeler";

    static final String MEDIA_GAP = "gap";
    static final String MEDIA_BLACK_MARK = "black_mark";
    static final String MEDIA_CONTINUOUS = "continuous";

    final String brand;
    final String printMethod;
    final String mediaHandling;
    final String mediaType;
    final String ipAddress;
    final int port;
    final int widthMm;
    final int heightMm;
    final int dpi;
    final float gapMm;

    PrinterSettings(
            String brand,
            String printMethod,
            String mediaHandling,
            String mediaType,
            String ipAddress,
            int port,
            int widthMm,
            int heightMm,
            int dpi,
            float gapMm
    ) {
        this.brand = brand;
        this.printMethod = printMethod;
        this.mediaHandling = mediaHandling;
        this.mediaType = mediaType;
        this.ipAddress = ipAddress;
        this.port = port;
        this.widthMm = widthMm;
        this.heightMm = heightMm;
        this.dpi = dpi;
        this.gapMm = gapMm;
    }
}
