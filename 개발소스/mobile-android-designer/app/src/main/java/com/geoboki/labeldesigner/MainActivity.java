package com.geoboki.labeldesigner;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
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

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class MainActivity extends Activity {
    private static final int OPEN_TEMPLATE = 1001;
    private static final int SAVE_TEMPLATE = 1002;
    private static final int OPEN_CSV = 1003;
    private static final int COLOR_PRIMARY = Color.rgb(18, 45, 52);
    private static final int COLOR_ACCENT = Color.rgb(115, 166, 57);
    private static final int COLOR_SURFACE = Color.rgb(246, 248, 247);
    private static final int COLOR_CARD = Color.WHITE;
    private static final int COLOR_LINE = Color.rgb(215, 224, 220);
    private static final int COLOR_TEXT = Color.rgb(31, 41, 55);
    private static final int COLOR_MUTED = Color.rgb(100, 116, 113);
    private static final int COLOR_DANGER = Color.rgb(180, 35, 24);

    private static final String[] BRAND_LABELS = {"TSC", "BIXOLON / 빅솔론", "Zebra / 제브라", "SEWOO / 세우테크"};
    private static final String[] BRAND_VALUES = {PrinterSettings.BRAND_TSC, PrinterSettings.BRAND_BIXOLON, PrinterSettings.BRAND_ZEBRA, PrinterSettings.BRAND_SEWOO};
    private static final String[] DPI_LABELS = {"203 dpi", "300 dpi", "600 dpi"};
    private static final int[] DPI_VALUES = {203, 300, 600};
    private static final String[] MEDIA_LABELS = {"갭 용지", "블랙마크 용지", "연속 용지"};
    private static final String[] MEDIA_VALUES = {PrinterSettings.MEDIA_GAP, PrinterSettings.MEDIA_BLACK_MARK, PrinterSettings.MEDIA_CONTINUOUS};
    private static final String[] AFTER_LABELS = {"뜯어내기", "커터", "필러"};
    private static final String[] AFTER_VALUES = {PrinterSettings.ACTION_TEAR, PrinterSettings.ACTION_CUT, PrinterSettings.ACTION_PEEL};
    private static final String[] ROTATION_LABELS = {"0도", "90도", "180도", "270도"};
    private static final int[] ROTATION_VALUES = {0, 90, 180, 270};

    private LinearLayout root;
    private DesignerCanvasView canvasView;
    private TextView selectedTitle;
    private TextView statusText;
    private TextView dataStatus;
    private Button sendButton;
    private Button connectionButton;
    private CsvTable csvTable;
    private Map<String, String> selectedRow = new LinkedHashMap<>();
    private String printerIp = "192.168.0.130";
    private int printerPort = 9100;
    private int dpi = 203;
    private int printQty = 1;
    private int brandIndex = 0;
    private int mediaIndex = 0;
    private int afterIndex = 0;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        loadSettings();
        buildUi();
        canvasView.newBlankTemplate();
        animateEntrance();
    }

    private void buildUi() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(10), dp(10), dp(10), dp(10));
        root.setBackgroundColor(COLOR_SURFACE);
        root.addView(hero());
        root.addView(toolbarCard());
        root.addView(selectionBar());
        root.addView(canvasCard(), new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
    }

    private View hero() {
        LinearLayout hero = new LinearLayout(this);
        hero.setOrientation(LinearLayout.VERTICAL);
        hero.setPadding(dp(14), dp(11), dp(14), dp(11));
        hero.setLayoutParams(bottomMargin(dp(8)));
        hero.setBackground(gradient(COLOR_PRIMARY, Color.rgb(45, 91, 72), dp(10)));
        if (Build.VERSION.SDK_INT >= 21) hero.setElevation(dp(2));
        TextView title = text("채움LAB 모바일 라벨", 20, Color.WHITE, true);
        hero.addView(title);
        statusText = text("빈 템플릿입니다. 객체를 추가하거나 파일을 불러오세요.", 11, Color.rgb(226, 245, 232), false);
        statusText.setPadding(0, dp(5), 0, 0);
        hero.addView(statusText);
        return hero;
    }

    private View toolbarCard() {
        LinearLayout card = card(null);
        card.setPadding(dp(9), dp(7), dp(9), dp(9));
        card.addView(buttonRow(
                actionButton("파일", false, v -> showFileMenu()),
                actionButton("객체 추가", false, v -> showObjectMenu()),
                actionButton("DB / CSV", false, v -> showDataMenu())
        ));
        connectionButton = actionButton("연결 확인", false, v -> checkConnection());
        sendButton = actionButton("출력", false, v -> showPrintDialog());
        card.addView(buttonRow(
                actionButton("프린터 설정", false, v -> showSettingsDialog()),
                connectionButton,
                sendButton
        ));
        return card;
    }

    private View selectionBar() {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.VERTICAL);
        bar.setPadding(dp(12), dp(7), dp(12), dp(7));
        bar.setLayoutParams(bottomMargin(dp(8)));
        bar.setBackground(rounded(Color.WHITE, COLOR_LINE, dp(10)));
        selectedTitle = text("선택된 객체 없음", 13, COLOR_PRIMARY, true);
        selectedTitle.setOnClickListener(v -> showPropertyDialog());
        bar.addView(selectedTitle);
        dataStatus = text("DB 연결 안 됨", 11, COLOR_MUTED, false);
        dataStatus.setPadding(0, dp(3), 0, 0);
        bar.addView(dataStatus);
        return bar;
    }

    private View canvasCard() {
        LinearLayout card = card("편집 캔버스");
        canvasView = new DesignerCanvasView(this);
        canvasView.setSelectionListener(this::updateSelection);
        canvasView.setBackground(rounded(Color.rgb(230, 237, 234), Color.rgb(190, 204, 198), dp(10)));
        card.addView(canvasView, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        return card;
    }

    private void showFileMenu() {
        String[] items = {"새 빈 템플릿", "JSON 템플릿 저장", "JSON 템플릿 불러오기"};
        new AlertDialog.Builder(this).setTitle("파일")
                .setItems(items, (d, which) -> {
                    if (which == 0) confirmNewTemplate();
                    else if (which == 1) createDocument("application/json", "chaeumlab-label.json", SAVE_TEMPLATE);
                    else openDocument("application/json", OPEN_TEMPLATE);
                }).show();
    }

    private void confirmNewTemplate() {
        new AlertDialog.Builder(this).setTitle("새 빈 템플릿")
                .setMessage("현재 편집 내용을 지우고 빈 템플릿으로 시작할까요?")
                .setNegativeButton("취소", null)
                .setPositiveButton("새로 만들기", (d, w) -> {
                    canvasView.newBlankTemplate();
                    selectedRow.clear();
                    dataStatus.setText(csvTable == null ? "DB 연결 안 됨" : "CSV 연결됨 | 출력 행 미선택");
                    setStatus("빈 템플릿을 만들었습니다.", false);
                }).show();
    }

    private void showObjectMenu() {
        String[] items = {"텍스트", "1D 바코드", "QR 코드", "박스", "선"};
        new AlertDialog.Builder(this).setTitle("객체 추가")
                .setItems(items, (d, which) -> {
                    if (which == 0) showInputDialog("텍스트 추가", "{{품목명}}", value -> canvasView.addText(value));
                    else if (which == 1) showInputDialog("1D 바코드 추가", "{{바코드}}", value -> canvasView.addBarcode(value));
                    else if (which == 2) showInputDialog("QR 코드 추가", "{{QR}}", value -> canvasView.addQr(value));
                    else if (which == 3) canvasView.addBox();
                    else canvasView.addLine();
                    setStatus("객체를 추가했습니다.", false);
                }).show();
    }

    private void showDataMenu() {
        String[] items = csvTable == null
                ? new String[]{"CSV 가져오기"}
                : new String[]{"CSV 다시 가져오기", "전체 열 검색 및 행 선택", "DB 연결 해제"};
        new AlertDialog.Builder(this).setTitle("데이터 소스")
                .setItems(items, (d, which) -> {
                    if (which == 0) openDocument("text/*", OPEN_CSV);
                    else if (which == 1) showRowPicker();
                    else {
                        csvTable = null;
                        selectedRow.clear();
                        dataStatus.setText("DB 연결 안 됨");
                        setStatus("CSV 연결을 해제했습니다.", false);
                    }
                }).show();
    }

    private void showRowPicker() {
        if (csvTable == null) { showError("CSV 파일을 먼저 가져오세요."); return; }
        LinearLayout box = dialogBox();
        EditText search = edit("", InputType.TYPE_CLASS_TEXT);
        search.setHint("모든 열에서 검색");
        TextView count = text("", 11, COLOR_MUTED, false);
        LinearLayout rows = new LinearLayout(this);
        rows.setOrientation(LinearLayout.VERTICAL);
        box.addView(inputGroup("검색", search));
        box.addView(count);
        box.addView(rows);
        Runnable refresh = () -> populateRows(rows, count, csvTable.search(search.getText().toString()));
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) { refresh.run(); }
            public void afterTextChanged(Editable s) {}
        });
        refresh.run();
        new AlertDialog.Builder(this).setTitle("CSV 행 선택")
                .setView(dialogScroll(box)).setNegativeButton("닫기", null).show();
    }

    private void populateRows(LinearLayout holder, TextView count, List<Integer> indexes) {
        holder.removeAllViews();
        count.setText("검색 결과 " + indexes.size() + "건");
        int limit = Math.min(indexes.size(), 100);
        for (int i = 0; i < limit; i++) {
            int rowIndex = indexes.get(i);
            Button row = actionButton(csvTable.summary(rowIndex), false, v -> {
                selectedRow = new LinkedHashMap<>(csvTable.rows.get(rowIndex));
                dataStatus.setText("선택 행 | " + csvTable.summary(rowIndex));
                setStatus("CSV 행을 선택했습니다. {{열이름}} 객체가 선택 값으로 출력됩니다.", false);
            });
            row.setGravity(Gravity.LEFT | Gravity.CENTER_VERTICAL);
            row.setTextSize(11);
            holder.addView(row, bottomMargin(dp(4)));
        }
        if (indexes.size() > limit) holder.addView(note("검색 결과가 많아 처음 100건만 표시합니다. 검색어를 더 입력하세요."));
    }

    private void showSettingsDialog() {
        EditText width = edit(format(canvasView.template().widthMm), decimalType());
        EditText height = edit(format(canvasView.template().heightMm), decimalType());
        EditText ip = edit(printerIp, InputType.TYPE_CLASS_TEXT);
        EditText port = edit(String.valueOf(printerPort), InputType.TYPE_CLASS_NUMBER);
        Spinner brand = spinner(BRAND_LABELS); brand.setSelection(brandIndex);
        Spinner dpiSpinner = spinner(DPI_LABELS); dpiSpinner.setSelection(indexOf(DPI_VALUES, dpi));
        Spinner media = spinner(MEDIA_LABELS); media.setSelection(mediaIndex);
        Spinner after = spinner(AFTER_LABELS); after.setSelection(afterIndex);
        LinearLayout box = dialogBox();
        box.addView(twoColumn(inputGroup("라벨 가로(mm)", width), inputGroup("라벨 세로(mm)", height)));
        box.addView(twoColumn(inputGroup("프린터 IP", ip), inputGroup("포트", port)));
        box.addView(twoColumn(inputGroup("브랜드", brand), inputGroup("해상도", dpiSpinner)));
        box.addView(twoColumn(inputGroup("용지 유형", media), inputGroup("인쇄 후 작업", after)));
        box.addView(note("무선 LAN 전용입니다. 휴대폰과 프린터가 같은 네트워크에 있어야 합니다."));
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("프린터 설정")
                .setView(dialogScroll(box)).setNegativeButton("취소", null)
                .setPositiveButton("저장", null).create();
        dialog.setOnShowListener(x -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                float w = parseFloat(width, "라벨 가로");
                float h = parseFloat(height, "라벨 세로");
                int p = parseInt(port, "포트");
                if (w < 10 || h < 10 || w > 300 || h > 300) throw new IllegalArgumentException("라벨 크기는 10~300mm 범위로 입력하세요.");
                if (p < 1 || p > 65535) throw new IllegalArgumentException("포트는 1~65535 범위로 입력하세요.");
                if (ip.getText().toString().trim().isEmpty()) throw new IllegalArgumentException("프린터 IP를 입력하세요.");
                printerIp = ip.getText().toString().trim();
                printerPort = p;
                brandIndex = brand.getSelectedItemPosition();
                dpi = DPI_VALUES[dpiSpinner.getSelectedItemPosition()];
                mediaIndex = media.getSelectedItemPosition();
                afterIndex = after.getSelectedItemPosition();
                PrinterSettings checked = collectPrinterSettings(printQty);
                LabelCommandRenderer.render(checked, sampleTemplateForValidation());
                canvasView.resizeTemplate(w, h);
                saveSettings();
                setStatus("프린터 설정을 저장했습니다.", false);
                dialog.dismiss();
            } catch (RuntimeException ex) { showError(ex.getMessage()); }
        }));
        dialog.show();
    }

    private LabelTemplate sampleTemplateForValidation() {
        if (!canvasView.template().elements.isEmpty()) return resolvedTemplate();
        LabelTemplate sample = new LabelTemplate();
        sample.addText("설정 확인");
        return sample;
    }

    private void showPropertyDialog() {
        LabelElement selected = canvasView.template().selected();
        if (selected == null) { showError("먼저 캔버스에서 객체를 선택하세요."); return; }
        EditText value = edit(selected.value, InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        value.setSingleLine(false); value.setMinLines(2);
        EditText x = edit(format(selected.xMm), decimalType());
        EditText y = edit(format(selected.yMm), decimalType());
        EditText w = edit(format(selected.widthMm), decimalType());
        EditText h = edit(format(selected.heightMm), decimalType());
        EditText textSize = edit(format(selected.textSizeMm), decimalType());
        EditText stroke = edit(format(selected.strokeMm), decimalType());
        Spinner rotation = spinner(ROTATION_LABELS); rotation.setSelection(indexOf(ROTATION_VALUES, selected.rotation));
        LinearLayout box = dialogBox();
        if (!LabelElement.TYPE_BOX.equals(selected.type) && !LabelElement.TYPE_LINE.equals(selected.type)) box.addView(inputGroup("값 / {{CSV 열이름}}", value));
        box.addView(twoColumn(inputGroup("X(mm)", x), inputGroup("Y(mm)", y)));
        box.addView(twoColumn(inputGroup("W(mm)", w), inputGroup("H(mm)", h)));
        box.addView(twoColumn(inputGroup("글자 크기(mm)", textSize), inputGroup("선 두께(mm)", stroke)));
        box.addView(inputGroup("방향", rotation));
        box.addView(twoColumn(actionButton("복제", false, v -> { canvasView.duplicateSelected(); setStatus("객체를 복제했습니다.", false); }),
                actionButton("삭제", true, v -> { canvasView.deleteSelected(); setStatus("객체를 삭제했습니다.", false); })));
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle(typeLabel(selected.type) + " 속성")
                .setView(dialogScroll(box)).setNegativeButton("취소", null).setPositiveButton("적용", null).create();
        dialog.setOnShowListener(ignore -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                selected.value = value.getText().toString().trim();
                selected.xMm = parseFloat(x, "X"); selected.yMm = parseFloat(y, "Y");
                selected.widthMm = parseFloat(w, "W"); selected.heightMm = parseFloat(h, "H");
                selected.textSizeMm = parseFloat(textSize, "글자 크기"); selected.strokeMm = parseFloat(stroke, "선 두께");
                selected.rotation = ROTATION_VALUES[rotation.getSelectedItemPosition()];
                selected.clamp(canvasView.template().widthMm, canvasView.template().heightMm);
                canvasView.refresh(); updateSelection(selected); setStatus("객체 속성을 적용했습니다.", false); dialog.dismiss();
            } catch (RuntimeException ex) { showError(ex.getMessage()); }
        }));
        dialog.show();
    }

    private void showPrintDialog() {
        EditText qty = edit(String.valueOf(printQty), InputType.TYPE_CLASS_NUMBER);
        LinearLayout box = dialogBox();
        box.addView(inputGroup("출력 매수 (1~100)", qty));
        box.addView(note(selectedRow.isEmpty() ? "템플릿의 현재 값을 출력합니다." : "선택한 CSV 행의 값으로 출력합니다."));
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("출력")
                .setView(box).setNegativeButton("취소", null).setPositiveButton("출력 시작", null).create();
        dialog.setOnShowListener(ignore -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                int parsed = parseInt(qty, "출력 매수");
                if (parsed < 1 || parsed > 100) throw new IllegalArgumentException("출력 매수는 1~100 사이여야 합니다.");
                printQty = parsed; saveSettings(); dialog.dismiss(); sendLabel();
            } catch (RuntimeException ex) { showError(ex.getMessage()); }
        }));
        dialog.show();
    }

    private void checkConnection() {
        PrinterSettings settings;
        try { settings = collectPrinterSettings(printQty); }
        catch (RuntimeException ex) { showError(ex.getMessage()); return; }
        setBusy(true, "연결 확인 중...");
        new Thread(() -> {
            try {
                PrinterSender.checkConnection(settings);
                runOnUiThread(() -> { setBusy(false, "연결됨"); setStatus("프린터 LAN 연결을 확인했습니다.", false); });
            } catch (Exception ex) {
                runOnUiThread(() -> { setBusy(false, "연결 확인"); showError("프린터 연결 실패: " + safeMessage(ex)); });
            }
        }).start();
    }

    private void sendLabel() {
        PrinterSettings settings;
        LabelTemplate template;
        try {
            settings = collectPrinterSettings(printQty);
            template = resolvedTemplate();
            LabelCommandRenderer.render(settings, template);
        } catch (RuntimeException ex) { showError(ex.getMessage()); return; }
        setBusy(true, "전송 중...");
        new Thread(() -> {
            try {
                PrinterSender.send(settings, LabelCommandRenderer.render(settings, template));
                runOnUiThread(() -> { setBusy(false, "연결 확인"); setStatus("명령 전송 완료. 실제 라벨 배출 상태를 확인하세요.", false); });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    setBusy(false, "연결 확인");
                    showError("출력 전송 실패: " + safeMessage(ex) + "\n설정을 확인한 뒤 출력 버튼으로 다시 시도할 수 있습니다.");
                });
            }
        }).start();
    }

    private LabelTemplate resolvedTemplate() {
        return selectedRow.isEmpty() ? canvasView.template() : TemplateJson.resolve(canvasView.template(), selectedRow);
    }

    private PrinterSettings collectPrinterSettings(int qty) {
        if (printerIp.trim().isEmpty()) throw new IllegalArgumentException("프린터 IP를 설정하세요.");
        return new PrinterSettings(BRAND_VALUES[brandIndex], printerIp, printerPort, dpi, qty,
                MEDIA_VALUES[mediaIndex], AFTER_VALUES[afterIndex]);
    }

    private void showInputDialog(String title, String initial, ValueCallback callback) {
        EditText input = edit(initial, InputType.TYPE_CLASS_TEXT);
        input.setSelectAllOnFocus(true);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle(title).setView(input)
                .setNegativeButton("취소", null).setPositiveButton("추가", null).create();
        dialog.setOnShowListener(ignore -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String value = input.getText().toString().trim();
            if (value.isEmpty()) showError("값을 입력하세요.");
            else { callback.apply(value); dialog.dismiss(); }
        }));
        dialog.show();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        try {
            if (requestCode == SAVE_TEMPLATE) {
                writeText(uri, TemplateJson.encode(canvasView.template()));
                setStatus("JSON 템플릿을 저장했습니다.", false);
            } else if (requestCode == OPEN_TEMPLATE) {
                canvasView.loadTemplate(TemplateJson.decode(readText(uri)));
                setStatus("JSON 템플릿을 불러왔습니다.", false);
            } else if (requestCode == OPEN_CSV) {
                csvTable = CsvTable.parse(readText(uri));
                selectedRow.clear();
                dataStatus.setText("CSV 연결됨 | " + csvTable.rows.size() + "행 | 출력 행 미선택");
                setStatus("CSV를 가져왔습니다. DB 메뉴에서 행을 선택하세요.", false);
                showRowPicker();
            }
        } catch (Exception ex) { showError("파일 처리 실패: " + safeMessage(ex)); }
    }

    private void openDocument(String type, int code) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE); intent.setType(type); startActivityForResult(intent, code);
    }

    private void createDocument(String type, String name, int code) {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE); intent.setType(type); intent.putExtra(Intent.EXTRA_TITLE, name); startActivityForResult(intent, code);
    }

    private String readText(Uri uri) throws IOException {
        try (InputStream stream = getContentResolver().openInputStream(uri);
             BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            StringBuilder result = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) result.append(line).append('\n');
            return result.toString();
        }
    }

    private void writeText(Uri uri, String content) throws IOException {
        try (OutputStream stream = getContentResolver().openOutputStream(uri, "wt")) {
            if (stream == null) throw new IOException("저장 위치를 열 수 없습니다.");
            stream.write(content.getBytes(StandardCharsets.UTF_8)); stream.flush();
        }
    }

    private void loadSettings() {
        SharedPreferences p = getSharedPreferences("chaeumlab_printer", MODE_PRIVATE);
        printerIp = p.getString("ip", printerIp); printerPort = p.getInt("port", printerPort);
        dpi = p.getInt("dpi", dpi); printQty = p.getInt("qty", printQty);
        brandIndex = clampIndex(p.getInt("brand", 0), BRAND_VALUES.length);
        mediaIndex = clampIndex(p.getInt("media", 0), MEDIA_VALUES.length);
        afterIndex = clampIndex(p.getInt("after", 0), AFTER_VALUES.length);
    }

    private void saveSettings() {
        getSharedPreferences("chaeumlab_printer", MODE_PRIVATE).edit()
                .putString("ip", printerIp).putInt("port", printerPort).putInt("dpi", dpi).putInt("qty", printQty)
                .putInt("brand", brandIndex).putInt("media", mediaIndex).putInt("after", afterIndex).apply();
    }

    private void updateSelection(LabelElement element) {
        if (selectedTitle == null) return;
        selectedTitle.setText(element == null ? "선택된 객체 없음 | 캔버스를 터치하세요"
                : typeLabel(element.type) + " 선택 | X " + format(element.xMm) + " / Y " + format(element.yMm) + " / " + element.rotation + "도 | 눌러서 편집");
    }

    private String typeLabel(String type) {
        if (LabelElement.TYPE_BARCODE.equals(type)) return "1D 바코드";
        if (LabelElement.TYPE_QR.equals(type)) return "QR 코드";
        if (LabelElement.TYPE_BOX.equals(type)) return "박스";
        if (LabelElement.TYPE_LINE.equals(type)) return "선";
        return "텍스트";
    }

    private void setBusy(boolean busy, String connectionText) {
        sendButton.setEnabled(!busy); connectionButton.setEnabled(!busy);
        sendButton.setText(busy ? "처리 중" : "출력"); connectionButton.setText(busy ? connectionText : "연결 확인");
    }

    private void setStatus(String message, boolean error) {
        statusText.setText(message); statusText.setTextColor(error ? Color.rgb(254, 226, 226) : Color.rgb(226, 245, 232));
    }

    private void showError(String message) {
        setStatus(message, true);
        new AlertDialog.Builder(this).setTitle("확인 필요").setMessage(message).setPositiveButton("확인", null).show();
    }

    private LinearLayout card(String titleValue) {
        LinearLayout card = new LinearLayout(this); card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(11), dp(9), dp(11), dp(11)); card.setLayoutParams(bottomMargin(dp(8)));
        card.setBackground(rounded(COLOR_CARD, COLOR_LINE, dp(10)));
        if (Build.VERSION.SDK_INT >= 21) card.setElevation(dp(1));
        if (titleValue != null) { TextView title = text(titleValue, 15, COLOR_PRIMARY, true); title.setPadding(0, 0, 0, dp(7)); card.addView(title); }
        return card;
    }

    private LinearLayout dialogBox() { LinearLayout box = new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL); box.setPadding(dp(18), dp(8), dp(18), dp(6)); return box; }
    private ScrollView dialogScroll(View child) { ScrollView scroll = new ScrollView(this); scroll.addView(child); return scroll; }
    private LinearLayout inputGroup(String labelValue, View input) { LinearLayout g = new LinearLayout(this); g.setOrientation(LinearLayout.VERTICAL); g.setPadding(0, dp(5), 0, dp(4)); TextView label = text(labelValue, 12, COLOR_TEXT, true); label.setPadding(0, 0, 0, dp(3)); g.addView(label); g.addView(input); return g; }
    private LinearLayout twoColumn(View left, View right) { LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setBaselineAligned(false); LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1); lp.setMargins(0, 0, dp(5), 0); row.addView(left, lp); LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1); rp.setMargins(dp(5), 0, 0, 0); row.addView(right, rp); return row; }
    private LinearLayout buttonRow(View a, View b, View c) { LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.addView(a, buttonParams(0, 3)); row.addView(b, buttonParams(3, 3)); row.addView(c, buttonParams(3, 0)); return row; }
    private LinearLayout.LayoutParams buttonParams(int l, int r) { LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1); p.setMargins(dp(l), dp(3), dp(r), dp(3)); return p; }
    private EditText edit(String value, int type) { EditText f = new EditText(this); f.setSingleLine(true); f.setText(value); f.setInputType(type); f.setTextSize(14); f.setTextColor(COLOR_TEXT); f.setPadding(dp(10), 0, dp(10), 0); f.setMinHeight(dp(42)); f.setBackground(rounded(Color.WHITE, COLOR_LINE, dp(8))); return f; }
    private Spinner spinner(String[] values) { Spinner s = new Spinner(this); ArrayAdapter<String> a = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, values); a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item); s.setAdapter(a); s.setMinimumHeight(dp(42)); s.setBackground(rounded(Color.WHITE, COLOR_LINE, dp(8))); return s; }
    private Button actionButton(String value, boolean danger, View.OnClickListener listener) { Button b = new Button(this); b.setText(value); b.setAllCaps(false); b.setTextSize(11); b.setTypeface(Typeface.DEFAULT_BOLD); b.setMinHeight(dp(40)); b.setTextColor(danger ? COLOR_DANGER : COLOR_PRIMARY); b.setBackground(rounded(Color.WHITE, danger ? Color.rgb(252, 165, 165) : COLOR_LINE, dp(8))); b.setOnClickListener(listener); return b; }
    private TextView text(String value, int size, int color, boolean bold) { TextView t = new TextView(this); t.setText(value); t.setTextSize(size); t.setTextColor(color); if (bold) t.setTypeface(Typeface.DEFAULT_BOLD); return t; }
    private TextView note(String value) { TextView t = text(value, 11, COLOR_MUTED, false); t.setPadding(0, dp(6), 0, dp(3)); return t; }
    private GradientDrawable rounded(int fill, int stroke, int radius) { GradientDrawable d = new GradientDrawable(); d.setColor(fill); d.setCornerRadius(radius); d.setStroke(1, stroke); return d; }
    private GradientDrawable gradient(int start, int end, int radius) { GradientDrawable d = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{start, end}); d.setCornerRadius(radius); return d; }
    private LinearLayout.LayoutParams bottomMargin(int bottom) { LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT); p.setMargins(0, 0, 0, bottom); return p; }
    private int parseInt(EditText field, String label) { try { return Integer.parseInt(field.getText().toString().trim()); } catch (NumberFormatException ex) { throw new IllegalArgumentException(label + " 값을 숫자로 입력하세요."); } }
    private float parseFloat(EditText field, String label) { try { return Float.parseFloat(field.getText().toString().trim()); } catch (NumberFormatException ex) { throw new IllegalArgumentException(label + " 값을 숫자로 입력하세요."); } }
    private int decimalType() { return InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED; }
    private String format(float value) { return value == Math.round(value) ? String.valueOf(Math.round(value)) : String.format(java.util.Locale.US, "%.1f", value); }
    private int indexOf(int[] values, int target) { for (int i = 0; i < values.length; i++) if (values[i] == target) return i; return 0; }
    private int clampIndex(int value, int length) { return Math.max(0, Math.min(value, length - 1)); }
    private String safeMessage(Exception ex) { return ex.getMessage() == null ? ex.getClass().getSimpleName() : ex.getMessage(); }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private void animateEntrance() { for (int i = 0; i < root.getChildCount(); i++) { View child = root.getChildAt(i); child.setAlpha(0f); child.setTranslationY(dp(8)); child.animate().alpha(1f).translationY(0f).setStartDelay(i * 35L).setDuration(180).setInterpolator(new DecelerateInterpolator()).start(); } }

    private interface ValueCallback { void apply(String value); }
}
