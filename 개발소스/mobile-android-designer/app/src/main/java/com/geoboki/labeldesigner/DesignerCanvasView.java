package com.geoboki.labeldesigner;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.DashPathEffect;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

final class DesignerCanvasView extends View {
    interface SelectionListener {
        void onSelectionChanged(LabelElement element);
    }

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF labelRect = new RectF();
    private final LabelTemplate template = new LabelTemplate();
    private SelectionListener listener;
    private float scale = 1f;
    private float dragStartXMm;
    private float dragStartYMm;
    private float elementStartXMm;
    private float elementStartYMm;
    private boolean dragging;

    DesignerCanvasView(Context context) {
        super(context);
        init();
    }

    DesignerCanvasView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    LabelTemplate template() {
        return template;
    }

    void setSelectionListener(SelectionListener listener) {
        this.listener = listener;
    }

    void addText(String value) {
        notifySelection(template.addText(value));
        invalidate();
    }

    void addBarcode(String value) {
        notifySelection(template.addBarcode(value));
        invalidate();
    }

    void addQr(String value) {
        notifySelection(template.addQr(value));
        invalidate();
    }

    void addBox() {
        notifySelection(template.addBox());
        invalidate();
    }

    void addLine() {
        notifySelection(template.addLine());
        invalidate();
    }

    void newBlankTemplate() {
        template.clear();
        notifySelection(null);
        invalidate();
    }

    void loadTemplate(LabelTemplate loaded) {
        template.replaceWith(loaded);
        notifySelection(null);
        invalidate();
    }

    void deleteSelected() {
        template.deleteSelected();
        notifySelection(null);
        invalidate();
    }

    void duplicateSelected() {
        template.duplicateSelected();
        notifySelection(template.selected());
        invalidate();
    }

    void centerSelected() {
        template.centerSelected();
        notifySelection(template.selected());
        invalidate();
    }

    void resizeTemplate(float widthMm, float heightMm) {
        template.resize(widthMm, heightMm);
        notifySelection(template.selected());
        invalidate();
    }

    void refresh() {
        template.normalize();
        invalidate();
    }

