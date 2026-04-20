---
name: taskflow-dart-standards
description: "Dart language standards and preferred tooling for all taskflow agents"
---

# Dart Standards

All agents MUST follow these conventions when working with Dart and Flutter.

## Package Management
- **USE**: `dart pub` for pure Dart, `flutter pub` for Flutter projects (NOT manual pubspec editing without the CLI)
- `dart create <project>` or `flutter create <project>` to create new projects
- `dart pub add <package>` / `flutter pub add <package>` to add dependencies
- `dart pub remove <package>` / `flutter pub remove <package>` to remove dependencies
- `dart pub get` / `flutter pub get` to install from `pubspec.lock`
- `dart pub upgrade <package>` to update a specific package
- `pubspec.yaml` and `pubspec.lock` both committed to version control

## Linting & Formatting
- **USE**: `dart format` + `dart analyze` with `very_good_analysis` (NOT custom lint rules as primary, NOT pedantic alone)
- `dart format .` to format all files
- `dart format --set-exit-if-changed .` to check formatting (used in CI)
- `dart analyze` to run static analysis
- Add `very_good_analysis` to `dev_dependencies` in `pubspec.yaml`:
  ```yaml
  dev_dependencies:
    very_good_analysis: ^<latest>
  ```
- `analysis_options.yaml` at repo root including:
  ```yaml
  include: package:very_good_analysis/analysis_options.yaml
  ```

## Testing
- **USE**: `dart test` + `mocktail` (NOT `mockito` with code generation, NOT manual test doubles)
- `dart test` to run all tests
- `flutter test` for Flutter widget and unit tests
- `dart test test/path/to/file_test.dart` to run a single file
- Tests in `test/` directory mirroring `lib/` structure
- Test filenames end with `_test.dart`
- Use `mocktail`: `class MockService extends Mock implements ServiceInterface {}` (no codegen required)
- Use `group`, `test`, and `setUp`/`tearDown` from `package:test`

## Version
- Target Dart 3.5+ / Flutter 3.27+ unless the project specifies otherwise
- Specify SDK constraint in `pubspec.yaml`:
  ```yaml
  environment:
    sdk: ">=3.5.0 <4.0.0"
    flutter: ">=3.27.0"  # Flutter projects only
  ```
- Use modern syntax: records, patterns, class modifiers (`final`, `base`, `sealed`), extension types

## Project Structure
- `lib/` for production code, `lib/src/` for internal implementation
- `test/` for test code
- `pubspec.yaml`, `pubspec.lock`, `analysis_options.yaml` at repo root
- Export public API from `lib/<package_name>.dart`
- Flutter: `lib/main.dart` as entry point; feature-based folder structure under `lib/`

## Key Patterns
- Records for lightweight immutable data structures: `(String name, int age)`
- Sealed classes for exhaustive pattern matching (domain events, states)
- Abstract classes / interfaces as ports (hexagonal architecture); inject abstractions not implementations
- `async/await` and `Stream` for asynchronous code (NOT raw `Future.then` chains)
- Null safety enforced — never use `!` (null-assert) unless the null case is genuinely impossible and documented
- `Result` pattern (e.g., via `fpdart` or custom sealed type) for operations that can fail (NOT throwing exceptions for expected failures)
