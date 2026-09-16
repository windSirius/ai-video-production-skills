import Foundation
import Vision
import ImageIO

struct OCRRegion: Codable {
    let text: String
    let confidence: Float
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

struct LabelResult: Codable {
    let identifier: String
    let confidence: Float
}

struct FrameInput {
    let frameID: String
    let sourceID: String
    let timestamp: Double
    let samplingPass: String
    let path: String
}

func tsvSafe(_ value: String) -> String {
    return value
        .replacingOccurrences(of: "\t", with: " ")
        .replacingOccurrences(of: "\r", with: " ")
        .replacingOccurrences(of: "\n", with: " ")
}

func jsonString<T: Encodable>(_ value: T) -> String {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
    guard let data = try? encoder.encode(value),
          let string = String(data: data, encoding: .utf8) else { return "[]" }
    return string
}

func readFrameInput(_ path: String) throws -> [FrameInput] {
    let text = try String(contentsOfFile: path, encoding: .utf8)
    let lines = text.split(whereSeparator: \.isNewline).map(String.init)
    guard let headerLine = lines.first else { return [] }
    let header = headerLine.split(separator: "\t", omittingEmptySubsequences: false).map(String.init)
    let required = ["frame_id", "source_id", "timestamp_s", "sampling_pass", "path"]
    let positions = Dictionary(uniqueKeysWithValues: header.enumerated().map { ($0.element, $0.offset) })
    for name in required where positions[name] == nil {
        throw NSError(domain: "VisionMissionAnalyzer", code: 2,
                      userInfo: [NSLocalizedDescriptionKey: "missing input column: \(name)"])
    }

    return try lines.dropFirst().filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }.map { line in
        let fields = line.split(separator: "\t", omittingEmptySubsequences: false).map(String.init)
        func field(_ name: String) -> String {
            let index = positions[name]!
            return index < fields.count ? fields[index] : ""
        }
        guard let timestamp = Double(field("timestamp_s")) else {
            throw NSError(domain: "VisionMissionAnalyzer", code: 3,
                          userInfo: [NSLocalizedDescriptionKey: "invalid timestamp in row: \(line)"])
        }
        return FrameInput(frameID: field("frame_id"), sourceID: field("source_id"),
                          timestamp: timestamp, samplingPass: field("sampling_pass"),
                          path: field("path"))
    }.sorted {
        if $0.sourceID != $1.sourceID { return $0.sourceID < $1.sourceID }
        if $0.timestamp != $1.timestamp { return $0.timestamp < $1.timestamp }
        return $0.frameID < $1.frameID
    }
}

guard CommandLine.arguments.count == 3 else {
    fputs("usage: vision_mission_analyzer INPUT.tsv OUTPUT.tsv\n", stderr)
    exit(2)
}

let inputPath = CommandLine.arguments[1]
let outputPath = CommandLine.arguments[2]
let frames: [FrameInput]
do {
    frames = try readFrameInput(inputPath)
} catch {
    fputs("input error: \(error.localizedDescription)\n", stderr)
    exit(2)
}

var output = [
    "frame_id\tsource_id\ttimestamp_s\tsampling_pass\tpath\twidth\theight\tocr_text\tocr_regions_json\tface_count\tsaliency_object_count\ttop_labels_json\tfeature_distance_from_previous\tanalysis_error"
]
var previousFeatureBySource: [String: VNFeaturePrintObservation] = [:]

for (index, frame) in frames.enumerated() {
    var width = 0
    var height = 0
    var ocrText = ""
    var ocrRegions: [OCRRegion] = []
    var faceCount = 0
    var saliencyObjectCount = 0
    var labels: [LabelResult] = []
    var featureDistance = ""
    var analysisError = ""

    if let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: frame.path) as CFURL, nil),
       let image = CGImageSourceCreateImageAtIndex(source, 0, nil) {
        width = image.width
        height = image.height

        let textRequest = VNRecognizeTextRequest()
        textRequest.recognitionLevel = .accurate
        textRequest.usesLanguageCorrection = true
        textRequest.recognitionLanguages = ["zh-Hans", "en-US"]

        let faceRequest = VNDetectFaceRectanglesRequest()
        let saliencyRequest = VNGenerateAttentionBasedSaliencyImageRequest()
        let classificationRequest = VNClassifyImageRequest()
        let featureRequest = VNGenerateImageFeaturePrintRequest()
        let handler = VNImageRequestHandler(cgImage: image, options: [:])

        do {
            try handler.perform([textRequest, faceRequest, saliencyRequest, classificationRequest, featureRequest])

            let observations = (textRequest.results ?? []).sorted {
                if abs($0.boundingBox.midY - $1.boundingBox.midY) > 0.03 {
                    return $0.boundingBox.midY > $1.boundingBox.midY
                }
                return $0.boundingBox.minX < $1.boundingBox.minX
            }
            for observation in observations {
                guard let candidate = observation.topCandidates(1).first else { continue }
                let box = observation.boundingBox
                ocrRegions.append(OCRRegion(text: candidate.string, confidence: candidate.confidence,
                                            x: box.minX, y: box.minY,
                                            width: box.width, height: box.height))
            }
            ocrText = ocrRegions.map(\.text).joined(separator: " ")
            faceCount = faceRequest.results?.count ?? 0
            saliencyObjectCount = saliencyRequest.results?.first?.salientObjects?.count ?? 0
            labels = (classificationRequest.results ?? [])
                .filter { $0.confidence >= 0.05 }
                .prefix(8)
                .map { LabelResult(identifier: $0.identifier, confidence: $0.confidence) }

            if let currentFeature = featureRequest.results?.first {
                if let previousFeature = previousFeatureBySource[frame.sourceID] {
                    var distance: Float = 0
                    try previousFeature.computeDistance(&distance, to: currentFeature)
                    featureDistance = String(format: "%.6f", distance)
                }
                previousFeatureBySource[frame.sourceID] = currentFeature
            }
        } catch {
            analysisError = error.localizedDescription
        }
    } else {
        analysisError = "cannot decode image"
    }

    output.append([
        frame.frameID,
        frame.sourceID,
        String(format: "%.3f", frame.timestamp),
        frame.samplingPass,
        frame.path,
        String(width),
        String(height),
        tsvSafe(ocrText),
        jsonString(ocrRegions),
        String(faceCount),
        String(saliencyObjectCount),
        jsonString(labels),
        featureDistance,
        tsvSafe(analysisError)
    ].joined(separator: "\t"))

    if (index + 1) % 100 == 0 || index + 1 == frames.count {
        fputs("processed \(index + 1)/\(frames.count)\n", stderr)
    }
}

do {
    try output.joined(separator: "\n").appending("\n")
        .write(to: URL(fileURLWithPath: outputPath), atomically: true, encoding: .utf8)
    print("wrote \(frames.count) rows to \(outputPath)")
} catch {
    fputs("output error: \(error.localizedDescription)\n", stderr)
    exit(1)
}
