import SwiftUI

@main
struct DanishProcedureGeneratorApp: App {
    @StateObject private var serverManager = ServerManager.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(serverManager)
                .onAppear {
                    serverManager.startServer()
                }
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        .commands {
            CommandGroup(replacing: .appInfo) {
                Button("About Danish Procedure Generator") {
                    NSApplication.shared.orderFrontStandardAboutPanel(
                        options: [
                            .applicationName: "Danish Procedure Generator",
                            .applicationVersion: "2.0",
                            .credits: NSAttributedString(string: "Evidence-based procedure generation for Danish emergency medicine."),
                        ]
                    )
                }
            }
            CommandGroup(after: .appSettings) {
                Button("Open in Browser") {
                    if let url = URL(string: "http://localhost:8000") {
                        NSWorkspace.shared.open(url)
                    }
                }
                .keyboardShortcut("o", modifiers: [.command, .shift])

                Divider()

                Button("Restart Server") {
                    serverManager.restartServer()
                }
                .keyboardShortcut("r", modifiers: [.command, .shift])
            }
        }
    }
}
