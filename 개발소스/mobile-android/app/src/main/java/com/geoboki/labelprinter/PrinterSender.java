package com.geoboki.labelprinter;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.Charset;

final class PrinterSender {
    private static final int CONNECT_TIMEOUT_MS = 5000;

    private PrinterSender() {
    }

    static void send(PrinterSettings settings, RenderedCommand rendered) throws IOException {
        byte[] payload = rendered.command.getBytes(Charset.forName(rendered.charsetName));
        sendWifi(settings.ipAddress, settings.port, payload);
    }

    private static void sendWifi(String ipAddress, int port, byte[] payload) throws IOException {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(ipAddress, port), CONNECT_TIMEOUT_MS);
            socket.setSoTimeout(CONNECT_TIMEOUT_MS);
            OutputStream output = socket.getOutputStream();
            output.write(payload);
            output.flush();
        }
    }
}
