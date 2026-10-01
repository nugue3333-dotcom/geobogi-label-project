import Foundation

enum PrinterBrand: String, Codable, CaseIterable, Identifiable {
    case tsc, bixolon, zebra, sewoo

    var id: String { rawValue }
    var title: String {
        switch self {
        case .tsc: return "TSC"
        case .bixolon: return "BIXOLON / 빅솔론"
        case .zebra: return "Zebra / 제브라"
        case .sewoo: return "SEWOO / 세우테크"
        }
    }
}

enum PrintMethod: String, Codable, CaseIterable, Identifiable {
    case directThermal = "direct_thermal"
    case thermalTransfer = "thermal_transfer"
    var id: String { rawValue }
    var title: String { self == .directThermal ? "감열 / 리본 없음" : "열전사 / 리본 사용" }
}

enum MediaHandling: String, Codable, CaseIterable, Identifiable {
    case tearOff = "tear_off", cutter, peeler
    var id: String { rawValue }
    var title: String {
        switch self {
        case .tearOff: return "뜯어내기"
        case .cutter: return "커터"
        case .peeler: return "필러"
        }
    }
}

enum MediaType: String, Codable, CaseIterable, Identifiable {
    case gap, blackMark = "black_mark", continuous
    var id: String { rawValue }
    var title: String {
        switch self {
        case .gap: return "갭 용지"
        case .blackMark: return "블랙마크 용지"
        case .continuous: return "연속 용지"
        }
    }
}

enum PrinterDPI: Int, Codable, CaseIterable, Identifiable {
    case dpi203 = 203, dpi300 = 300, dpi600 = 600
    var id: Int { rawValue }
    var title: String { "\(rawValue) dpi" }
}

struct PrinterSettings: Codable, Equatable {
    var host = "192.168.0.130"
    var port = 9100
    var brand: PrinterBrand = .tsc
    var printMethod: PrintMethod = .directThermal
    var mediaHandling: MediaHandling = .tearOff
    var mediaType: MediaType = .gap
    var gapMm = 3.0
    var dpi: PrinterDPI = .dpi203
}

enum LabelElementKind: String, Codable, CaseIterable, Identifiable {
    case text, barcode, qr, box, line
    var id: String { rawValue }
    var title: String {
        switch self {
        case .text: return "텍스트"
        case .barcode: return "1D 바코드"
        case .qr: return "QR 코드"
        case .box: return "박스"
        case .line: return "선"
        }
    }
    var symbol: String {
        switch self {
        case .text: return "textformat"
        case .barcode: return "barcode"
        case .qr: return "qrcode"
        case .box: return "square"
        case .line: return "line.diagonal"
        }
    }
}

enum ElementRotation: Int, Codable, CaseIterable, Identifiable {
    case degree0 = 0, degree90 = 90, degree180 = 180, degree270 = 270
    var id: Int { rawValue }
    var title: String { "\(rawValue)°" }
}

struct LabelElement: Codable, Equatable, Identifiable {
    var id = UUID()
    var kind: LabelElementKind
    var value: String
    var field: String = ""
    var xMm: Double
    var yMm: Double
    var widthMm: Double
    var heightMm: Double
    var rotation: ElementRotation = .degree0
    var fontSizeMm: Double = 3.5
    var strokeMm: Double = 0.35

    private enum CodingKeys: String, CodingKey {
        case id, kind, value, field, rotation
        case type, text, x, y, width, height
        case xMm, yMm, widthMm, heightMm, fontSizeMm, strokeMm
        case fontSize = "font_size"
        case strokeWidth = "stroke_width"
    }

