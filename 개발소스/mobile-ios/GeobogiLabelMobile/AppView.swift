import SwiftUI
import UniformTypeIdentifiers

enum AppTab: String, CaseIterable, Identifiable {
    case template, data, print, settings
    var id: String { rawValue }
    var title: String {
        switch self {
        case .template: return "템플릿"
        case .data: return "데이터"
        case .print: return "출력"
        case .settings: return "설정"
        }
    }
    var symbol: String {
        switch self {
        case .template: return "square.and.pencil"
        case .data: return "tablecells"
        case .print: return "printer.fill"
        case .settings: return "gearshape.fill"
        }
    }
}

struct AppView: View {
    @State private var selectedTab: AppTab = .template

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack { TemplateEditorView() }
                .tabItem { Label(AppTab.template.title, systemImage: AppTab.template.symbol) }
                .tag(AppTab.template)
            NavigationStack { DatabaseView() }
                .tabItem { Label(AppTab.data.title, systemImage: AppTab.data.symbol) }
                .tag(AppTab.data)
            NavigationStack { PrintView() }
                .tabItem { Label(AppTab.print.title, systemImage: AppTab.print.symbol) }
                .tag(AppTab.print)
            NavigationStack { SettingsView() }
                .tabItem { Label(AppTab.settings.title, systemImage: AppTab.settings.symbol) }
                .tag(AppTab.settings)
        }
        .tint(Brand.green)
    }
}

private struct TemplateEditorView: View {
    @EnvironmentObject private var store: AppStore
    @State private var importing = false
    @State private var exporting = false
    @State private var exportDocument = TransferDocument()

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                BrandHeader(title: "라벨 디자이너", subtitle: "PC와 같은 mm 기준으로 객체를 배치합니다.")
                labelSize
                objectToolbar
                LabelCanvas(store: store)
                if store.selectedElement != nil { selectedInspector }
            }
            .padding()
        }
        .background(Brand.background)
        .navigationTitle("템플릿")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button("JSON 불러오기", systemImage: "folder") { importing = true }
                    Button("JSON 내보내기", systemImage: "square.and.arrow.up") {
                        do {
                            exportDocument = TransferDocument(data: try store.exportTemplateData())
                            exporting = true
                        } catch { store.alertMessage = error.localizedDescription }
                    }
                    Divider()
                    Button("빈 템플릿", systemImage: "doc", role: .destructive) { store.clearTemplate() }
                } label: { Image(systemName: "ellipsis.circle") }
            }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.json]) { result in
            do {
                let url = try result.get()
                guard url.startAccessingSecurityScopedResource() else {
                    throw MobileValidationError(message: "선택한 파일에 접근할 수 없습니다.")
                }
                defer { url.stopAccessingSecurityScopedResource() }
                try store.importTemplate(data: Data(contentsOf: url))
            } catch { store.alertMessage = error.localizedDescription }
        }
        .fileExporter(isPresented: $exporting, document: exportDocument, contentType: .json, defaultFilename: "chaeumlab-label") { result in
            if case let .failure(error) = result { store.alertMessage = error.localizedDescription }
        }
        .appAlert(store: store)
    }

    private var labelSize: some View {
        Surface(title: "라벨 크기", icon: "ruler") {
            HStack {
                NumberField(title: "가로(mm)", value: $store.template.widthMm, range: 10...300)
                NumberField(title: "세로(mm)", value: $store.template.heightMm, range: 10...300)
            }
        }
    }

    private var objectToolbar: some View {
        Surface(title: "객체 추가", icon: "plus.square.on.square") {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 94))], spacing: 8) {
                ForEach(LabelElementKind.allCases) { kind in
                    Button { store.addElement(kind) } label: {
                        Label(kind.title, systemImage: kind.symbol).frame(maxWidth: .infinity)
                    }
                    .buttonStyle(SoftButtonStyle())
                }
            }
        }
    }

    private var selectedInspector: some View {
        Surface(title: "선택 객체 편집", icon: "slider.horizontal.3") {
            if let element = store.selectedElement {
                TextField("내용 또는 {{DB열}}", text: Binding(
                    get: { element.value },
                    set: { value in store.updateSelected { $0.value = value } }
                ))
                .textFieldStyle(.roundedBorder)
                HStack {
                    NumberField(title: "X", value: binding(\.xMm), range: 0...store.template.widthMm)
                    NumberField(title: "Y", value: binding(\.yMm), range: 0...store.template.heightMm)
                }
                HStack {
                    NumberField(title: "너비", value: binding(\.widthMm), range: 0.5...store.template.widthMm)
                    NumberField(title: "높이", value: binding(\.heightMm), range: 0.5...store.template.heightMm)
                }
                Picker("방향", selection: Binding(
                    get: { element.rotation },
                    set: { value in store.updateSelected { $0.rotation = value } }
                )) {
                    ForEach(ElementRotation.allCases) { Text($0.title).tag($0) }
                }
                .pickerStyle(.segmented)
                HStack {
                    Button { store.moveSelected(deltaX: -1, deltaY: 0) } label: { Image(systemName: "arrow.left") }
                    Button { store.moveSelected(deltaX: 0, deltaY: -1) } label: { Image(systemName: "arrow.up") }
                    Button { store.moveSelected(deltaX: 0, deltaY: 1) } label: { Image(systemName: "arrow.down") }
                    Button { store.moveSelected(deltaX: 1, deltaY: 0) } label: { Image(systemName: "arrow.right") }
                    Spacer()
                    Button(role: .destructive) { store.deleteSelected() } label: { Label("삭제", systemImage: "trash") }
                }
                .buttonStyle(.bordered)
            }
        }
    }

    private func binding(_ keyPath: WritableKeyPath<LabelElement, Double>) -> Binding<Double> {
        Binding(
            get: { store.selectedElement?[keyPath: keyPath] ?? 0 },
            set: { value in store.updateSelected { $0[keyPath: keyPath] = value } }
        )
    }
}

