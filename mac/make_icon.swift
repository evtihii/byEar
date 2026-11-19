// Малює іконку наСлуху (рожевий квадрат із навушниками) у PNG 1024×1024: swift make_icon.swift out.png
import Cocoa

let size: CGFloat = 1024
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
let inset: CGFloat = 100
let rect = NSRect(x: inset, y: inset, width: size - 2 * inset, height: size - 2 * inset)
let path = NSBezierPath(roundedRect: rect, xRadius: 185, yRadius: 185)
NSGraphicsContext.current?.saveGraphicsState()
let shadow = NSShadow(); shadow.shadowBlurRadius = 28; shadow.shadowOffset = NSSize(width: 0, height: -12)
shadow.shadowColor = NSColor.black.withAlphaComponent(0.28); shadow.set()
NSColor(red: 1, green: 0.18, blue: 0.33, alpha: 1).setFill(); path.fill()
NSGraphicsContext.current?.restoreGraphicsState()
NSGradient(starting: NSColor(red: 1, green: 0.40, blue: 0.52, alpha: 1),
           ending: NSColor(red: 1, green: 0.16, blue: 0.31, alpha: 1))!.draw(in: path, angle: -90)
let cfg = NSImage.SymbolConfiguration(pointSize: 440, weight: .medium)
if let sym = NSImage(systemSymbolName: "headphones", accessibilityDescription: nil)?.withSymbolConfiguration(cfg) {
    let tinted = NSImage(size: sym.size)
    tinted.lockFocus()
    sym.draw(at: .zero, from: .zero, operation: .sourceOver, fraction: 1)
    NSColor.white.set(); NSRect(origin: .zero, size: sym.size).fill(using: .sourceAtop)
    tinted.unlockFocus()
    tinted.draw(in: NSRect(x: (size - sym.size.width) / 2, y: (size - sym.size.height) / 2,
                           width: sym.size.width, height: sym.size.height))
}
img.unlockFocus()
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
