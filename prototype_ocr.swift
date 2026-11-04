// THROWAWAY macOS-only OCR. Originals are never modified; output is unverified.
import Foundation
import PDFKit
import AppKit
import Vision

let args = CommandLine.arguments
if args.count < 3 { exit(2) }
guard let pdf = PDFDocument(url: URL(fileURLWithPath: args[1])) else { exit(3) }
var output: [String: String] = [:]
for value in args.dropFirst(2) {
    guard let number = Int(value), let page = pdf.page(at: number - 1) else { exit(4) }
    let image = page.thumbnail(of: NSSize(width: 1800, height: 2500), for: .mediaBox)
    guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(5) }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["es-ES", "en-US"]
    request.usesLanguageCorrection = true
    do {
        try VNImageRequestHandler(cgImage: cgImage).perform([request])
        let observations = request.results ?? []
        output[String(number)] = observations.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
    } catch { exit(6) }
}
guard let data = try? JSONSerialization.data(withJSONObject: output, options: [.sortedKeys]),
      let json = String(data: data, encoding: .utf8) else { exit(7) }
print(json)
