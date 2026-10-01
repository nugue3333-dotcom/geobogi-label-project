import Foundation

@MainActor
final class AppStore: ObservableObject {
    @Published var template: LabelTemplate = .blank
    @Published var selectedElementID: UUID?
    @Published var databaseColumns: [String] = []
    @Published var databaseRows: [DatabaseRow] = []
    @Published var selectedRowIDs: Set<UUID> = []
    @Published var searchText = ""
    @Published var settings = PrinterSettings()
    @Published var printQuantity = 1
    @Published var printState: PrintJobState = .idle
    @Published var alertMessage: String?

    private let lanClient: PrinterLANClient
    private var retryRows: [[String: String]] = []

    init(lanClient: PrinterLANClient = PrinterLANClient()) {
        self.lanClient = lanClient
    }

    var selectedElement: LabelElement? {
        template.elements.first { $0.id == selectedElementID }
    }

    var filteredRows: [DatabaseRow] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !query.isEmpty else { return databaseRows }
        return databaseRows.filter { row in
            row.values.values.contains { $0.lowercased().contains(query) }
        }
    }

    var selectedRows: [DatabaseRow] {
        databaseRows.filter { selectedRowIDs.contains($0.id) }
    }

    var canRetry: Bool { !retryRows.isEmpty }

    func addElement(_ kind: LabelElementKind) {
        let element = LabelElement.make(kind, index: template.elements.count)
        template.elements.append(element)
        template.normalize()
        selectedElementID = element.id
    }

    func updateSelected(_ mutate: (inout LabelElement) -> Void) {
        guard let id = selectedElementID,
              let index = template.elements.firstIndex(where: { $0.id == id }) else { return }
        mutate(&template.elements[index])
        template.normalize()
    }

    func moveSelected(deltaX: Double, deltaY: Double) {
        updateSelected {
            $0.xMm += deltaX
            $0.yMm += deltaY
        }
    }

    func deleteSelected() {
        guard let id = selectedElementID else { return }
        template.elements.removeAll { $0.id == id }
        selectedElementID = nil
    }

    func clearTemplate() {
        template = .blank
        selectedElementID = nil
    }

    func importTemplate(data: Data) throws {
        var decoded = try JSONDecoder().decode(LabelTemplate.self, from: data)
        decoded.normalize()
        template = decoded
        selectedElementID = nil
    }

    func exportTemplateData() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(template)
    }

    func importCSV(data: Data) throws {
        let table = try CSVDatabaseService.parse(data: data)
        databaseColumns = table.columns
        databaseRows = table.rows
        selectedRowIDs.removeAll()
        searchText = ""
    }

    func toggleRow(_ row: DatabaseRow) {
        if selectedRowIDs.contains(row.id) {
            selectedRowIDs.remove(row.id)
        } else {
            selectedRowIDs.insert(row.id)
        }
    }

    func selectFilteredRows() {
        selectedRowIDs.formUnion(filteredRows.map(\.id))
    }

    func clearRowSelection() {
        selectedRowIDs.removeAll()
    }

    func testConnection() async {
        do {
            printState = .checking
            try validateSettings()
            try await lanClient.check(host: settings.host, port: UInt16(settings.port))
            printState = .ready
        } catch {
            printState = .failed(message: error.localizedDescription)
        }
    }

    func printSelectedRows() async {
        guard !isSending else { return }
        let rows = selectedRows.map(\.values)
        retryRows = rows.isEmpty ? [[:]] : rows
        await send(rows: retryRows)
    }

    func retryLastPrint() async {
        guard !isSending else { return }
        guard !retryRows.isEmpty else { return }
        await send(rows: retryRows)
    }

    private var isSending: Bool {
        if case .sending = printState { return true }
        return false
    }

    private func send(rows: [[String: String]]) async {
        do {
            try validateSettings()
            let quantity = min(max(printQuantity, 1), 100)
            for (index, row) in rows.enumerated() {
                retryRows = Array(rows[index...])
                printState = .sending(current: index + 1, total: rows.count)
                let rendered = try LabelCommandRenderer.render(
                    settings: settings,
                    template: template,
                    dataRow: row,
                    quantity: quantity
                )
                try await lanClient.send(rendered.data, host: settings.host, port: UInt16(settings.port))
            }
            retryRows.removeAll()
            printState = .sent(count: rows.count)
        } catch {
            // Failed jobs remain retryable; no connection or sending lock survives this point.
            printState = .failed(message: error.localizedDescription)
            alertMessage = error.localizedDescription
        }
    }

    private func validateSettings() throws {
        guard !settings.host.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw MobileValidationError(message: "프린터 IP를 입력하세요.")
        }
        guard (1...65535).contains(settings.port) else {
            throw MobileValidationError(message: "포트는 1부터 65535 사이여야 합니다.")
        }
        guard (10...300).contains(template.widthMm), (10...300).contains(template.heightMm) else {
            throw MobileValidationError(message: "라벨 크기는 10~300mm 범위로 설정하세요.")
        }
        guard !template.elements.isEmpty else {
            throw MobileValidationError(message: "출력할 객체가 없습니다. 템플릿에 객체를 추가하세요.")
        }
    }
}
