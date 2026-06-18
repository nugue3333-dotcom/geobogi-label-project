package com.geoboki.labelprinter;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.transition.AutoTransition;
import android.transition.TransitionManager;
import android.view.Gravity;
import android.view.View;
import android.view.animation.DecelerateInterpolator;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;

public class MainActivity extends Activity {
    private static final int REQUEST_BLUETOOTH_CONNECT = 1001;

    private static final int COLOR_PRIMARY = Color.rgb(11, 37, 69);
    private static final int COLOR_ACCENT = Color.rgb(31, 111, 235);
    private static final int COLOR_SUCCESS = Color.rgb(18, 128, 92);
    private static final int COLOR_SURFACE = Color.rgb(244, 246, 249);
    private static final int COLOR_CARD = Color.WHITE;
    private static final int COLOR_LINE = Color.rgb(216, 222, 232);
    private static final int COLOR_TEXT = Color.rgb(31, 41, 55);
    private static final int COLOR_MUTED = Color.rgb(107, 114, 128);
    private static final int COLOR_ERROR = Color.rgb(155, 28, 28);

    private static final String[] CONNECTION_LABELS = {"무선랜 / LAN", "블루투스"};
    private static final String[] CONNECTION_VALUES = {PrinterSettings.CONNECTION_WIFI, PrinterSettings.CONNECTION_BLUETOOTH};
    private static final String[] BRAND_LABELS = {"BIXOLON / 빅솔론", "TSC", "Zebra / 제브라"};
    private static final String[] BRAND_VALUES = {PrinterSettings.BRAND_BIXOLON, PrinterSettings.BRAND_TSC, PrinterSettings.BRAND_ZEBRA};
    private static final String[] METHOD_LABELS = {"감열 / 리본 없음", "열전사 / 리본 사용"};
    private static final String[] METHOD_VALUES = {PrinterSettings.METHOD_DIRECT_THERMAL, PrinterSettings.METHOD_THERMAL_TRANSFER};

    private SharedPreferences prefs;
    private final LinkedHashMap<String, String> bluetoothDevices = new LinkedHashMap<>();

