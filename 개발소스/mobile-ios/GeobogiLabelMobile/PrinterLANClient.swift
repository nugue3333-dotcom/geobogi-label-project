import Foundation
import Network

final class PrinterLANClient {
    private let timeoutSeconds: TimeInterval

    init(timeoutSeconds: TimeInterval = 5) {
        self.timeoutSeconds = timeoutSeconds
    }

    func check(host: String, port: UInt16) async throws {
        try await perform(host: host, port: port, payload: nil)
    }

    func send(_ data: Data, host: String, port: UInt16) async throws {
        try await perform(host: host, port: port, payload: data)
    }

    private func perform(host: String, port: UInt16, payload: Data?) async throws {
        guard let nwPort = NWEndpoint.Port(rawValue: port) else {
            throw MobileValidationError(message: "프린터 포트가 올바르지 않습니다.")
        }
        try await withCheckedThrowingContinuation { continuation in
            let connection = NWConnection(host: NWEndpoint.Host(host), port: nwPort, using: .tcp)
            let queue = DispatchQueue(label: "kr.chaeumlab.label-printer", qos: .userInitiated)
            let lock = NSLock()
            var finished = false

            func finish(_ result: Result<Void, Error>) {
                lock.lock()
                guard !finished else { lock.unlock(); return }
                finished = true
                lock.unlock()
                connection.cancel()
                continuation.resume(with: result)
            }

            connection.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    guard let payload else { finish(.success(())); return }
                    connection.send(content: payload, completion: .contentProcessed { error in
                        if let error { finish(.failure(error)) } else { finish(.success(())) }
                    })
                case let .failed(error), let .waiting(error):
                    finish(.failure(error))
                case .cancelled:
                    finish(.failure(MobileValidationError(message: "프린터 연결이 취소되었습니다.")))
                default:
                    break
                }
            }
            connection.start(queue: queue)
            queue.asyncAfter(deadline: .now() + timeoutSeconds) {
                finish(.failure(MobileValidationError(message: "프린터 연결 시간이 초과되었습니다. IP와 Wi-Fi를 확인하세요.")))
            }
        }
    }
}
