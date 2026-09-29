package com.geoboki.labelprinter;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
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

public class MainActivity extends Activity {
    private static final int COLOR_PRIMARY = Color.rgb(11, 37, 69);
    private static final int COLOR_ACCENT = Color.rgb(0, 128, 92);
    private static final int COLOR_SUCCESS = Color.rgb(18, 128, 92);
    private static final int COLOR_SURFACE = Color.rgb(244, 246, 249);
    private static final int COLOR_CARD = Color.WHITE;
    private static final int COLOR_LINE = Color.rgb(216, 222, 232);
    private static final int COLOR_TEXT = Color.rgb(31, 41, 55);
    private static final int COLOR_MUTED = Color.rgb(107, 114, 128);
    private static final int COLOR_ERROR = Color.rgb(155, 28, 28);

    private static final String[] BRAND_LABELS = {
            "BIXOLON / 빅솔론",
            "TSC",
            "Zebra / 제브라",
            "SEWOO / 세우테크 (ZPL)"
    };
    private static final String[] BRAND_VALUES = {
            PrinterSettings.BRAND_BIXOLON,
            PrinterSettings.BRAND_TSC,
            PrinterSettings.BRAND_ZEBRA,
            PrinterSettings.BRAND_SEWOO
    };
    private static final String[] METHOD_LABELS = {"감열 / 리본 없음", "열전사 / 리본 사용"};
    private static final String[] METHOD_VALUES = {PrinterSettings.METHOD_DIRECT_THERMAL, PrinterSettings.METHOD_THERMAL_TRANSFER};
    private static final String[] HANDLING_LABELS = {"뜯어내기", "커터", "필러"};
    private static final String[] HANDLING_VALUES = {PrinterSettings.HANDLING_TEAR_OFF, PrinterSettings.HANDLING_CUTTER, PrinterSettings.HANDLING_PEELER};
    private static final String[] MEDIA_LABELS = {"갭 용지", "블랙마크 용지", "연속 용지"};
    private static final String[] MEDIA_VALUES = {PrinterSettings.MEDIA_GAP, PrinterSettings.MEDIA_BLACK_MARK, PrinterSettings.MEDIA_CONTINUOUS};

    private SharedPreferences prefs;
    private LinearLayout root;
    private Spinner brandSpinner;
    private Spinner methodSpinner;
    private Spinner handlingSpinner;
    private Spinner mediaSpinner;
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
        hero.setBackground(gradient(COLOR_PRIMARY, Color.rgb(14, 100, 82), dp(16)));
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
        subtitle.setText("무선 LAN으로 라벨 프린터에 RAW 명령을 직접 전송합니다.");
        subtitle.setTextColor(Color.rgb(219, 234, 254));
        subtitle.setTextSize(14);
        subtitle.setPadding(0, dp(8), 0, 0);
        hero.addView(subtitle);

        TextView hint = new TextView(this);
        hint.setText("휴대폰과 프린터가 같은 공유기 또는 같은 사내망에 있어야 합니다.");
        hint.setTextColor(Color.rgb(209, 250, 229));
        hint.setTextSize(12);
        hint.setPadding(0, dp(10), 0, 0);
        hero.addView(hint);