private struct LabelCanvas: View {
    @ObservedObject var store: AppStore

    var body: some View {
        Surface(title: "미리보기", icon: "rectangle.on.rectangle") {
            GeometryReader { proxy in
                let scale = min(proxy.size.width / store.template.widthMm, 6)
                ZStack(alignment: .topLeading) {
                    Rectangle().fill(.white)
                    ForEach(store.template.elements) { element in
                        ElementPreview(element: element, selected: element.id == store.selectedElementID)
                            .frame(width: element.widthMm * scale, height: element.heightMm * scale)
                            .rotationEffect(.degrees(Double(element.rotation.rawValue)))
                            .position(
                                x: (element.xMm + element.widthMm / 2) * scale,
                                y: (element.yMm + element.heightMm / 2) * scale
                            )
                            .onTapGesture { store.selectedElementID = element.id }
                            .gesture(DragGesture().onEnded { value in
                                store.selectedElementID = element.id
                                store.moveSelected(deltaX: value.translation.width / scale, deltaY: value.translation.height / scale)
                            })
                    }
                }
                .frame(width: store.template.widthMm * scale, height: store.template.heightMm * scale)
                .overlay(Rectangle().stroke(Brand.ink.opacity(0.7), lineWidth: 1))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(height: min(420, max(220, store.template.heightMm * 5.2)))
        }
    }
}

private struct ElementPreview: View {
    let element: LabelElement
    let selected: Bool
    var body: some View {
        Group {
            switch element.kind {
            case .text:
                Text(element.value).font(.system(size: max(9, element.fontSizeMm * 3))).lineLimit(2)
            case .barcode:
                VStack(spacing: 1) { BarcodeBars(); Text(element.value).font(.system(size: 7, design: .monospaced)) }
            case .qr:
                Image(systemName: "qrcode").resizable().scaledToFit()
            case .box:
                Rectangle().stroke(.black, lineWidth: max(1, element.strokeMm * 2))
            case .line:
                Rectangle().fill(.black).frame(maxHeight: max(1, element.strokeMm * 2))
            }
        }
        .clipped()
        .overlay(Rectangle().stroke(selected ? Brand.green : .clear, lineWidth: 2))
    }
}

private struct BarcodeBars: View {
    var body: some View {
        GeometryReader { proxy in
            HStack(spacing: 1) {
                ForEach(0..<24, id: \.self) { index in
                    Rectangle().frame(width: index.isMultiple(of: 3) ? 3 : 1)
                }
            }.frame(width: proxy.size.width, height: proxy.size.height)
        }
    }
}

private struct DatabaseView: View {
    @EnvironmentObject private var store: AppStore
    @State private var importing = false

