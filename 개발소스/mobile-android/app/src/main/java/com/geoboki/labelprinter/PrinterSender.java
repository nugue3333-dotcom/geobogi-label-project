package com.geoboki.labelprinter;

import android.Manifest;
import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.Charset;
import java.util.UUID;

final class PrinterSender {
    private static final int CONNECT_TIMEOUT_MS = 5000;
    private static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    private PrinterSender() {
    }

    static void send(Context context, PrinterSettings settings, RenderedCommand rendered) throws IOException {
        byte[] payload = rendered.command.getBytes(Charset.forName(rendered.charsetName));
        if (PrinterSettings.CONNECTION_WIFI.equals(settings.connectionType)) {
            sendWifi(settings.ipAddress, settings.port, payload);
            return;
        }
        if (PrinterSettings.CONNECTION_BLUETOOTH.equals(settings.connectionType)) {
            sendBluetooth(context, settings.bluetoothAddress, payload);
            return;
        }
        throw new IOException("지원하지 않는 연결 방식입니다.");
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

    @SuppressLint("MissingPermission")
    private static void sendBluetooth(Context context, String bluetoothAddress, byte[] payload) throws IOException {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                && context.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            throw new IOException("Bluetooth 권한이 허용되지 않았습니다.");
        }

        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter == null) {
            throw new IOException("이 기기에서 Bluetooth를 사용할 수 없습니다.");
        }
        if (!adapter.isEnabled()) {
            throw new IOException("Bluetooth가 꺼져 있습니다.");
        }

        BluetoothDevice device = adapter.getRemoteDevice(bluetoothAddress);
        BluetoothSocket socket = null;
        try {
            socket = device.createRfcommSocketToServiceRecord(SPP_UUID);
            socket.connect();
            OutputStream output = socket.getOutputStream();
            output.write(payload);
            output.flush();
        } finally {
            if (socket != null) {
                try {
                    socket.close();
                } catch (IOException ignored) {
                    // Closing best effort.
                }
            }
        }
    }
}