    init(
        id: UUID = UUID(),
        kind: LabelElementKind,
        value: String,
        field: String = "",
        xMm: Double,
        yMm: Double,
        widthMm: Double,
        heightMm: Double,
        rotation: ElementRotation = .degree0,
        fontSizeMm: Double = 3.5,
        strokeMm: Double = 0.35
    ) {
        self.id = id
        self.kind = kind
        self.value = value
        self.field = field
        self.xMm = xMm
        self.yMm = yMm
        self.widthMm = widthMm
        self.heightMm = heightMm
        self.rotation = rotation
        self.fontSizeMm = fontSizeMm
        self.strokeMm = strokeMm
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let sourceID = try container.decodeIfPresent(String.self, forKey: .id)
        id = sourceID.flatMap(UUID.init(uuidString:)) ?? UUID()

        let sourceType = try container.decodeIfPresent(String.self, forKey: .type)
            ?? container.decodeIfPresent(String.self, forKey: .kind)
            ?? "text"
        switch sourceType.lowercased() {
        case "barcode", "1d_barcode", "1d": kind = .barcode
        case "qr", "qrcode", "2d_code": kind = .qr
        case "box", "rectangle": kind = .box
        case "line": kind = .line
        default: kind = .text
        }

        let sourceText = try container.decodeIfPresent(String.self, forKey: .text)
            ?? container.decodeIfPresent(String.self, forKey: .value)
            ?? ""
        field = try container.decodeIfPresent(String.self, forKey: .field) ?? ""
        value = sourceText.isEmpty && !field.isEmpty ? "{{\(field)}}" : sourceText
        xMm = try container.decodeIfPresent(Double.self, forKey: .x) ?? container.decodeIfPresent(Double.self, forKey: .xMm) ?? 5
        yMm = try container.decodeIfPresent(Double.self, forKey: .y) ?? container.decodeIfPresent(Double.self, forKey: .yMm) ?? 5
        widthMm = try container.decodeIfPresent(Double.self, forKey: .width) ?? container.decodeIfPresent(Double.self, forKey: .widthMm) ?? 20
        heightMm = try container.decodeIfPresent(Double.self, forKey: .height) ?? container.decodeIfPresent(Double.self, forKey: .heightMm) ?? 5
        let degrees = try container.decodeIfPresent(Int.self, forKey: .rotation) ?? 0
        rotation = ElementRotation(rawValue: degrees) ?? .degree0
        if let mobileSize = try container.decodeIfPresent(Double.self, forKey: .fontSizeMm) {
            fontSizeMm = mobileSize
        } else {
            let pcSize = try container.decodeIfPresent(Double.self, forKey: .fontSize) ?? 10
            fontSizeMm = max(1.5, pcSize * 0.35)
        }
        strokeMm = try container.decodeIfPresent(Double.self, forKey: .strokeWidth)
            ?? container.decodeIfPresent(Double.self, forKey: .strokeMm)
            ?? 0.35
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id.uuidString, forKey: .id)
        try container.encode(kind.rawValue, forKey: .kind)
        try container.encode(pcType, forKey: .type)
        try container.encode(value, forKey: .value)
        try container.encode(value, forKey: .text)
        try container.encode(field, forKey: .field)
        try container.encode(xMm, forKey: .x)
        try container.encode(yMm, forKey: .y)
        try container.encode(widthMm, forKey: .width)
        try container.encode(heightMm, forKey: .height)
        try container.encode(xMm, forKey: .xMm)
        try container.encode(yMm, forKey: .yMm)
        try container.encode(widthMm, forKey: .widthMm)
        try container.encode(heightMm, forKey: .heightMm)
        try container.encode(rotation.rawValue, forKey: .rotation)
        try container.encode(fontSizeMm, forKey: .fontSizeMm)
        try container.encode(max(6, Int((fontSizeMm / 0.35).rounded())), forKey: .fontSize)
        try container.encode(strokeMm, forKey: .strokeMm)
        try container.encode(strokeMm, forKey: .strokeWidth)
    }

    private var pcType: String {
        if kind == .text, !field.isEmpty { return "field" }
        return kind.rawValue
    }

    static func make(_ kind: LabelElementKind, index: Int) -> LabelElement {
        let offset = Double(index % 5) * 2.0
        switch kind {
        case .text:
            return LabelElement(kind: kind, value: "텍스트", xMm: 4, yMm: 4 + offset, widthMm: 34, heightMm: 7)
        case .barcode:
            return LabelElement(kind: kind, value: "1234567890", xMm: 6, yMm: 15 + offset, widthMm: 38, heightMm: 14)
        case .qr:
            return LabelElement(kind: kind, value: "https://chaeumlab.kr", xMm: 6, yMm: 12 + offset, widthMm: 16, heightMm: 16)
        case .box:
            return LabelElement(kind: kind, value: "", xMm: 3, yMm: 3 + offset, widthMm: 42, heightMm: 25)
        case .line:
            return LabelElement(kind: kind, value: "", xMm: 4, yMm: 10 + offset, widthMm: 40, heightMm: 0.5)
        }
    }
}