    var body: some View {
        VStack(spacing: 0) {
            VStack(spacing: 12) {
                BrandHeader(title: "데이터 소스", subtitle: "CSV의 모든 열을 검색하고 출력할 행을 선택합니다.")
                Button { importing = true } label: {
                    Label("CSV 불러오기", systemImage: "tablecells.badge.ellipsis").frame(maxWidth: .infinity)
                }.buttonStyle(.borderedProminent)
                TextField("전체 열 검색", text: $store.searchText)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                HStack {
                    Text("검색 \(store.filteredRows.count)건 · 선택 \(store.selectedRowIDs.count)건")
                        .font(.footnote).foregroundStyle(.secondary)
                    Spacer()
                    Button("전체 선택") { store.selectFilteredRows() }
                    Button("선택 해제") { store.clearRowSelection() }
                }.font(.footnote.weight(.semibold))
            }
            .padding()
            List(store.filteredRows) { row in
                Button { store.toggleRow(row) } label: {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: store.selectedRowIDs.contains(row.id) ? "checkmark.square.fill" : "square")
                            .foregroundStyle(store.selectedRowIDs.contains(row.id) ? Brand.green : .secondary)
                        VStack(alignment: .leading, spacing: 5) {
                            ForEach(store.databaseColumns.prefix(4), id: \.self) { column in
                                HStack(alignment: .top) {
                                    Text(column).font(.caption.weight(.semibold)).foregroundStyle(.secondary).frame(width: 72, alignment: .leading)
                                    Text(row.values[column, default: ""]).font(.subheadline).foregroundStyle(Brand.ink)
                                }
                            }
                        }
                    }
                }
                .buttonStyle(.plain)
            }
            .overlay {
                if store.databaseRows.isEmpty {
                    ContentUnavailableView("데이터 없음", systemImage: "tablecells", description: Text("CSV 파일을 불러오면 이곳에서 검색하고 선택할 수 있습니다."))
                }
            }
        }
        .background(Brand.background)
        .navigationTitle("데이터")
        .fileImporter(isPresented: $importing, allowedContentTypes: [.commaSeparatedText, .plainText]) { result in
            do {
                let url = try result.get()
                guard url.startAccessingSecurityScopedResource() else { throw MobileValidationError(message: "CSV 파일에 접근할 수 없습니다.") }
                defer { url.stopAccessingSecurityScopedResource() }
                try store.importCSV(data: Data(contentsOf: url))
            } catch { store.alertMessage = error.localizedDescription }
        }
        .appAlert(store: store)
    }
}

private struct PrintView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                BrandHeader(title: "무선 출력", subtitle: "선택한 데이터만 같은 매수로 순서대로 전송합니다.")
                Surface(title: "출력 대상", icon: "checklist") {
                    LabeledContent("라벨", value: "\(Int(store.template.widthMm)) × \(Int(store.template.heightMm)) mm")
                    LabeledContent("선택 데이터", value: store.selectedRows.isEmpty ? "템플릿 1건" : "\(store.selectedRows.count)건")
                    Stepper("항목별 \(store.printQuantity)매", value: $store.printQuantity, in: 1...100)
                    HStack {
                        ForEach([1, 3, 5, 10], id: \.self) { value in
                            Button("\(value)매") { store.printQuantity = value }.buttonStyle(.bordered)
                        }
                    }
                }
                Surface(title: "프린터", icon: "wifi") {
                    LabeledContent("장비", value: "\(store.settings.brand.title) · \(store.settings.host):\(store.settings.port)")
                    LabeledContent("상태", value: store.printState.title)
                    if case .sending = store.printState { ProgressView() }
                    Button { Task { await store.testConnection() } } label: {
                        Label("연결 확인", systemImage: "antenna.radiowaves.left.and.right").frame(maxWidth: .infinity)
                    }.buttonStyle(.bordered)
                }
                Button { Task { await store.printSelectedRows() } } label: {
                    Label("선택 항목 인쇄", systemImage: "printer.fill").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(isSending)
                if case .failed = store.printState, store.canRetry {
                    Button { Task { await store.retryLastPrint() } } label: {
                        Label("마지막 작업 다시 시도", systemImage: "arrow.clockwise").frame(maxWidth: .infinity)
                    }.buttonStyle(.bordered)
                }
                Text("명령 전송 완료는 프린터 수신 성공이며 실제 인쇄 완료와는 구분됩니다.")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding()
        }
        .background(Brand.background)
        .navigationTitle("출력")
        .navigationBarTitleDisplayMode(.inline)
        .appAlert(store: store)
    }

    private var isSending: Bool {
        if case .sending = store.printState { return true }
        return false
    }
}

