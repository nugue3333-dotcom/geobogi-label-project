import CoreFoundation
import Foundation

enum LabelCommandRenderer {
    static func render(
        settings: PrinterSettings,
        template: LabelTemplate,
        dataRow: [String: String],
        quantity: Int
    ) throws -> RenderedCommand {
        guard (1...100).contains(quantity) else {
            throw MobileValidationError(message: "출력 매수는 1~100 범위여야 합니다.")
        }
        let command: String
        let encoding: String.Encoding
        let fileExtension: String
        switch settings.brand {
        case .tsc:
            command = try renderTSPL(settings: settings, template: template, row: dataRow, quantity: quantity)
            encoding = .utf8
            fileExtension = "tspl"
        case .bixolon:
            guard settings.mediaHandling != .peeler else {
                throw MobileValidationError(message: "빅솔론 SLCS 필러는 공식 검증 명령이 없어 사용할 수 없습니다.")
            }
            command = try renderSLCS(settings: settings, template: template, row: dataRow, quantity: quantity)
            encoding = koreanEncoding
            fileExtension = "slcs"
        case .zebra:
            command = try renderZPL(settings: settings, template: template, row: dataRow, quantity: quantity)
            encoding = .utf8
            fileExtension = "zpl"
        case .sewoo:
            guard settings.mediaHandling == .tearOff else {
                throw MobileValidationError(message: "세우테크는 승인된 모델별 근거가 없어 뜯어내기만 사용할 수 있습니다.")
            }
            command = try renderZPL(settings: settings, template: template, row: dataRow, quantity: quantity)
            encoding = .utf8
            fileExtension = "zpl"
        }
        guard let data = command.data(using: encoding) else {
            throw MobileValidationError(message: "프린터 명령 인코딩에 실패했습니다.")
        }
        return RenderedCommand(text: command, data: data, fileExtension: fileExtension)
    }

    static func preview(settings: PrinterSettings, template: LabelTemplate, row: [String: String]) -> String {
        (try? render(settings: settings, template: template, dataRow: row, quantity: 1).text) ?? "입력값을 확인하세요."
    }

    private static func renderTSPL(settings: PrinterSettings, template: LabelTemplate, row: [String: String], quantity: Int) throws -> String {
        var command = "SIZE \(format(template.widthMm)) mm,\(format(template.heightMm)) mm\n"
        command += tsplMedia(settings)
        command += settings.printMethod == .thermalTransfer ? "SET RIBBON ON\n" : "SET RIBBON OFF\n"
        command += "CODEPAGE UTF-8\nDIRECTION 1\nREFERENCE 0,0\nCLS\n"
        for element in template.elements {
            command += try tsplElement(element, row: row, dpi: settings.dpi.rawValue)
        }
        switch settings.mediaHandling {
        case .tearOff: command += "SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n"
        case .cutter: command += "SET PEEL OFF\nSET CUTTER 1\n"
        case .peeler: command += "SET CUTTER OFF\nSET PEEL ON\n"
        }
        return command + "PRINT 1,\(quantity)\n"
    }

    private static func tsplElement(_ element: LabelElement, row: [String: String], dpi: Int) throws -> String {
        let box = dotBox(element, dpi: dpi)
        let rotation = element.rotation.rawValue
        let value = resolve(element.value, row: row)
        switch element.kind {
        case .text:
            let scale = max(1, min(10, Int((element.fontSizeMm * Double(dpi) / 25.4 / 16).rounded())))
            return "TEXT \(box.x),\(box.y),\"3\",\(rotation),\(scale),\(scale),\"\(sanitizeTSPL(value))\"\n"
        case .barcode:
            let height = max(12, box.h - 18)
            return "BARCODE \(box.x),\(box.y),\"128\",\(height),1,\(rotation),2,4,\"\(try barcodeValue(value))\"\n"
        case .qr:
            let cell = max(1, min(10, min(box.w, box.h) / 29))
            return "QRCODE \(box.x),\(box.y),M,\(cell),A,\(rotation),M2,S7,\"\(try barcodeValue(value))\"\n"
        case .box:
            return "BOX \(box.x),\(box.y),\(box.x + box.w),\(box.y + box.h),\(strokeDots(element, dpi: dpi))\n"
        case .line:
            let thickness = strokeDots(element, dpi: dpi)
            if element.rotation == .degree90 || element.rotation == .degree270 {
                return "BAR \(box.x),\(box.y),\(thickness),\(max(1, box.h))\n"
            }
            return "BAR \(box.x),\(box.y),\(max(1, box.w)),\(thickness)\n"
        }
    }