struct LabelTemplate: Codable, Equatable {
    var schemaVersion = 1
    var name = "새 라벨"
    var widthMm = 50.0
    var heightMm = 40.0
    var elements: [LabelElement] = []

    static let blank = LabelTemplate()

    private enum CodingKeys: String, CodingKey {
        case schemaVersion, name, widthMm, heightMm, label, elements
    }

    private struct PCLabelSize: Codable {
        var widthMm: Double
        var heightMm: Double
        enum CodingKeys: String, CodingKey {
            case widthMm = "width_mm"
            case heightMm = "height_mm"
        }
    }

    init(
        schemaVersion: Int = 1,
        name: String = "새 라벨",
        widthMm: Double = 50,
        heightMm: Double = 40,
        elements: [LabelElement] = []
    ) {
        self.schemaVersion = schemaVersion
        self.name = name
        self.widthMm = widthMm
        self.heightMm = heightMm
        self.elements = elements
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        schemaVersion = try container.decodeIfPresent(Int.self, forKey: .schemaVersion) ?? 1
        name = try container.decodeIfPresent(String.self, forKey: .name) ?? "불러온 라벨"
        let pcLabel = try container.decodeIfPresent(PCLabelSize.self, forKey: .label)
        widthMm = pcLabel?.widthMm ?? container.decodeIfPresent(Double.self, forKey: .widthMm) ?? 50
        heightMm = pcLabel?.heightMm ?? container.decodeIfPresent(Double.self, forKey: .heightMm) ?? 40
        elements = try container.decodeIfPresent([LabelElement].self, forKey: .elements) ?? []
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(schemaVersion, forKey: .schemaVersion)
        try container.encode(name, forKey: .name)
        try container.encode(widthMm, forKey: .widthMm)
        try container.encode(heightMm, forKey: .heightMm)
        try container.encode(PCLabelSize(widthMm: widthMm, heightMm: heightMm), forKey: .label)
        try container.encode(elements, forKey: .elements)
    }

    mutating func normalize() {
        widthMm = min(max(widthMm, 10), 300)
        heightMm = min(max(heightMm, 10), 300)
        for index in elements.indices {
            elements[index].widthMm = min(max(elements[index].widthMm, 0.5), widthMm)
            elements[index].heightMm = min(max(elements[index].heightMm, 0.5), heightMm)
            elements[index].xMm = min(max(elements[index].xMm, 0), max(0, widthMm - elements[index].widthMm))
            elements[index].yMm = min(max(elements[index].yMm, 0), max(0, heightMm - elements[index].heightMm))
            elements[index].fontSizeMm = min(max(elements[index].fontSizeMm, 1.5), 20)
            elements[index].strokeMm = min(max(elements[index].strokeMm, 0.1), 5)
        }
    }
}

struct DatabaseRow: Identifiable, Equatable {
    let id = UUID()
    var values: [String: String]
}

struct RenderedCommand {
    let text: String
    let data: Data
    let fileExtension: String
}

enum PrintJobState: Equatable {
    case idle
    case checking
    case ready
    case sending(current: Int, total: Int)
    case sent(count: Int)
    case failed(message: String)

    var title: String {
        switch self {
        case .idle: return "출력 대기"
        case .checking: return "연결 확인 중"
        case .ready: return "연결 가능"
        case let .sending(current, total): return "전송 중 \(current)/\(total)"
        case .sent: return "명령 전송 완료"
        case let .failed(message): return "실패: \(message)"
        }
    }
}

struct MobileValidationError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}
