package com.geoboki.labelprinter;

final class LabelData {
    final String itemCode;
    final String itemName;
    final String barcode;
    final String lotNo;
    final int qty;
    final int printQty;

    LabelData(String itemCode, String itemName, String barcode, String lotNo, int qty, int printQty) {
        this.itemCode = itemCode;
        this.itemName = itemName;
        this.barcode = barcode;
        this.lotNo = lotNo;
        this.qty = qty;
        this.printQty = printQty;
    }
}
