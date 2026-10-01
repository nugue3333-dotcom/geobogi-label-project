import Foundation
import SwiftUI
import UniformTypeIdentifiers

struct TransferDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.json, .commaSeparatedText, .plainText] }
    var data: Data

    init(data: Data = Data()) {
        self.data = data
    }

    init(configuration: ReadConfiguration) throws {
        guard let data = configuration.file.regularFileContents else {
            throw MobileValidationError(message: "파일 내용을 읽을 수 없습니다.")
        }
        self.data = data
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: data)
    }
}

enum CSVDatabaseService {
    struct Table {
        let columns: [String]
        let rows: [DatabaseRow]
    }

    static func parse(data: Data) throws -> Table {
        let text = decode(data: data)
        let records = parseRecords(text)
        guard let header = records.first, !header.isEmpty else {
            throw MobileValidationError(message: "CSV 파일에 열 이름이 없습니다.")
        }
        let columns = header.enumerated().map { index, value in
            let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? "열\(index + 1)" : trimmed
        }
        let rows = records.dropFirst().filter { record in
            record.contains { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        }.map { record in
            var values: [String: String] = [:]
            for (index, column) in columns.enumerated() {
                values[column] = index < record.count ? record[index] : ""
            }
            return DatabaseRow(values: values)
        }
        return Table(columns: columns, rows: rows)
    }

    private static func decode(data: Data) -> String {
        if let utf8 = String(data: data, encoding: .utf8) { return utf8 }
        if let euckr = String(data: data, encoding: .init(rawValue: 0x80000422)) { return euckr }
        return String(decoding: data, as: UTF8.self)
    }

    private static func parseRecords(_ text: String) -> [[String]] {
        var rows: [[String]] = []
        var row: [String] = []
        var field = ""
        var quoted = false
        let characters = Array(text.replacingOccurrences(of: "\r\n", with: "\n"))
        var index = 0
        while index < characters.count {
            let character = characters[index]
            if character == "\"" {
                if quoted, index + 1 < characters.count, characters[index + 1] == "\"" {
                    field.append("\"")
                    index += 1
                } else {
                    quoted.toggle()
                }
            } else if character == ",", !quoted {
                row.append(field)
                field = ""
            } else if character == "\n", !quoted {
                row.append(field)
                rows.append(row)
                row = []
                field = ""
            } else {
                field.append(character)
            }
            index += 1
        }
        if !field.isEmpty || !row.isEmpty {
            row.append(field)
            rows.append(row)
        }
        return rows
    }
}