    private void init() {
        setLayerType(View.LAYER_TYPE_SOFTWARE, null);
        setBackgroundColor(Color.rgb(232, 238, 245));
        textPaint.setColor(Color.rgb(17, 24, 39));
        textPaint.setSubpixelText(true);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        computeLabelRect();
        drawWorkspace(canvas);
        drawGrid(canvas);
        drawElements(canvas);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
            if (getParent() != null) {
                getParent().requestDisallowInterceptTouchEvent(true);
            }
            LabelElement hit = hitTest(event.getX(), event.getY());
            template.selectedId = hit == null ? null : hit.id;
            notifySelection(hit);
            dragging = hit != null;
            if (hit != null) {
                dragStartXMm = pxToMmX(event.getX());
                dragStartYMm = pxToMmY(event.getY());
                elementStartXMm = hit.xMm;
                elementStartYMm = hit.yMm;
            }
            invalidate();
            return true;
        }
        if (event.getActionMasked() == MotionEvent.ACTION_MOVE && dragging) {
            LabelElement selected = template.selected();
            if (selected != null) {
                selected.xMm = elementStartXMm + (pxToMmX(event.getX()) - dragStartXMm);
                selected.yMm = elementStartYMm + (pxToMmY(event.getY()) - dragStartYMm);
                selected.clamp(template.widthMm, template.heightMm);
                notifySelection(selected);
                invalidate();
            }
            return true;
        }
        if (event.getActionMasked() == MotionEvent.ACTION_UP || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
            dragging = false;
            if (getParent() != null) {
                getParent().requestDisallowInterceptTouchEvent(false);
            }
            return true;
        }
        return true;
    }

    private void computeLabelRect() {
        float availableW = Math.max(1, getWidth() - dp(28));
        float availableH = Math.max(1, getHeight() - dp(28));
        scale = Math.min(availableW / template.widthMm, availableH / template.heightMm);
        float labelW = template.widthMm * scale;
        float labelH = template.heightMm * scale;
        float left = (getWidth() - labelW) / 2f;
        float top = (getHeight() - labelH) / 2f;
        labelRect.set(left, top, left + labelW, top + labelH);
    }

    private void drawWorkspace(Canvas canvas) {
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.rgb(214, 224, 235));
        canvas.drawRoundRect(labelRect.left + dp(6), labelRect.top + dp(6), labelRect.right + dp(6), labelRect.bottom + dp(6), dp(12), dp(12), paint);
        paint.setColor(Color.WHITE);
        canvas.drawRoundRect(labelRect, dp(10), dp(10), paint);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(dp(1));
        paint.setColor(Color.rgb(148, 163, 184));
        canvas.drawRoundRect(labelRect, dp(10), dp(10), paint);
    }

    private void drawGrid(Canvas canvas) {
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(1f);
        paint.setColor(Color.rgb(226, 232, 240));
        paint.setPathEffect(null);
        for (int x = 5; x < template.widthMm; x += 5) {
            float px = labelRect.left + x * scale;
            canvas.drawLine(px, labelRect.top, px, labelRect.bottom, paint);
        }
        for (int y = 5; y < template.heightMm; y += 5) {
            float py = labelRect.top + y * scale;
            canvas.drawLine(labelRect.left, py, labelRect.right, py, paint);
        }
    }

    private void drawElements(Canvas canvas) {
        for (LabelElement element : template.elements) {
            RectF rect = elementRect(element);
            if (LabelElement.TYPE_BARCODE.equals(element.type)) {
                drawBarcode(canvas, element, rect);
            } else if (LabelElement.TYPE_QR.equals(element.type)) {
                drawQr(canvas, element, rect);
            } else if (LabelElement.TYPE_BOX.equals(element.type)) {
                drawBox(canvas, element, rect);
            } else if (LabelElement.TYPE_LINE.equals(element.type)) {
                drawLine(canvas, element, rect);
            } else {
                drawTextElement(canvas, element, rect);
            }
            if (element.id.equals(template.selectedId)) {
                drawSelection(canvas, rect);
            }
        }
    }

    private void drawTextElement(Canvas canvas, LabelElement element, RectF rect) {
        canvas.save();
        canvas.rotate(element.rotation, rect.centerX(), rect.centerY());
        textPaint.setColor(Color.rgb(17, 24, 39));
        textPaint.setTextSize(Math.max(10f, element.textSizeMm * scale));
        textPaint.setFakeBoldText(false);
        float baseline = rect.top + Math.min(rect.height() - dp(2), -textPaint.ascent());
        canvas.drawText(element.value, rect.left + dp(2), baseline, textPaint);
        canvas.restore();
    }

    private void drawBarcode(Canvas canvas, LabelElement element, RectF rect) {
        canvas.save();
        canvas.rotate(element.rotation, rect.centerX(), rect.centerY());
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.TRANSPARENT);
        canvas.drawRect(rect, paint);
        paint.setColor(Color.rgb(17, 24, 39));

        String value = element.value == null ? "" : element.value;
        int bars = Math.max(24, value.length() * 7);
        float x = rect.left + dp(2);
        float available = Math.max(1f, rect.width() - dp(4));
        float unit = available / bars;
        int seed = Math.max(1, value.hashCode());
        for (int i = 0; i < bars; i++) {
            int bit = Math.abs(seed + i * 31 + (i < value.length() ? value.charAt(i) : i)) % 5;
            if (bit == 0 || bit == 2 || bit == 4) {
                float barW = Math.max(1f, unit * (bit == 4 ? 1.7f : 1f));
                canvas.drawRect(x, rect.top + dp(2), x + barW, rect.bottom - dp(8), paint);
            }
            x += unit;
        }
        textPaint.setColor(Color.rgb(17, 24, 39));
        textPaint.setTextSize(Math.max(9f, element.textSizeMm * scale));
        textPaint.setTextAlign(Paint.Align.CENTER);
        canvas.drawText(value, rect.centerX(), rect.bottom - dp(1), textPaint);
        textPaint.setTextAlign(Paint.Align.LEFT);
        canvas.restore();
    }

    private void drawQr(Canvas canvas, LabelElement element, RectF rect) {
        canvas.save();
        canvas.rotate(element.rotation, rect.centerX(), rect.centerY());
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.WHITE);
        canvas.drawRect(rect, paint);
        paint.setColor(Color.rgb(17, 24, 39));
        int cells = 21;
        float size = Math.min(rect.width(), rect.height()) / cells;
        int seed = Math.max(1, element.value.hashCode());
        for (int row = 0; row < cells; row++) {
            for (int col = 0; col < cells; col++) {
                boolean finder = (row < 7 && col < 7) || (row < 7 && col >= cells - 7) || (row >= cells - 7 && col < 7);
                boolean dark = finder ? (row % 6 == 0 || col % 6 == 0 || (row % 6 >= 2 && row % 6 <= 4 && col % 6 >= 2 && col % 6 <= 4))
                        : Math.abs(seed + row * 31 + col * 17) % 3 == 0;
                if (dark) canvas.drawRect(rect.left + col * size, rect.top + row * size,
                        rect.left + (col + 1) * size, rect.top + (row + 1) * size, paint);
            }
        }
        canvas.restore();
    }

    private void drawBox(Canvas canvas, LabelElement element, RectF rect) {
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(Math.max(1f, element.strokeMm * scale));
        paint.setColor(Color.rgb(17, 24, 39));
        canvas.drawRect(rect, paint);
    }

    private void drawLine(Canvas canvas, LabelElement element, RectF rect) {
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(Math.max(1f, element.strokeMm * scale));
        paint.setColor(Color.rgb(17, 24, 39));
        if (element.rotation == 90 || element.rotation == 270) {
            canvas.drawLine(rect.left, rect.top, rect.left, rect.top + element.widthMm * scale, paint);
        } else {
            canvas.drawLine(rect.left, rect.top, rect.right, rect.top, paint);
        }
    }

    private void drawSelection(Canvas canvas, RectF rect) {
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(dp(2));
        paint.setColor(Color.rgb(0, 128, 92));
        paint.setPathEffect(new DashPathEffect(new float[]{dp(5), dp(3)}, 0));
        canvas.drawRoundRect(rect, dp(4), dp(4), paint);
        paint.setPathEffect(null);
        paint.setStyle(Paint.Style.FILL);
        canvas.drawCircle(rect.right, rect.bottom, dp(4), paint);
    }

    private LabelElement hitTest(float x, float y) {
        for (int i = template.elements.size() - 1; i >= 0; i--) {
            LabelElement element = template.elements.get(i);
            if (elementRect(element).contains(x, y)) {
                return element;
            }
        }
        return null;
    }

    private RectF elementRect(LabelElement element) {
        return new RectF(
                labelRect.left + element.xMm * scale,
                labelRect.top + element.yMm * scale,
                labelRect.left + (element.xMm + element.widthMm) * scale,
                labelRect.top + (element.yMm + element.heightMm) * scale
        );
    }

    private float pxToMmX(float px) {
        return (px - labelRect.left) / scale;
    }

    private float pxToMmY(float py) {
        return (py - labelRect.top) / scale;
    }

    private void notifySelection(LabelElement element) {
        if (listener != null) {
            listener.onSelectionChanged(element);
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
