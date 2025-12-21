import SwiftUI
import WebKit

struct WebView: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator

        // Enable back/forward gestures
        webView.allowsBackForwardNavigationGestures = true

        // Custom user agent
        webView.customUserAgent = "DanishProcedureGenerator/2.0 (macOS; SwiftUI)"

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        let request = URLRequest(url: url)
        webView.load(request)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    class Coordinator: NSObject, WKNavigationDelegate {
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("WebView navigation failed: \(error.localizedDescription)")
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            print("WebView provisional navigation failed: \(error.localizedDescription)")
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            // Open external links in default browser
            if let url = navigationAction.request.url,
               navigationAction.navigationType == .linkActivated,
               url.host != "localhost" {
                NSWorkspace.shared.open(url)
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }
    }
}

#Preview {
    WebView(url: URL(string: "http://localhost:8000")!)
        .frame(width: 800, height: 600)
}
