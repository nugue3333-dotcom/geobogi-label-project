package com.geoboki.labeldesigner;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class CsvTable {
    final List<String> headers = new ArrayList<>();
    final List<Map<String, String>> rows = new ArrayList<>();

    static CsvTable parse(String input) {
        CsvTable table = new CsvTable();
        List<List<String>> records = parseRecords(input == null ? "" : input.replace("\uFEFF", ""));
        if (records.isEmpty()) throw new IllegalArgumentException("CSV 파일에 데이터가 없습니다.");
        for (String header : records.get(0)) {
            String normalized = header.trim();
            if (normalized.isEmpty()) throw new IllegalArgumentException("CSV 열 이름은 비어 있을 수 없습니다.");
            if (table.headers.contains(normalized)) throw new IllegalArgumentException("CSV 열 이름이 중복되었습니다: " + normalized);
            table.headers.add(normalized);
        }
        for (int i = 1; i < records.size(); i++) {
            List<String> record = records.get(i);
            boolean empty = true;
            Map<String, String> row = new LinkedHashMap<>();
            for (int column = 0; column < table.headers.size(); column++) {
                String value = column < record.size() ? record.get(column).trim() : "";
                if (!value.isEmpty()) empty = false;
                row.put(table.headers.get(column), value);
            }
            if (!empty) table.rows.add(row);
        }
        if (table.rows.isEmpty()) throw new IllegalArgumentException("CSV 파일에 출력할 행이 없습니다.");
        return table;
    }

    List<Integer> search(String query) {
        String needle = query == null ? "" : query.trim().toLowerCase(Locale.ROOT);
        List<Integer> indexes = new ArrayList<>();
        for (int i = 0; i < rows.size(); i++) {
            if (needle.isEmpty() || contains(rows.get(i), needle)) indexes.add(i);
        }
        return indexes;
    }

    String summary(int index) {
        Map<String, String> row = rows.get(index);
        StringBuilder result = new StringBuilder();
        for (String header : headers) {
            if (result.length() > 0) result.append("  |  ");
            result.append(header).append(": ").append(row.get(header));
        }
        return result.toString();
    }

    private static boolean contains(Map<String, String> row, String needle) {
        for (Map.Entry<String, String> item : row.entrySet()) {
            if (item.getKey().toLowerCase(Locale.ROOT).contains(needle)) return true;
            if (item.getValue().toLowerCase(Locale.ROOT).contains(needle)) return true;
        }
        return false;
    }

    private static List<List<String>> parseRecords(String text) {
        List<List<String>> records = new ArrayList<>();
        List<String> row = new ArrayList<>();
        StringBuilder value = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (ch == '"') {
                if (quoted && i + 1 < text.length() && text.charAt(i + 1) == '"') {
                    value.append('"');
                    i++;
                } else quoted = !quoted;
            } else if (ch == ',' && !quoted) {
                row.add(value.toString());
                value.setLength(0);
            } else if ((ch == '\n' || ch == '\r') && !quoted) {
                if (ch == '\r' && i + 1 < text.length() && text.charAt(i + 1) == '\n') i++;
                row.add(value.toString());
                value.setLength(0);
                records.add(row);
                row = new ArrayList<>();
            } else value.append(ch);
        }
        if (value.length() > 0 || !row.isEmpty()) {
            row.add(value.toString());
            records.add(row);
        }
        return records;
    }
}
