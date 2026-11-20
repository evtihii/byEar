// Малює іконку Голосія (коралова «хвиля-усмішка»: очі й звукова хвиля, що усміхається) у PNG 1024×1024:
// swift make_icon.swift out.png. Та сама фігура, що й у static/js/core.js (I.logo), у полі 120×120.
import Cocoa

let size: CGFloat = 1024
let inset: CGFloat = 100
let s = (size - 2 * inset) / 120                     // одиниця поля 120×120 → пікселі
func r(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> NSRect {   // y згори вниз, як у SVG
    NSRect(x: inset + x * s, y: size - inset - (y + h) * s, width: w * s, height: h * s)
}
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
let body = NSBezierPath(roundedRect: r(0, 0, 120, 120), xRadius: 28 * s, yRadius: 28 * s)
NSGraphicsContext.current?.saveGraphicsState()
let shadow = NSShadow(); shadow.shadowBlurRadius = 28; shadow.shadowOffset = NSSize(width: 0, height: -12)
shadow.shadowColor = NSColor.black.withAlphaComponent(0.25); shadow.set()
NSColor(red: 1, green: 0.31, blue: 0.43, alpha: 1).setFill(); body.fill()
NSGraphicsContext.current?.restoreGraphicsState()
NSGradient(starting: NSColor(red: 1, green: 0.42, blue: 0.53, alpha: 1),
           ending: NSColor(red: 0.98, green: 0.27, blue: 0.40, alpha: 1))!.draw(in: body, angle: -90)
NSColor.white.setFill()
for cx in [38.0, 82.0] as [CGFloat] { NSBezierPath(ovalIn: r(cx - 6.5, 24.5, 13, 13)).fill() }
let bars: [(CGFloat, CGFloat)] = [(55, 14), (59, 22), (62, 28), (63, 32), (62, 28), (59, 22), (55, 14)]
for (i, b) in bars.enumerated() {
    let x = 20.5 + CGFloat(i) * 12
    NSBezierPath(roundedRect: r(x, b.0, 7, b.1), xRadius: 3.5 * s, yRadius: 3.5 * s).fill()
}
img.unlockFocus()
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
