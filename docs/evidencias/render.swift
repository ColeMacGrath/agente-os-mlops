import AppKit
import WebKit
// Uso: swift render.swift entrada.html salida.png ancho alto [salida.pdf]
let args = CommandLine.arguments
let url = URL(fileURLWithPath: args[1])
let out = URL(fileURLWithPath: args[2])
let w = CGFloat(Double(args[3])!), h = CGFloat(Double(args[4])!)
let pdfOut: URL? = args.count > 5 ? URL(fileURLWithPath: args[5]) : nil
let app = NSApplication.shared
class D: NSObject, WKNavigationDelegate {
  func webView(_ wv: WKWebView, didFinish n: WKNavigation!) {
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
      let cfg = WKSnapshotConfiguration(); cfg.rect = CGRect(x: 0, y: 0, width: w, height: h); cfg.snapshotWidth = NSNumber(value: Double(w) * 2)
      wv.takeSnapshot(with: cfg) { img, err in
        guard let img = img, let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else { print("error", err as Any); exit(1) }
        try! png.write(to: out)
        if let p = pdfOut {
          let pc = WKPDFConfiguration(); pc.rect = CGRect(x: 0, y: 0, width: w, height: h)
          wv.createPDF(configuration: pc) { r in if case .success(let d) = r { try! d.write(to: p) }; exit(0) }
        } else { exit(0) }
      }
    }
  }
}
let d = D()
let wv = WKWebView(frame: CGRect(x: 0, y: 0, width: w, height: h))
wv.navigationDelegate = d
wv.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
app.run()