        return hero;
    }

    private View buildPrinterSection() {
        LinearLayout section = section("프린터 설정", R.drawable.ic_wifi);

        ipField = edit("192.168.0.130", InputType.TYPE_CLASS_TEXT);
        portField = edit("9100", InputType.TYPE_CLASS_NUMBER);
        section.addView(twoColumn(inputGroup("프린터 IP", ipField), inputGroup("포트", portField)));

        brandSpinner = spinner(BRAND_LABELS);
        methodSpinner = spinner(METHOD_LABELS);
        section.addView(twoColumn(inputGroup("브랜드", brandSpinner), inputGroup("인쇄 방식", methodSpinner)));

        handlingSpinner = spinner(HANDLING_LABELS);
        mediaSpinner = spinner(MEDIA_LABELS);
        section.addView(twoColumn(inputGroup("인쇄후작업", handlingSpinner), inputGroup("용지 유형", mediaSpinner)));
        section.addView(note("연결 방식은 무선 LAN 고정입니다. USB, Bluetooth, 드라이버 큐 전송은 모바일 앱에서 사용하지 않습니다."));
        return section;
    }

    private View buildLabelSizeSection() {
        LinearLayout section = section("용지 설정", R.drawable.ic_label);
        widthField = edit("50", InputType.TYPE_CLASS_NUMBER);
        heightField = edit("40", InputType.TYPE_CLASS_NUMBER);
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

        printButton = button("테스트 라벨 전송", R.drawable.ic_print, true);
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
        setStatus("무선 LAN 전송 중...", false);
        new Thread(() -> {
            try {
                RenderedCommand command = LabelCommandRenderer.render(settings, data);
                PrinterSender.send(settings, command);
                runOnUiThread(() -> {
                    setBusy(false);
                    setStatus("명령 전송 완료", false);
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
        String brand = selectedValue(brandSpinner, BRAND_VALUES);
        String method = selectedValue(methodSpinner, METHOD_VALUES);
        String handling = selectedValue(handlingSpinner, HANDLING_VALUES);
        String media = selectedValue(mediaSpinner, MEDIA_VALUES);
        int port = parseIntOrDefault(portField, "포트", 9100);
        int width = parseInt(widthField, "가로");
        int height = parseInt(heightField, "세로");
        int dpi = parseInt(dpiField, "DPI");
        float gap = parseFloat(gapField, "라벨 간격");

        if (ipField.getText().toString().trim().isEmpty()) {
            throw new IllegalArgumentException("프린터 IP를 입력하세요.");
        }
        if (port <= 0 || port > 65535) {
            throw new IllegalArgumentException("포트는 1부터 65535 사이여야 합니다.");
        }
        if (width <= 0 || height <= 0) {
            throw new IllegalArgumentException("용지 가로/세로는 1 이상이어야 합니다.");
        }
        if (dpi != 203 && dpi != 300 && dpi != 600) {
            throw new IllegalArgumentException("DPI는 203, 300, 600 중 하나로 입력하세요.");
        }
        if (gap < 0) {
            throw new IllegalArgumentException("라벨 간격은 0 이상이어야 합니다.");
        }

        return new PrinterSettings(
                brand,
                method,
                handling,
                media,
                ipField.getText().toString().trim(),
                port,
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
                .putString("brand", settings.brand)
                .putString("method", settings.printMethod)
                .putString("handling", settings.mediaHandling)
                .putString("media", settings.mediaType)
                .putString("ip", settings.ipAddress)
                .putInt("port", settings.port)
                .putInt("width", settings.widthMm)
                .putInt("height", settings.heightMm)
                .putInt("dpi", settings.dpi)
                .putFloat("gap", settings.gapMm)
                .apply();
    }

    private void loadPreferences() {
        setSpinnerByValue(brandSpinner, BRAND_VALUES, prefs.getString("brand", PrinterSettings.BRAND_BIXOLON));
        setSpinnerByValue(methodSpinner, METHOD_VALUES, prefs.getString("method", PrinterSettings.METHOD_DIRECT_THERMAL));
        setSpinnerByValue(handlingSpinner, HANDLING_VALUES, prefs.getString("handling", PrinterSettings.HANDLING_TEAR_OFF));
        setSpinnerByValue(mediaSpinner, MEDIA_VALUES, prefs.getString("media", PrinterSettings.MEDIA_GAP));
        ipField.setText(prefs.getString("ip", "192.168.0.130"));
        portField.setText(String.valueOf(prefs.getInt("port", 9100)));
        widthField.setText(String.valueOf(prefs.getInt("width", 50)));
        heightField.setText(String.valueOf(prefs.getInt("height", 40)));
        dpiField.setText(String.valueOf(prefs.getInt("dpi", 203)));
        gapField.setText(trimFloat(prefs.getFloat("gap", 3f)));
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
        printButton.setText(busy ? "전송 중..." : "테스트 라벨 전송");
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
}
