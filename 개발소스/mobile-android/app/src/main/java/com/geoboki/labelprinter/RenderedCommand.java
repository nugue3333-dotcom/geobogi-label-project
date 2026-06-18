package com.geoboki.labelprinter;

final class RenderedCommand {
    final String command;
    final String charsetName;

    RenderedCommand(String command, String charsetName) {
        this.command = command;
        this.charsetName = charsetName;
    }
}
