import Foundation
import Combine

@MainActor
class ServerManager: ObservableObject {
    static let shared = ServerManager()

    @Published var isReady = false
    @Published var statusMessage = "Starting server..."
    @Published var errorMessage: String?

    private var serverProcess: Process?
    private var healthCheckTimer: Timer?
    private let serverPort = 8000
    private let maxRetries = 30
    private var retryCount = 0

    private init() {}

    func startServer() {
        isReady = false
        errorMessage = nil
        statusMessage = "Locating project..."

        // Find the project root (relative to the app bundle or dev location)
        guard let projectRoot = findProjectRoot() else {
            errorMessage = "Could not find project root. Make sure the app is in the project directory."
            return
        }

        statusMessage = "Starting backend server..."

        // Check if server is already running
        if checkServerHealth() {
            isReady = true
            statusMessage = "Connected to existing server"
            return
        }

        // Start the server process
        startServerProcess(projectRoot: projectRoot)
    }

    func restartServer() {
        stopServer()
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in
            self?.startServer()
        }
    }

    func stopServer() {
        healthCheckTimer?.invalidate()
        healthCheckTimer = nil

        if let process = serverProcess, process.isRunning {
            process.terminate()
            serverProcess = nil
        }

        isReady = false
        retryCount = 0
    }

    private func findProjectRoot() -> URL? {
        // Check common locations
        var possibleRoots: [URL] = [
            // Development: app is in desktop-app/ subdirectory
            Bundle.main.bundleURL.deletingLastPathComponent().deletingLastPathComponent(),
            // Installed: check user's home directory
            FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("danish-procedure-generator-unified"),
        ]

        // Check Documents (optional)
        if let docsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            possibleRoots.append(docsDir.appendingPathComponent("danish-procedure-generator-unified"))
        }

        for root in possibleRoots {
            let scriptsDir = root.appendingPathComponent("scripts")
            let backendDir = root.appendingPathComponent("backend")
            if FileManager.default.fileExists(atPath: scriptsDir.path) &&
               FileManager.default.fileExists(atPath: backendDir.path) {
                return root
            }
        }

        return nil
    }

    private func startServerProcess(projectRoot: URL) {
        let process = Process()
        process.currentDirectoryURL = projectRoot
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = ["-c", "./scripts/start"]

        // Set up environment
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:" + (env["PATH"] ?? "")
        process.environment = env

        // Capture output for debugging
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        do {
            try process.run()
            serverProcess = process
            statusMessage = "Server starting..."

            // Start health check polling
            startHealthCheck()
        } catch {
            errorMessage = "Failed to start server: \(error.localizedDescription)"
        }
    }

    private func startHealthCheck() {
        retryCount = 0
        healthCheckTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.performHealthCheck()
            }
        }
    }

    private func performHealthCheck() {
        retryCount += 1
        statusMessage = "Waiting for server... (\(retryCount)/\(maxRetries))"

        if checkServerHealth() {
            healthCheckTimer?.invalidate()
            isReady = true
            statusMessage = "Server ready"
            return
        }

        if retryCount >= maxRetries {
            healthCheckTimer?.invalidate()
            errorMessage = "Server failed to start after \(maxRetries) seconds"
        }
    }

    private func checkServerHealth() -> Bool {
        guard let url = URL(string: "http://localhost:\(serverPort)/api/status") else {
            return false
        }

        var request = URLRequest(url: url)
        request.timeoutInterval = 1.0

        let semaphore = DispatchSemaphore(value: 0)
        var success = false

        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200 {
                success = true
            }
            semaphore.signal()
        }
        task.resume()
        _ = semaphore.wait(timeout: .now() + 2)

        return success
    }

    deinit {
        // Note: This won't work well with @MainActor, but leaving for reference
    }
}
