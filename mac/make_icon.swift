// Малює іконку Голосія (біла плитка, чорні очі-дужки й усміхнений рот з білою звуковою хвилею) у PNG 1024×1024:
// swift make_icon.swift out.png. Та сама фігура, що й у static/js/core.js (I.logo), у полі 120×120.
import Cocoa

let size: CGFloat = 1024
let inset: CGFloat = 100
let s = (size - 2 * inset) / 120                     // одиниця поля 120×120 → пікселі
func p(_ x: CGFloat, _ y: CGFloat) -> NSPoint { NSPoint(x: inset + x * s, y: size - inset - y * s) }   // y згори вниз, як у SVG
func r(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> NSRect {
    NSRect(x: inset + x * s, y: size - inset - (y + h) * s, width: w * s, height: h * s)
}
extension NSBezierPath {                             // квадратична крива SVG (Q) через кубічну
    func quad(to e: NSPoint, control c: NSPoint) {
        let a = currentPoint
        curve(to: e, controlPoint1: NSPoint(x: a.x + 2 / 3 * (c.x - a.x), y: a.y + 2 / 3 * (c.y - a.y)),
              controlPoint2: NSPoint(x: e.x + 2 / 3 * (c.x - e.x), y: e.y + 2 / 3 * (c.y - e.y)))
    }
}
let ink = NSColor(white: 0.07, alpha: 1)
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
let body = NSBezierPath(roundedRect: r(0, 0, 120, 120), xRadius: 28 * s, yRadius: 28 * s)
NSGraphicsContext.current?.saveGraphicsState()
let shadow = NSShadow(); shadow.shadowBlurRadius = 28; shadow.shadowOffset = NSSize(width: 0, height: -12)
shadow.shadowColor = NSColor.black.withAlphaComponent(0.25); shadow.set()
NSColor.white.setFill(); body.fill()
NSGraphicsContext.current?.restoreGraphicsState()
NSGradient(starting: .white, ending: NSColor(white: 0.93, alpha: 1))!.draw(in: body, angle: -90)
// очі «^ ^»
ink.setStroke()
for x0 in [29.0, 75.0] as [CGFloat] {
    let e = NSBezierPath(); e.lineWidth = 6 * s; e.lineCapStyle = .round
    e.move(to: p(x0, 40)); e.quad(to: p(x0 + 16, 40), control: p(x0 + 8, 28)); e.stroke()
}
// рот
let m = NSBezierPath()
m.move(to: p(30, 58)); m.line(to: p(90, 58))
m.quad(to: p(60, 94), control: p(90, 94)); m.quad(to: p(30, 58), control: p(30, 94)); m.close()
ink.setFill(); m.fill()
// звукова хвиля в роті
NSColor.white.setFill()
let bars: [(CGFloat, CGFloat, CGFloat)] = [(41, 66, 10), (50, 62, 20), (59, 64, 16), (68, 62, 20), (77, 66, 10)]
for b in bars { NSBezierPath(roundedRect: r(b.0, b.1, 5, b.2), xRadius: 2.5 * s, yRadius: 2.5 * s).fill() }
img.unlockFocus()
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