    private static func renderSLCS(settings: PrinterSettings, template: LabelTemplate, row: [String: String], quantity: Int) throws -> String {
        let width = dots(template.widthMm, dpi: settings.dpi.rawValue)
        let height = dots(template.heightMm, dpi: settings.dpi.rawValue)
        let gap = dots(settings.gapMm, dpi: settings.dpi.rawValue)
        var command = "CB\nSS3\nSD20\nCS13,0\n"
        command += settings.printMethod == .thermalTransfer ? "STt\n" : "STd\n"
        command += settings.mediaHandling == .cutter ? "CUTy\n" : "CUTn\n"
        command += "SW\(width)\n"
        switch settings.mediaType {
        case .gap: command += "SL\(height),\(gap),G\n"
        case .blackMark: command += "SL\(height),\(gap),B\n"
        case .continuous: command += "SL\(height),0,C\n"
        }
        command += "SOT\n"
        for element in template.elements {
            command += try slcsElement(element, row: row, dpi: settings.dpi.rawValue)
        }
        return command + "P\(quantity)\n"
    }

    private static func slcsElement(_ element: LabelElement, row: [String: String], dpi: Int) throws -> String {
        let box = dotBox(element, dpi: dpi)
        let value = resolve(element.value, row: row)
        switch element.kind {
        case .text:
            let rotation = element.rotation.rawValue
            return "T\(box.x),\(box.y),K,1,1,\(rotation),0,N,N,'\(sanitizeSLCS(value))'\r\n"
        case .barcode:
            let height = max(12, box.h - 18)
            return "B1\(box.x),\(box.y),1,2,4,\(height),\(element.rotation.rawValue),1,'\(try barcodeValue(value))'\r\n"
        case .qr:
            let cell = max(1, min(10, min(box.w, box.h) / 29))
            return "B2\(box.x),\(box.y),Q,2,M,\(cell),\(element.rotation.rawValue),'\(try barcodeValue(value))'\r\n"
        case .box:
            let t = strokeDots(element, dpi: dpi)
            return "R\(box.x),\(box.y),\(box.x + box.w),\(box.y + box.h),\(t)\r\n"
        case .line:
            let t = strokeDots(element, dpi: dpi)
            if element.rotation == .degree90 || element.rotation == .degree270 {
                return "R\(box.x),\(box.y),\(box.x + t),\(box.y + box.h),\(t)\r\n"
            }
            return "R\(box.x),\(box.y),\(box.x + box.w),\(box.y + t),\(t)\r\n"
        }
    }

    private static func renderZPL(settings: PrinterSettings, template: LabelTemplate, row: [String: String], quantity: Int) throws -> String {
        let dpi = settings.dpi.rawValue
        var command = "^XA\n^CI28\n"
        command += settings.printMethod == .thermalTransfer ? "^MTT\n" : "^MTD\n"
        switch settings.mediaHandling {
        case .tearOff: command += "^MMT\n"
        case .cutter: command += "^MMC\n"
        case .peeler: command += "^MMP\n"
        }
        switch settings.mediaType {
        case .gap: command += "^MNY\n"
        case .blackMark: command += "^MNM,0\n"
        case .continuous: command += "^MNN\n"
        }
        command += "^PW\(dots(template.widthMm, dpi: dpi))\n^LL\(dots(template.heightMm, dpi: dpi))\n"
        for element in template.elements {
            command += try zplElement(element, row: row, dpi: dpi)
        }
        return command + "^PQ\(quantity)\n^XZ\n"
    }

