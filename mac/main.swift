// наСлух (ByEar) — оболонка для macOS.
// Запускає server.py (якщо він ще не працює), показує сторінку у власному вікні (WKWebView)
// і при виході (⌘Q) зупиняє сервер разом з агентом. Якщо сервер запустили окремо — не чіпає його.
import Cocoa
import WebKit


func serverDir() -> String {
    // Тека з server.py: ключ ByEarServerDir в Info.plist, інакше — тека, де лежить ByEar.app
    if let d = Bundle.main.object(forInfoDictionaryKey: "ByEarServerDir") as? String,
       FileManager.default.fileExists(atPath: d + "/server.py") { return d }
    return Bundle.main.bundleURL.deletingLastPathComponent().path
}

// Порт: змінна PORT → "port" у settings.json поруч із server.py → 8765 (так само, як у server.py)
func serverPort() -> Int {
    if let e = ProcessInfo.processInfo.environment["PORT"], let p = Int(e) { return p }
    let f = URL(fileURLWithPath: serverDir() + "/settings.json")
    if let d = try? Data(contentsOf: f),
       let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
       let p = j["port"] as? Int { return p }
    return 8765
}
let port = serverPort()
let baseURL = URL(string: "http://localhost:\(port)/")!

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?
    var log: FileHandle?

    func applicationDidFinishLaunching(_ n: Notification) {
        buildMenu()
        let cfg = WKWebViewConfiguration()
        cfg.mediaTypesRequiringUserActionForPlayback = []
        cfg.websiteDataStore = .default()                 // localStorage між запусками
        web = WKWebView(frame: .zero, configuration: cfg)
        web.uiDelegate = self
        web.navigationDelegate = self
        web.setValue(false, forKey: "drawsBackground")    // без білого спалаху в темній темі

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1320, height: 840),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "наСлух"
        window.minSize = NSSize(width: 900, height: 560)
        window.contentView = web
        window.center()
        window.setFrameAutosaveName("ByEarMain")
        window.makeKeyAndOrderFront(nil)
        showMessage("Запускаю наСлух…")
        start()
    }

    // ---------- сервер ----------
    func ping(_ done: @escaping (Bool) -> Void) {
        var r = URLRequest(url: baseURL.appendingPathComponent("api/state"))
        r.timeoutInterval = 0.8
        URLSession.shared.dataTask(with: r) { _, resp, _ in
            done((resp as? HTTPURLResponse)?.statusCode == 200)
        }.resume()
    }

    func start() {
        ping { up in
            DispatchQueue.main.async {
                if up { self.load() } else { self.launchServer() }
            }
        }
    }

    func launchServer() {
        let dir = serverDir()
        guard FileManager.default.fileExists(atPath: dir + "/server.py") else {
            showMessage("Не знайдено server.py у теці:<br>\(dir)"); return
        }
        let p = Process()
        // Логін-оболонка дає звичний PATH (Homebrew: python3, ffmpeg, claude)
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-lc", "exec python3 server.py --no-open"]
        p.currentDirectoryURL = URL(fileURLWithPath: dir)
        let logs = dir + "/logs"
        try? FileManager.default.createDirectory(atPath: logs, withIntermediateDirectories: true)
        let lp = logs + "/app_server.log"
        FileManager.default.createFile(atPath: lp, contents: nil)
        log = FileHandle(forWritingAtPath: lp)
        p.standardOutput = log
        p.standardError = log
        p.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                guard let self = self, self.server === proc else { return }
                self.server = nil
                self.showMessage("Сервер наСлуху зупинився (код \(proc.terminationStatus)).<br>Журнал: logs/app_server.log<br><br><a href='byear:restart'>Запустити знову</a>")
            }
        }
        do { try p.run() } catch { showMessage("Не вдалося запустити python3: \(error.localizedDescription)"); return }
        server = p
        waitUntilUp(tries: 60)
    }

    func waitUntilUp(tries: Int) {
        ping { up in
            DispatchQueue.main.async {
                if up { self.load() }
                else if tries > 0 && self.server != nil {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { self.waitUntilUp(tries: tries - 1) }
                } else if self.server != nil { self.showMessage("Сервер не відповідає. Журнал: logs/app_server.log") }
            }
        }
    }

    func load() { web.load(URLRequest(url: baseURL)) }

    func showMessage(_ html: String) {
        let page = """
        <html><body style="margin:0;height:100vh;display:grid;place-items:center;font:14px -apple-system;
        color:#888;background:transparent;text-align:center"><div>\(html)</div></body></html>
        """
        web.loadHTMLString(page, baseURL: nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ n: Notification) {
        guard let p = server, p.isRunning else { return }
        server = nil
        p.terminate()                                   // SIGTERM → server.py зупиняє агента й виходить
        let deadline = Date().addingTimeInterval(6)
        while p.isRunning && Date() < deadline { usleep(50_000) }
        if p.isRunning { kill(p.processIdentifier, SIGKILL) }
    }

    // ---------- мікрофон для диктування (запис у сторінці → Whisper на сервері) ----------
    @available(macOS 12.0, *)
    func webView(_ w: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame f: WKFrameInfo, type: WKMediaCaptureType,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        let local = origin.host == "localhost" || origin.host == "127.0.0.1"
        decisionHandler(local && type == .microphone ? .grant : .deny)
    }

    // ---------- WebKit: діалоги, посилання ----------
    func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage m: String,
                 initiatedByFrame f: WKFrameInfo, completionHandler done: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "OK")
        a.beginSheetModal(for: window) { _ in done() }
    }

    func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage m: String,
                 initiatedByFrame f: WKFrameInfo, completionHandler done: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = m
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Скасувати")
        a.beginSheetModal(for: window) { r in done(r == .alertFirstButtonReturn) }
    }

    func webView(_ w: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
                 initiatedByFrame f: WKFrameInfo, completionHandler done: @escaping (String?) -> Void) {
        let a = NSAlert(); a.messageText = prompt
        let t = NSTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24)); t.stringValue = defaultText ?? ""
        a.accessoryView = t
        a.addButton(withTitle: "OK"); a.addButton(withTitle: "Скасувати")
        a.beginSheetModal(for: window) { r in done(r == .alertFirstButtonReturn ? t.stringValue : nil) }
    }

    // target=_blank і зовнішні посилання — у звичайному браузері
    func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration,
                 for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
        if let u = a.request.url { NSWorkspace.shared.open(u) }
        return nil
    }

    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction,
                 decisionHandler done: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let u = a.request.url else { return done(.allow) }
        if u.scheme == "byear" { done(.cancel); showMessage("Запускаю наСлух…"); start(); return }
        if u.host == "localhost" || u.host == "127.0.0.1" || u.scheme == "about" || u.scheme == "data" { return done(.allow) }
        NSWorkspace.shared.open(u)
        done(.cancel)
    }

    // ---------- меню ----------
    @objc func reloadPage(_ s: Any?) { if server == nil { start() } else { web.reload() } }

    func buildMenu() {
        let main = NSMenu()
        func sub(_ title: String, _ items: [NSMenuItem]) {
            let m = NSMenu(title: title); items.forEach { m.addItem($0) }
            let it = NSMenuItem(); it.submenu = m; main.addItem(it)
        }
        func item(_ t: String, _ a: Selector?, _ k: String, _ mods: NSEvent.ModifierFlags = .command) -> NSMenuItem {
            let i = NSMenuItem(title: t, action: a, keyEquivalent: k); i.keyEquivalentModifierMask = mods; return i
        }
        sub("наСлух", [
            item("Про наСлух", #selector(NSApplication.orderFrontStandardAboutPanel(_:)), ""),
            .separator(),
            item("Сховати наСлух", #selector(NSApplication.hide(_:)), "h"),
            item("Сховати інші", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            .separator(),
            item("Вийти з наСлуху", #selector(NSApplication.terminate(_:)), "q"),
        ])
        // ⌘Z / ⌘F спершу отримує сторінка (там свої скасування й пошук); меню — запасний шлях
        sub("Редагування", [
            item("Скасувати", Selector(("undo:")), "z"),
            item("Повторити", Selector(("redo:")), "z", [.command, .shift]),
            .separator(),
            item("Вирізати", #selector(NSText.cut(_:)), "x"),
            item("Копіювати", #selector(NSText.copy(_:)), "c"),
            item("Вставити", #selector(NSText.paste(_:)), "v"),
            item("Виділити все", #selector(NSText.selectAll(_:)), "a"),
        ])
        sub("Вигляд", [
            item("Оновити сторінку", #selector(reloadPage(_:)), "r"),
            item("На весь екран", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ])
        sub("Вікно", [
            item("Згорнути", #selector(NSWindow.performMiniaturize(_:)), "m"),
            item("Масштаб", #selector(NSWindow.performZoom(_:)), ""),
        ])
        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.activate(ignoringOtherApps: true)
app.run()