private struct SettingsView: View {
    @EnvironmentObject private var store: AppStore
    var body: some View {
        Form {
            Section {
                BrandHeader(title: "프린터 설정", subtitle: "휴대폰과 프린터를 같은 Wi-Fi에 연결하세요.")
            }
            Section("연결") {
                TextField("프린터 IP", text: $store.settings.host)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                TextField("포트", value: $store.settings.port, format: .number).keyboardType(.numberPad)
            }
            Section("프린터") {
                Picker("제조사", selection: $store.settings.brand) { ForEach(PrinterBrand.allCases) { Text($0.title).tag($0) } }
                Picker("해상도", selection: $store.settings.dpi) { ForEach(PrinterDPI.allCases) { Text($0.title).tag($0) } }
                Picker("인쇄 방식", selection: $store.settings.printMethod) { ForEach(PrintMethod.allCases) { Text($0.title).tag($0) } }
            }
            Section("용지와 인쇄후작업") {
                Picker("용지 유형", selection: $store.settings.mediaType) { ForEach(MediaType.allCases) { Text($0.title).tag($0) } }
                TextField("간격(mm)", value: $store.settings.gapMm, format: .number).keyboardType(.decimalPad)
                Picker("인쇄후작업", selection: $store.settings.mediaHandling) {
                    ForEach(allowedHandling) { Text($0.title).tag($0) }
                }
            }
            Section {
                Button { Task { await store.testConnection() } } label: {
                    Label("연결 확인", systemImage: "wifi").frame(maxWidth: .infinity)
                }
            } footer: {
                Text("빅솔론 필러와 세우테크 커터·필러는 공식 모델별 명령이 확인되지 않아 출력 단계에서 차단됩니다.")
            }
        }
        .navigationTitle("설정")
        .onChange(of: store.settings.brand) { _ in
            if !allowedHandling.contains(store.settings.mediaHandling) {
                store.settings.mediaHandling = .tearOff
            }
        }
        .appAlert(store: store)
    }

    private var allowedHandling: [MediaHandling] {
        switch store.settings.brand {
        case .tsc, .zebra: return MediaHandling.allCases
        case .bixolon: return [.tearOff, .cutter]
        case .sewoo: return [.tearOff]
        }
    }
}

private struct BrandHeader: View {
    let title: String
    let subtitle: String
    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10).fill(Brand.ink)
                Text("C·").font(.title2.bold()).foregroundStyle(.white)
                Circle().fill(Brand.lime).frame(width: 6, height: 6).offset(x: 10, y: 4)
            }.frame(width: 48, height: 48)
            VStack(alignment: .leading, spacing: 3) {
                Text("채움LAB").font(.caption.weight(.semibold)).foregroundStyle(Brand.green)
                Text(title).font(.title2.bold()).foregroundStyle(Brand.ink)
                Text(subtitle).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
        }
    }
}

private struct Surface<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: icon).font(.headline).foregroundStyle(Brand.ink)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Brand.border))
    }
}

private struct NumberField: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            TextField(title, value: $value, format: .number.precision(.fractionLength(0...2)))
                .keyboardType(.decimalPad).textFieldStyle(.roundedBorder)
                .onChange(of: value) { newValue in
                    value = min(max(newValue, range.lowerBound), range.upperBound)
                }
        }
    }
}

private struct SoftButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(Brand.ink)
            .padding(.vertical, 11).padding(.horizontal, 10)
            .background(configuration.isPressed ? Brand.green.opacity(0.16) : Brand.background)
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

private enum Brand {
    static let ink = Color(red: 0.06, green: 0.10, blue: 0.12)
    static let green = Color(red: 0.00, green: 0.42, blue: 0.31)
    static let lime = Color(red: 0.55, green: 0.84, blue: 0.05)
    static let background = Color(red: 0.96, green: 0.97, blue: 0.97)
    static let border = Color.black.opacity(0.08)
}

private extension View {
    func appAlert(store: AppStore) -> some View {
        alert("확인", isPresented: Binding(
            get: { store.alertMessage != nil },
            set: { if !$0 { store.alertMessage = nil } }
        )) {
            Button("닫기") { store.alertMessage = nil }
        } message: {
            Text(store.alertMessage ?? "")
        }
    }
}

#Preview {
    AppView().environmentObject(AppStore())
}
