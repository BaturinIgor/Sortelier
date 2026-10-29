// Проверка движка "Рынка" на macOS-раннере: swiftc Match3Board.swift main.swift.
// Играет уровни подсказкой и сверяет ленту событий с состоянием доски: сцена, которая
// повторяет события, должна в каждой клетке видеть ту же фишку, что и движок.
import Foundation

struct File: Decodable { let levels: [M3Level] }

let path = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "match3.json"
let file = try! JSONDecoder().decode(File.self, from: Data(contentsOf: URL(fileURLWithPath: path)))
let seeds = CommandLine.arguments.count > 2 ? Int(CommandLine.arguments[2]) ?? 12 : 12

var problems = 0
func problem(_ s: String) {
    problems += 1
    if problems < 60 { print("PROBLEM " + s) }
}

/// Зеркало сцены: какая фишка в какой клетке и какие узлы живы.
struct Mirror {
    var idAt: [M3Cell: Int] = [:]
    var alive = Set<Int>()

    init(_ b: M3Board) {
        for p in b.allCells { if let t = b.tile(p) { idAt[p] = t.id; alive.insert(t.id) } }
    }

    mutating func apply(_ line: M3Timeline, level: Int) {
        var last = -1.0
        for e in line.events {
            if e.t < last { problem("L\(level) events out of order") }
            last = e.t
            switch e.event {
            case let .swap(a, b, back):
                if idAt[a] == nil || idAt[b] == nil { problem("L\(level) swap of empty cell") }
                if !back { let t = idAt[a]; idAt[a] = idAt[b]; idAt[b] = t }
            case let .pop(id, cell, _, _):
                if !alive.contains(id) { problem("L\(level) pop of dead \(id)") }
                alive.remove(id)
                if idAt[cell] == id { idAt[cell] = nil } else { problem("L\(level) pop \(id) not at \(cell)") }
            case let .create(tile, cell):
                if let other = idAt[cell], alive.contains(other) { problem("L\(level) create over live \(other) at \(cell)") }
                idAt[cell] = tile.id
                alive.insert(tile.id)
            case let .fire(id, cell, _):
                if let id = id {
                    if !alive.contains(id) { problem("L\(level) fire of dead \(id)") }
                    alive.remove(id)
                    if idAt[cell] == id { idAt[cell] = nil }
                    for (k, v) in idAt where v == id { idAt[k] = nil }
                }
            case let .combo(a, b, _, _, _):
                for id in [a, b] {
                    alive.remove(id)
                    for (k, v) in idAt where v == id { idAt[k] = nil }
                }
            case let .convert(id, _, _, _):
                if !alive.contains(id) { problem("L\(level) convert of dead \(id)") }
            case .crate, .ice, .jam, .booster:
                break
            case let .move(id, path, _):
                if !alive.contains(id) { problem("L\(level) move of dead \(id) path \(path)") }
                for (k, v) in idAt where v == id && k != path.last! { idAt[k] = nil }
                if let to = path.last {
                    if let other = idAt[to], other != id, alive.contains(other) { problem("L\(level) move onto live \(other) at \(to)") }
                    idAt[to] = id
                }
            case let .spawn(tile, path, _):
                alive.insert(tile.id)
                if let to = path.last {
                    if let other = idAt[to], alive.contains(other) { problem("L\(level) spawn onto live \(other) at \(to)") }
                    idAt[to] = tile.id
                }
            case let .shuffle(list):
                idAt = [:]
                for (id, cell) in list { idAt[cell] = id }
                for (k, v) in idAt where !alive.contains(v) { idAt[k] = nil }
            }
        }
    }

    func compare(_ b: M3Board, level: Int, step: String) {
        for p in b.allCells {
            let real = b.tile(p)?.id
            let seen = idAt[p].flatMap { alive.contains($0) ? $0 : nil }
            if real != seen { problem("L\(level) \(step): cell \(p.r),\(p.c) board \(String(describing: real)) scene \(String(describing: seen))") }
        }
    }
}

var report: [String] = []
for level in file.levels {
    var wins = 0
    var used: [Int] = []
    var jamPerMove: [Double] = []
    for seed in 0..<seeds {
        var board = M3Board(level: level, seed: UInt64(seed * 7919 + 13))
        var mirror = Mirror(board)
        if seed % 3 == 0 {
            let line = board.placeStart([.rowPin, .bomb, .whisk])
            mirror.apply(line, level: level.id)
            mirror.compare(board, level: level.id, step: "start")
        }
        var moves = 0
        let jam0 = board.gotJam
        while moves < level.moves + 20 && !board.won {
            var line: M3Timeline?
            if let h = board.hint() {
                line = board.swap(h.0, h.1)
            } else if let tap = board.moves().first(where: { $0.1 == nil }) {
                line = board.tap(tap.0)
            }
            guard let l = line else { problem("L\(level.id) no move at \(moves)"); break }
            if !l.counted { problem("L\(level.id) hint move not counted") }
            mirror.apply(l, level: level.id)
            mirror.compare(board, level: level.id, step: "move \(moves)")
            if !board.findGroups().isEmpty { problem("L\(level.id) groups left after move") }
            if !board.hasMove() { problem("L\(level.id) no moves after settle") }
            if l.end > 30 { problem("L\(level.id) timeline \(l.end)s") }
            moves += 1
        }
        if board.won {
            wins += 1
            used.append(moves)
            var fin = board
            let line = fin.finale(moves: max(0, level.moves - moves))
            var m2 = mirror
            m2.apply(line, level: level.id)
            m2.compare(fin, level: level.id, step: "finale")
        }
        jamPerMove.append(Double(board.gotJam - jam0) / Double(max(1, moves)))
    }
    used.sort()
    let p50 = used.isEmpty ? -1 : used[used.count / 2]
    report.append("L\(level.id) moves \(level.moves) win \(wins)/\(seeds) p50 \(p50) jam/move \(String(format: "%.2f", jamPerMove.reduce(0, +) / Double(seeds)))")
}
print(report.joined(separator: "\n"))
print("problems: \(problems)")
