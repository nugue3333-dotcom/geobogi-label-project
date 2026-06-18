package com.geoboki.labelprinter;

final class PrinterSettings {
    static final String CONNECTION_WIFI = "wifi";
    static final String CONNECTION_BLUETOOTH = "bluetooth";

    static final String BRAND_BIXOLON = "bixolon";
    static final String BRAND_TSC = "tsc";
    static final String BRAND_ZEBRA = "zebra";

    static final String METHOD_DIRECT_THERMAL = "direct_thermal";
    static final String METHOD_THERMAL_TRANSFER = "thermal_transfer";

    final String connectionType;
    final String brand;
    final String printMethod;
    final String ipAddress;
    final int port;
    final String bluetoothAddress;
    final int widthMm;
    final int heightMm;
    final int dpi;
    final float gapMm;

    PrinterSettings(
            String connectionType,
            String brand,
            String printMethod,
            String ipAddress,
            int port,
            String bluetoothAddress,
            int widthMm,
            int heightMm,
            int dpi,
            float gapMm
    ) {
        this.connectionType = connectionType;
        this.brand = brand;
        this.printMethod = printMethod;
        this.ipAddress = ipAddress;
        this.port = port;
        this.bluetoothAddress = bluetoothAddress;
        this.widthMm = widthMm;
        this.heightMm = heightMm;
        this.dpi = dpi;
        this.gapMm = gapMm;
    }
}
