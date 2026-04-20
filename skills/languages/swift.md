---
name: taskflow-swift-standards
description: "Swift language standards and preferred tooling for all taskflow agents"
---

# Swift Standards

All agents MUST follow these conventions when working with Swift.

## Package Management
- **USE**: `Swift Package Manager` (NOT CocoaPods, NOT Carthage)
- `swift package init` to create a new package
- `swift package init --type executable` for CLI tools
- Edit `Package.swift` to add dependencies (NOT a separate lockfile tool)
- `swift package resolve` to resolve and fetch dependencies
- `swift package update` to update dependencies
- `swift build` to compile, `swift run` to run

## Linting & Formatting
- **USE**: `swift-format` (NOT SwiftLint alone, NOT Prettier for Swift)
- `swift-format format --in-place --recursive Sources/` to format
- `swift-format lint --recursive Sources/` to lint (used in CI)
- `.swift-format` JSON config file at repo root for rule configuration
- Add `swift-format` as a package dependency in `Package.swift` for consistent versioning:
  ```swift
  .package(url: "https://github.com/swiftlang/swift-format.git", from: "<version>")
  ```

## Testing
- **USE**: `swift test` with XCTest and Swift Testing framework (NOT third-party test runners)
- `swift test` to run all tests
- `swift test --filter TestSuiteName` to run a specific suite
- Use Swift Testing (`@Test`, `#expect`) for new test files (NOT `XCTestCase` subclasses for new code)
- Use XCTest for legacy/UIKit tests where Swift Testing integration is incomplete
- Tests in `Tests/<TargetName>Tests/` directory

## Version
- Target Swift 6.0+ unless the project specifies otherwise
- Swift 6 strict concurrency enabled by default in new packages:
  ```swift
  .target(
      name: "MyTarget",
      swiftSettings: [.swiftLanguageVersion(.v6)]
  )
  ```
- Use modern syntax: actors, async/await, structured concurrency, macros

## Project Structure
- `Sources/<TargetName>/` for production code
- `Tests/<TargetName>Tests/` for test code
- `Package.swift` as the single source of project config
- `.swift-format` config at repo root

## Key Patterns
- `struct` for value types and domain models (NOT `class` unless reference semantics are required)
- `actor` for shared mutable state (NOT `DispatchQueue` or locks for new code)
- `protocol` as ports for dependency injection (hexagonal architecture)
- `async/await` and `AsyncSequence` for concurrency (NOT completion handlers, NOT Combine for new code)
- `Result<Success, Failure>` for operations that can fail
- `Sendable` conformance on all types crossing actor boundaries