    private LinearLayout root;
    private LinearLayout wifiFields;
    private LinearLayout bluetoothFields;
    private Spinner connectionSpinner;
    private Spinner brandSpinner;
    private Spinner methodSpinner;
    private Spinner bluetoothSpinner;
    private EditText ipField;
    private EditText portField;
    private EditText widthField;
    private EditText heightField;
    private EditText gapField;
    private EditText dpiField;
    private EditText itemCodeField;
    private EditText itemNameField;
    private EditText barcodeField;
    private EditText lotNoField;
    private EditText qtyField;
    private EditText printQtyField;
    private TextView statusText;
    private Button saveButton;
    private Button printButton;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("printer_settings", MODE_PRIVATE);
        buildUi();
        loadPreferences();
        refreshBluetoothDevices(false);
        refreshConnectionVisibility(false);
        animateEntrance();
    }

    private void buildUi() {
        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        scrollView.setBackgroundColor(COLOR_SURFACE);

        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(18), dp(18), dp(28));
        scrollView.addView(root);

        root.addView(hero());
        root.addView(buildPrinterSection());
        root.addView(buildLabelSizeSection());
        root.addView(buildLabelDataSection());
        root.addView(buildActionSection());

        setContentView(scrollView);
    }

    private View hero() {
        LinearLayout hero = new LinearLayout(this);
        hero.setOrientation(LinearLayout.VERTICAL);
        hero.setPadding(dp(18), dp(18), dp(18), dp(18));
        hero.setBackground(gradient(COLOR_PRIMARY, Color.rgb(24, 72, 120), dp(16)));
        hero.setLayoutParams(bottomMargin(dp(16)));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            hero.setElevation(dp(3));
        }

        TextView title = new TextView(this);
        title.setText("라벨 출력 모바일");
        title.setTextColor(Color.WHITE);
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER_VERTICAL);
        setIcon(title, R.drawable.ic_print, Color.WHITE, 24);
        hero.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("블루투스와 무선랜으로 프린터에 직접 전송합니다.");
        subtitle.setTextColor(Color.rgb(219, 234, 254));
        subtitle.setTextSize(14);
        subtitle.setPadding(0, dp(8), 0, 0);
        hero.addView(subtitle);

        TextView hint = new TextView(this);
        hint.setText("설정 저장 후 테스트 라벨 출력으로 바로 확인하세요.");
        hint.setTextColor(Color.rgb(191, 219, 254));
        hint.setTextSize(12);
        hint.setPadding(0, dp(10), 0, 0);
        hero.addView(hint);

        return hero;
    }

    private View buildPrinterSection() {
        LinearLayout section = section("프린터 설정", R.drawable.ic_settings);

        connectionSpinner = spinner(CONNECTION_LABELS);
        section.addView(inputGroup("연결 방식", connectionSpinner));

        brandSpinner = spinner(BRAND_LABELS);
        methodSpinner = spinner(METHOD_LABELS);
        section.addView(twoColumn(inputGroup("브랜드", brandSpinner), inputGroup("인쇄 방식", methodSpinner)));

        wifiFields = new LinearLayout(this);
        wifiFields.setOrientation(LinearLayout.VERTICAL);
        ipField = edit("192.168.0.130", InputType.TYPE_CLASS_TEXT);
        portField = edit("9100", InputType.TYPE_CLASS_NUMBER);
        wifiFields.addView(twoColumn(inputGroup("프린터 IP", ipField), inputGroup("포트", portField)));
        section.addView(wifiFields);

        bluetoothFields = new LinearLayout(this);
        bluetoothFields.setOrientation(LinearLayout.VERTICAL);
        bluetoothSpinner = spinner(new String[]{"페어링된 프린터 없음"});
        bluetoothFields.addView(inputGroup("블루투스 프린터", bluetoothSpinner));

        Button refreshButton = button("블루투스 목록 새로고침", R.drawable.ic_bluetooth, false);
        refreshButton.setOnClickListener(v -> refreshBluetoothDevices(true));
        bluetoothFields.addView(refreshButton);
        bluetoothFields.addView(note("Android 설정에서 프린터를 먼저 페어링해야 목록에 표시됩니다."));
        section.addView(bluetoothFields);

        connectionSpinner.setOnItemSelectedListener(new SimpleSelectedListener(() -> refreshConnectionVisibility(true)));
        return section;
    }

    private View buildLabelSizeSection() {
        LinearLayout section = section("용지 설정", R.drawable.ic_label);

        widthField = edit("50", InputType.TYPE_CLASS_NUMBER);
        heightField = edit("30", InputType.TYPE_CLASS_NUMBER);
        gapField = edit("3", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        dpiField = edit("203", InputType.TYPE_CLASS_NUMBER);

        section.addView(twoColumn(inputGroup("가로(mm)", widthField), inputGroup("세로(mm)", heightField)));
        section.addView(twoColumn(inputGroup("간격(mm)", gapField), inputGroup("DPI", dpiField)));
        return section;
    }

    private View buildLabelDataSection() {
        LinearLayout section = section("라벨 데이터", R.drawable.ic_barcode);

        itemCodeField = edit("A1001", InputType.TYPE_CLASS_TEXT);
        itemNameField = edit("SENSOR BRACKET", InputType.TYPE_CLASS_TEXT);
        barcodeField = edit("A1001-250531", InputType.TYPE_CLASS_TEXT);
        lotNoField = edit("LOT250531", InputType.TYPE_CLASS_TEXT);
        qtyField = edit("100", InputType.TYPE_CLASS_NUMBER);
        printQtyField = edit("1", InputType.TYPE_CLASS_NUMBER);

        section.addView(twoColumn(inputGroup("품목 코드", itemCodeField), inputGroup("수량", qtyField)));
        section.addView(inputGroup("품목명", itemNameField));
        section.addView(inputGroup("바코드 값", barcodeField));
        section.addView(twoColumn(inputGroup("LOT 번호", lotNoField), inputGroup("출력 매수", printQtyField)));
        return section;
    }

    private View buildActionSection() {
        LinearLayout section = new LinearLayout(this);
        section.setOrientation(LinearLayout.VERTICAL);
        section.setPadding(0, dp(4), 0, 0);

        saveButton = button("설정 저장", R.drawable.ic_save, false);
        saveButton.setOnClickListener(v -> savePreferences());
        section.addView(saveButton);

        printButton = button("테스트 라벨 출력", R.drawable.ic_print, true);
        printButton.setOnClickListener(v -> printLabel());
        section.addView(printButton);

        statusText = note("대기 중");
        statusText.setPadding(dp(4), dp(10), dp(4), 0);
        section.addView(statusText);
        return section;
    }

    private void printLabel() {
        PrinterSettings settings;
        LabelData data;
        try {
            settings = collectSettings();
            data = collectLabelData();
            persistSettings(settings);
        } catch (RuntimeException ex) {
            showError("입력 확인", ex.getMessage());
            return;
        }

        setBusy(true);
        setStatus("출력 전송 중...", false);
        new Thread(() -> {
            try {
                RenderedCommand command = LabelCommandRenderer.render(settings, data);
                PrinterSender.send(this, settings, command);
                runOnUiThread(() -> {
                    setBusy(false);
                    setStatus("출력 전송 완료", false);
                });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    setBusy(false);
                    showError("출력 실패", ex.getMessage());
                });
            }
        }).start();
    }

    private PrinterSettings collectSettings() {
        String connection = selectedValue(connectionSpinner, CONNECTION_VALUES);
        String brand = selectedValue(brandSpinner, BRAND_VALUES);
        String method = selectedValue(methodSpinner, METHOD_VALUES);
        int port = parseIntOrDefault(portField, "포트", 9100);
        int width = parseInt(widthField, "가로");
        int height = parseInt(heightField, "세로");
        int dpi = parseInt(dpiField, "DPI");
        float gap = parseFloat(gapField, "라벨 간격");
        String bluetoothAddress = selectedBluetoothAddress();

        if (width <= 0 || height <= 0) {
            throw new IllegalArgumentException("용지 가로/세로는 1 이상이어야 합니다.");
        }
        if (dpi != 203 && dpi != 300 && dpi != 600) {
            throw new IllegalArgumentException("DPI는 203, 300, 600 중 하나로 입력하세요.");
        }
        if (gap < 0) {
            throw new IllegalArgumentException("라벨 간격은 0 이상이어야 합니다.");
        }
        if (PrinterSettings.CONNECTION_WIFI.equals(connection)) {
            if (ipField.getText().toString().trim().isEmpty()) {
                throw new IllegalArgumentException("무선랜 IP를 입력하세요.");
            }
            if (port <= 0 || port > 65535) {
                throw new IllegalArgumentException("포트는 1부터 65535 사이여야 합니다.");
            }
        }
        if (PrinterSettings.CONNECTION_BLUETOOTH.equals(connection) && bluetoothAddress.isEmpty()) {
            throw new IllegalArgumentException("블루투스 프린터를 선택하세요.");
        }

        return new PrinterSettings(
                connection,
                brand,
                method,
                ipField.getText().toString().trim(),
                port,
                bluetoothAddress,
                width,
                height,
                dpi,
                gap
        );
    }

    private LabelData collectLabelData() {
        int qty = parseInt(qtyField, "수량");
        int printQty = parseInt(printQtyField, "출력 매수");
        if (printQty <= 0 || printQty > 100) {
            throw new IllegalArgumentException("출력 매수는 1부터 100 사이로 입력하세요.");
        }
        if (barcodeField.getText().toString().trim().isEmpty()) {
            throw new IllegalArgumentException("바코드 값을 입력하세요.");
        }
        return new LabelData(
                itemCodeField.getText().toString(),
                itemNameField.getText().toString(),
                barcodeField.getText().toString(),
                lotNoField.getText().toString(),
                qty,
                printQty
        );
    }

    private void savePreferences() {
        try {
            PrinterSettings settings = collectSettings();
            persistSettings(settings);
            setStatus("설정 저장 완료", false);
        } catch (RuntimeException ex) {
            showError("저장 실패", ex.getMessage());
        }
    }

    private void persistSettings(PrinterSettings settings) {
        prefs.edit()
                .putString("connection", settings.connectionType)
                .putString("brand", settings.brand)
                .putString("method", settings.printMethod)
                .putString("ip", settings.ipAddress)
                .putInt("port", settings.port)
                .putString("bluetooth", settings.bluetoothAddress)
                .putInt("width", settings.widthMm)
                .putInt("height", settings.heightMm)
                .putInt("dpi", settings.dpi)
                .putFloat("gap", settings.gapMm)
                .apply();
    }

    private void loadPreferences() {
        setSpinnerByValue(connectionSpinner, CONNECTION_VALUES, prefs.getString("connection", PrinterSettings.CONNECTION_WIFI));
        setSpinnerByValue(brandSpinner, BRAND_VALUES, prefs.getString("brand", PrinterSettings.BRAND_BIXOLON));
        setSpinnerByValue(methodSpinner, METHOD_VALUES, prefs.getString("method", PrinterSettings.METHOD_DIRECT_THERMAL));
        ipField.setText(prefs.getString("ip", "192.168.0.130"));
        portField.setText(String.valueOf(prefs.getInt("port", 9100)));
        widthField.setText(String.valueOf(prefs.getInt("width", 50)));
        heightField.setText(String.valueOf(prefs.getInt("height", 30)));
        dpiField.setText(String.valueOf(prefs.getInt("dpi", 203)));
        gapField.setText(trimFloat(prefs.getFloat("gap", 3f)));
    }

    private void refreshConnectionVisibility(boolean animate) {
        if (wifiFields == null || bluetoothFields == null) {
            return;
        }
        if (animate && Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            AutoTransition transition = new AutoTransition();
            transition.setDuration(180);
            TransitionManager.beginDelayedTransition(root, transition);
        }
        boolean wifi = PrinterSettings.CONNECTION_WIFI.equals(selectedValue(connectionSpinner, CONNECTION_VALUES));
        wifiFields.setVisibility(wifi ? View.VISIBLE : View.GONE);
        bluetoothFields.setVisibility(wifi ? View.GONE : View.VISIBLE);
    }

    private void refreshBluetoothDevices(boolean requestPermission) {
        if (requestPermission && !hasBluetoothPermission()) {
            requestBluetoothPermission();
            return;
        }

        bluetoothDevices.clear();
        if (!hasBluetoothPermission()) {
            setBluetoothAdapterValues("Bluetooth 권한 필요");
            return;
        }

        BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
        if (adapter == null) {
            setBluetoothAdapterValues("Bluetooth 미지원 기기");
            return;
        }
        if (!adapter.isEnabled()) {
            setBluetoothAdapterValues("Bluetooth 꺼짐");
            return;
        }

        try {
            loadBondedDevices(adapter);
        } catch (SecurityException ex) {
            setBluetoothAdapterValues("Bluetooth 권한 필요");
            return;
        }

        if (bluetoothDevices.isEmpty()) {
            setBluetoothAdapterValues("페어링된 프린터 없음");
            return;
        }

        List<String> labels = new ArrayList<>(bluetoothDevices.keySet());
        setBluetoothAdapterValues(labels.toArray(new String[0]));
        String savedAddress = prefs.getString("bluetooth", "");
        if (!savedAddress.isEmpty()) {
            int index = 0;
            for (String label : labels) {
                if (savedAddress.equals(bluetoothDevices.get(label))) {
                    bluetoothSpinner.setSelection(index);
                    break;
                }
                index++;
            }
        }
    }

    @SuppressLint("MissingPermission")
    private void loadBondedDevices(BluetoothAdapter adapter) {
        for (BluetoothDevice device : adapter.getBondedDevices()) {
            String name = device.getName();
            if (name == null || name.trim().isEmpty()) {
                name = "이름 없음";
            }
            bluetoothDevices.put(name + " / " + device.getAddress(), device.getAddress());
        }
    }

    private boolean hasBluetoothPermission() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.S
                || checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestBluetoothPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, REQUEST_BLUETOOTH_CONNECT);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_BLUETOOTH_CONNECT) {
            if (hasBluetoothPermission()) {
                refreshBluetoothDevices(false);
            } else {
                showError("Bluetooth 권한 필요", "블루투스 프린터를 사용하려면 권한을 허용해야 합니다.");
            }
        }
    }

    private String selectedBluetoothAddress() {
        Object item = bluetoothSpinner.getSelectedItem();
        if (item == null) {
            return "";
        }
        String address = bluetoothDevices.get(item.toString());
        return address == null ? "" : address;
    }

    private LinearLayout section(String titleText, int iconRes) {
        LinearLayout section = new LinearLayout(this);
        section.setOrientation(LinearLayout.VERTICAL);
        section.setPadding(dp(16), dp(16), dp(16), dp(16));
        section.setLayoutParams(bottomMargin(dp(14)));
        section.setBackground(rounded(COLOR_CARD, COLOR_LINE, dp(14)));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            section.setElevation(dp(2));
        }

        TextView title = new TextView(this);
        title.setText(titleText);
        title.setTextColor(COLOR_PRIMARY);
        title.setTextSize(17);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER_VERTICAL);
        title.setPadding(0, 0, 0, dp(8));
        setIcon(title, iconRes, COLOR_PRIMARY, 21);
        section.addView(title);
        return section;
    }

    private LinearLayout inputGroup(String labelText, View input) {
        LinearLayout group = new LinearLayout(this);
        group.setOrientation(LinearLayout.VERTICAL);
        group.setPadding(0, dp(7), 0, dp(5));

        TextView label = new TextView(this);
        label.setText(labelText);
        label.setTextColor(COLOR_TEXT);
        label.setTextSize(12);
        label.setTypeface(Typeface.DEFAULT_BOLD);
        label.setPadding(0, 0, 0, dp(4));
        group.addView(label);

        group.addView(input);
        return group;
    }

    private LinearLayout twoColumn(View left, View right) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setBaselineAligned(false);

        LinearLayout.LayoutParams leftParams = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
        leftParams.setMargins(0, 0, dp(7), 0);
        row.addView(left, leftParams);

        LinearLayout.LayoutParams rightParams = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
        rightParams.setMargins(dp(7), 0, 0, 0);
        row.addView(right, rightParams);
        return row;
    }

    private TextView note(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextColor(COLOR_MUTED);
        view.setTextSize(12);
        view.setPadding(0, dp(7), 0, dp(4));
        return view;
    }

    private EditText edit(String hint, int inputType) {
        EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setHint(hint);
        field.setInputType(inputType);
        field.setTextSize(15);
        field.setTextColor(COLOR_TEXT);
        field.setHintTextColor(Color.rgb(156, 163, 175));
        field.setPadding(dp(12), 0, dp(12), 0);
        field.setMinHeight(dp(48));
        field.setBackground(rounded(Color.WHITE, COLOR_LINE, dp(10)));
        return field;
    }

    private Spinner spinner(String[] items) {
        Spinner spinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, items);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(adapter);
        spinner.setMinimumHeight(dp(48));
        spinner.setPadding(dp(8), 0, dp(8), 0);
        spinner.setBackground(rounded(Color.WHITE, COLOR_LINE, dp(10)));
        return spinner;
    }

    private Button button(String text, int iconRes, boolean primary) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextSize(15);
        button.setTypeface(Typeface.DEFAULT_BOLD);
        button.setMinHeight(dp(52));
        button.setTextColor(primary ? Color.WHITE : COLOR_PRIMARY);
        button.setGravity(Gravity.CENTER);
        button.setBackground(primary
                ? rounded(COLOR_ACCENT, COLOR_ACCENT, dp(13))
                : rounded(Color.WHITE, COLOR_LINE, dp(13)));
        setIcon(button, iconRes, primary ? Color.WHITE : COLOR_PRIMARY, 20);

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, dp(8), 0, 0);
        button.setLayoutParams(params);
        return button;
    }

    private void setBluetoothAdapterValues(String singleValue) {
        setBluetoothAdapterValues(new String[]{singleValue});
    }

    private void setBluetoothAdapterValues(String[] values) {
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, values);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        bluetoothSpinner.setAdapter(adapter);
    }

    private String selectedValue(Spinner spinner, String[] values) {
        int index = spinner.getSelectedItemPosition();
        if (index < 0 || index >= values.length) {
            return values[0];
        }
        return values[index];
    }

    private void setSpinnerByValue(Spinner spinner, String[] values, String value) {
        for (int i = 0; i < values.length; i++) {
            if (values[i].equals(value)) {
                spinner.setSelection(i);
                return;
            }
        }
        spinner.setSelection(0);
    }

    private int parseInt(EditText field, String label) {
        try {
            return Integer.parseInt(field.getText().toString().trim());
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException(label + " 값을 숫자로 입력하세요.");
        }
    }

    private int parseIntOrDefault(EditText field, String label, int fallback) {
        String value = field.getText().toString().trim();
        if (value.isEmpty()) {
            return fallback;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException(label + " 값을 숫자로 입력하세요.");
        }
    }

    private float parseFloat(EditText field, String label) {
        try {
            return Float.parseFloat(field.getText().toString().trim());
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException(label + " 값을 숫자로 입력하세요.");
        }
    }

    private void setStatus(String message, boolean error) {
        statusText.animate().alpha(0f).setDuration(90).withEndAction(() -> {
            statusText.setText(message);
            statusText.setTextColor(error ? COLOR_ERROR : COLOR_SUCCESS);
            statusText.animate().alpha(1f).setDuration(140).start();
        }).start();
    }

    private void showError(String title, String message) {
        setStatus(title + ": " + message, true);
        new AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(message)
                .setPositiveButton("확인", null)
                .show();
    }

    private void setBusy(boolean busy) {
        saveButton.setEnabled(!busy);
        printButton.setEnabled(!busy);
        printButton.setText(busy ? "전송 중..." : "테스트 라벨 출력");
        printButton.animate()
                .alpha(busy ? 0.72f : 1f)
                .scaleX(busy ? 0.98f : 1f)
                .scaleY(busy ? 0.98f : 1f)
                .setDuration(160)
                .start();
    }

    private void animateEntrance() {
        for (int i = 0; i < root.getChildCount(); i++) {
            View child = root.getChildAt(i);
            child.setAlpha(0f);
            child.setTranslationY(dp(14));
            child.animate()
                    .alpha(1f)
                    .translationY(0f)
                    .setStartDelay(i * 70L)
                    .setDuration(260)
                    .setInterpolator(new DecelerateInterpolator())
                    .start();
        }
    }

    private void setIcon(TextView view, int resId, int color, int sizeDp) {
        Drawable icon = getResources().getDrawable(resId, getTheme());
        icon.setTint(color);
        int size = dp(sizeDp);
        icon.setBounds(0, 0, size, size);
        view.setCompoundDrawables(icon, null, null, null);
        view.setCompoundDrawablePadding(dp(8));
    }

    private GradientDrawable rounded(int fillColor, int strokeColor, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fillColor);
        drawable.setCornerRadius(radius);
        drawable.setStroke(1, strokeColor);
        return drawable;
    }

    private GradientDrawable gradient(int startColor, int endColor, int radius) {
        GradientDrawable drawable = new GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{startColor, endColor}
        );
        drawable.setCornerRadius(radius);
        return drawable;
    }

    private LinearLayout.LayoutParams bottomMargin(int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, 0, 0, bottom);
        return params;
    }

    private String trimFloat(float value) {
        if (value == Math.round(value)) {
            return String.valueOf(Math.round(value));
        }
        return String.valueOf(value);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private static final class SimpleSelectedListener implements android.widget.AdapterView.OnItemSelectedListener {
        private final Runnable callback;

        SimpleSelectedListener(Runnable callback) {
            this.callback = callback;
        }

        @Override
        public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
            callback.run();
        }

        @Override
        public void onNothingSelected(android.widget.AdapterView<?> parent) {
            callback.run();
        }
    }
}
