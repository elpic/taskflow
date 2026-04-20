---
name: taskflow-java-standards
description: "Java language standards and preferred tooling for all taskflow agents"
---

# Java Standards

All agents MUST follow these conventions when working with Java.

## Package Management
- **USE**: `Gradle` with Kotlin DSL (NOT Maven, NOT Gradle Groovy DSL)
- `gradle init` to create projects (select Kotlin DSL when prompted)
- `build.gradle.kts` for project config (NOT `build.gradle`, NOT `pom.xml`)
- `settings.gradle.kts` for multi-project builds
- `./gradlew <task>` to run Gradle tasks via wrapper
- `./gradlew dependencies` to inspect dependency tree
- Add dependencies in `dependencies {}` block in `build.gradle.kts`

## Linting & Formatting
- **USE**: `google-java-format` via Spotless plugin (NOT Checkstyle standalone, NOT manual formatting)
- Add Spotless to `build.gradle.kts`:
  ```kotlin
  plugins {
      id("com.diffplug.spotless") version "<latest>"
  }
  spotless {
      java {
          googleJavaFormat()
      }
  }
  ```
- `./gradlew spotlessApply` to format
- `./gradlew spotlessCheck` to check formatting (used in CI)

## Testing
- **USE**: JUnit 5 + Mockito + AssertJ (NOT JUnit 4, NOT Hamcrest, NOT EasyMock)
- `./gradlew test` to run tests
- `./gradlew test --info` for verbose output
- Tests in `src/test/java/` directory
- Use `@ExtendWith(MockitoExtension.class)` for Mockito integration
- Use `assertThat(...)` from AssertJ for assertions (NOT `assertEquals`)
- Add to `build.gradle.kts`:
  ```kotlin
  dependencies {
      testImplementation("org.junit.jupiter:junit-jupiter:<version>")
      testImplementation("org.mockito:mockito-core:<version>")
      testImplementation("org.assertj:assertj-core:<version>")
  }
  tasks.test {
      useJUnitPlatform()
  }
  ```

## Version
- Target Java 21 LTS unless the project specifies otherwise
- Set in `build.gradle.kts`:
  ```kotlin
  java {
      toolchain {
          languageVersion = JavaLanguageVersion.of(21)
      }
  }
  ```
- Use modern syntax: records, sealed classes, pattern matching, text blocks, switch expressions

## Project Structure
- `src/main/java/` for production code
- `src/test/java/` for test code
- `src/main/resources/` for resources
- Package names follow reverse-domain convention: `com.example.project`
- One top-level class per file, filename matches class name

## Key Patterns
- Records for immutable data structures (NOT POJOs with getters/setters for simple data)
- Sealed classes + pattern matching for algebraic types
- Use `Optional` for nullable return values (NOT returning null)
- `var` for local type inference where it improves readability
- Prefer interfaces for dependency injection (hexagonal architecture: ports as interfaces)
- Streams and functional style for collection processing
