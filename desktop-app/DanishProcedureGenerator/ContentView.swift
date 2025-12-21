import SwiftUI

struct ContentView: View {
    @EnvironmentObject var serverManager: ServerManager

    var body: some View {
        ZStack {
            if serverManager.isReady {
                WebView(url: URL(string: "http://localhost:8000")!)
                    .frame(minWidth: 1200, minHeight: 800)
            } else {
                VStack(spacing: 20) {
                    ProgressView()
                        .scaleEffect(1.5)
                        .progressViewStyle(CircularProgressViewStyle(tint: .blue))

                    Text(serverManager.statusMessage)
                        .font(.headline)
                        .foregroundColor(.secondary)

                    if let error = serverManager.errorMessage {
                        VStack(spacing: 8) {
                            Text("Error")
                                .font(.headline)
                                .foregroundColor(.red)
                            Text(error)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)

                            Button("Retry") {
                                serverManager.restartServer()
                            }
                            .buttonStyle(.borderedProminent)
                            .padding(.top, 8)
                        }
                        .padding()
                        .background(Color.red.opacity(0.1))
                        .cornerRadius(8)
                    }
                }
                .frame(minWidth: 400, minHeight: 300)
                .padding(40)
            }
        }
        .background(Color(NSColor.windowBackgroundColor))
    }
}

#Preview {
    ContentView()
        .environmentObject(ServerManager.shared)
}