    private static func zplElement(_ element: LabelElement, row: [String: String], dpi: Int) throws -> String {
        let box = dotBox(element, dpi: dpi)
        let orientation: String
        switch element.rotation {
        case .degree0: orientation = "N"
        case .degree90: orientation = "R"
        case .degree180: orientation = "I"
        case .degree270: orientation = "B"
        }
        let value = sanitizeZPL(resolve(element.value, row: row))
        switch element.kind {
        case .text:
            let font = max(12, dots(element.fontSizeMm, dpi: dpi))
            return "^FO\(box.x),\(box.y)^A0\(orientation),\(font),\(font)^FD\(value)^FS\n"
        case .barcode:
            return "^FO\(box.x),\(box.y)^BY2,2,\(box.h)^BC\(orientation),\(box.h),Y,N,N^FD\(try barcodeValue(value))^FS\n"
        case .qr:
            let cell = max(1, min(10, min(box.w, box.h) / 29))
            return "^FO\(box.x),\(box.y)^BQ\(orientation),2,\(cell)^FDLA,\(try barcodeValue(value))^FS\n"
        case .box:
            return "^FO\(box.x),\(box.y)^GB\(box.w),\(box.h),\(strokeDots(element, dpi: dpi))^FS\n"
        case .line:
            let t = strokeDots(element, dpi: dpi)
            if element.rotation == .degree90 || element.rotation == .degree270 {
                return "^FO\(box.x),\(box.y)^GB\(t),\(max(1, box.h)),\(t)^FS\n"
            }
            return "^FO\(box.x),\(box.y)^GB\(max(1, box.w)),\(t),\(t)^FS\n"
        }
    }

    private static func resolve(_ source: String, row: [String: String]) -> String {
        var result = source
        for (column, value) in row {
            result = result.replacingOccurrences(of: "{{\(column)}}", with: value)
        }
        return result
    }

    private static func dotBox(_ element: LabelElement, dpi: Int) -> (x: Int, y: Int, w: Int, h: Int) {
        (dots(element.xMm, dpi: dpi), dots(element.yMm, dpi: dpi), max(1, dots(element.widthMm, dpi: dpi)), max(1, dots(element.heightMm, dpi: dpi)))
    }

    private static func dots(_ mm: Double, dpi: Int) -> Int {
        Int((mm / 25.4 * Double(dpi)).rounded())
    }

    private static func strokeDots(_ element: LabelElement, dpi: Int) -> Int {
        max(1, dots(element.strokeMm, dpi: dpi))
    }

    private static func barcodeValue(_ value: String) throws -> String {
        let clean = value.filter { scalar in
            scalar.unicodeScalars.allSatisfy { (32...126).contains($0.value) }
        }.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { throw MobileValidationError(message: "바코드 값을 입력하세요.") }
        return clean
    }

    private static func tsplMedia(_ settings: PrinterSettings) -> String {
        switch settings.mediaType {
        case .gap: return "GAP \(format(settings.gapMm)) mm,0 mm\n"
        case .blackMark: return "BLINE \(format(settings.gapMm)) mm,0 mm\n"
        case .continuous: return "GAP 0,0\n"
        }
    }

    private static func format(_ value: Double) -> String {
        value.rounded() == value ? String(Int(value)) : String(format: "%.2f", value)
    }

    private static func sanitizeTSPL(_ value: String) -> String { value.replacingOccurrences(of: "\"", with: "") }
    private static func sanitizeSLCS(_ value: String) -> String { value.replacingOccurrences(of: "'", with: "") }
    private static func sanitizeZPL(_ value: String) -> String {
        value.replacingOccurrences(of: "^", with: "").replacingOccurrences(of: "~", with: "")
    }

    private static let koreanEncoding = String.Encoding(
        rawValue: CFStringConvertEncodingToNSStringEncoding(CFStringEncoding(0x0422))
    )
}
