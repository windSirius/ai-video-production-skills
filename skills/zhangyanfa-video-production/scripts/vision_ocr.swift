import Foundation
import Vision
import ImageIO

func imagePaths(under roots: [String]) -> [String] {
    let fm = FileManager.default
    let extensions = Set(["jpg", "jpeg", "png", "webp"])
    var paths: [String] = []
    for root in roots {
        var isDir: ObjCBool = false
        guard fm.fileExists(atPath: root, isDirectory: &isDir) else { continue }
        if !isDir.boolValue {
            if extensions.contains(URL(fileURLWithPath: root).pathExtension.lowercased()) {
                paths.append(root)
            }
            continue
        }
        guard let enumerator = fm.enumerator(atPath: root) else { continue }
        for case let rel as String in enumerator {
            if extensions.contains(URL(fileURLWithPath: rel).pathExtension.lowercased()) {
                paths.append(URL(fileURLWithPath: root).appendingPathComponent(rel).path)
            }
        }
    }
    return paths.sorted()
}

func recognize(_ path: String) -> String {
    guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { return "" }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    do {
        try handler.perform([request])
    } catch {
        return ""
    }
    let observations = (request.results ?? []).sorted {
        if abs($0.boundingBox.midY - $1.boundingBox.midY) > 0.03 {
            return $0.boundingBox.midY > $1.boundingBox.midY
        }
        return $0.boundingBox.minX < $1.boundingBox.minX
    }
    return observations.compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: " ")
        .replacingOccurrences(of: "\t", with: " ")
        .replacingOccurrences(of: "\n", with: " ")
}

guard CommandLine.arguments.count >= 3 else {
    fputs("usage: vision_ocr OUTPUT.tsv ROOT [ROOT ...]\n", stderr)
    exit(2)
}

let output = CommandLine.arguments[1]
let paths = imagePaths(under: Array(CommandLine.arguments.dropFirst(2)))
var lines = ["path\tocr_text"]
for (index, path) in paths.enumerated() {
    lines.append("\(path)\t\(recognize(path))")
    if (index + 1) % 100 == 0 {
        fputs("processed \(index + 1)/\(paths.count)\n", stderr)
    }
}
try lines.joined(separator: "\n").appending("\n").write(
    to: URL(fileURLWithPath: output), atomically: true, encoding: .utf8
)
print("wrote \(paths.count) rows to \(output)")
