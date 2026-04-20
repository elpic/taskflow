---
name: taskflow-kotlin-standards
description: "Kotlin language standards and preferred tooling for all taskflow agents"
---

# Kotlin Standards

All agents MUST follow these conventions when working with Kotlin.

## Package Management
- **USE**: `Gradle` with Kotlin DSL (NOT Maven, NOT Gradle Groovy DSL)
- `gradle init` to create projects (select Kotlin DSL)
- `build.gradle.kts` for project config (NOT `build.gradle`, NOT `pom.xml`)
- `settings.gradle.kts` for multi-project builds
- `./gradlew <task>` to run Gradle tasks via wrapper
- `./gradlew dependencies` to inspect dependency tree
- Add dependencies in `dependencies {}` block in `build.gradle.kts`

## Linting & Formatting
- **USE**: `ktfmt` + `detekt` (NOT ktlint, NOT Checkstyle)
- Add both to `build.gradle.kts`:
  ```kotlin
  plugins {
      id("com.ncorti.ktfmt.gradle") version "<latest>"
      id("io.gitlab.arturbosch.detekt") version "<latest>"
  }
  ktfmt { kotlinLangStyle() }
  ```
- `./gradlew ktfmtFormat` to format
- `./gradlew ktfmtCheck` to check formatting (used in CI)
- `./gradlew detekt` to run static analysis
- `detekt.yml` at repo root for detekt rule configuration

## Testing
- **USE**: `kotlin.test` + JUnit 5 + MockK + Kotest (NOT JUnit 4, NOT Mockito for Kotlin code, NOT plain assertions)
- `./gradlew test` to run tests
- Tests in `src/test/kotlin/` directory
- Use MockK: `mockk<ServiceInterface>()` for mocking (NOT Mockito — MockK handles Kotlin idioms)
- Use Kotest assertions: `result shouldBe expected` (NOT `assertEquals`)
- Use `@Test` from `kotlin.test` for test annotations
- Add to `build.gradle.kts`:
  ```kotlin
  dependencies {
      testImplementation(kotlin("test"))
      testImplementation("io.mockk:mockk:<version>")
      testImplementation("io.kotest:kotest-assertions-core:<version>")
  }
  tasks.test { useJUnitPlatform() }
  ```

## Version
- Target Kotlin 2.1+ / JVM 21 unless the project specifies otherwise
- Set in `build.gradle.kts`:
  ```kotlin
  kotlin { jvmToolchain(21) }
  ```
- Use modern syntax: context parameters, value classes, sealed interfaces, K2 compiler features

## Project Structure
- `src/main/kotlin/` for production code
- `src/test/kotlin/` for test code
- `src/main/resources/` for resources
- Package names follow reverse-domain convention: `com.example.project`
- One top-level declaration per file where practical; filename matches primary class

## Key Patterns
- Data classes for immutable domain models and DTOs
- Sealed classes / sealed interfaces for algebraic types (domain events, results)
- `interface` as ports for dependency injection (hexagonal architecture)
- Coroutines + `Flow` for async/streaming (NOT `RxJava`, NOT callbacks)
- `Result<T>` or a custom sealed type for operations that can fail (NOT throwing exceptions for expected failures)
- Extension functions for adding behavior to existing types without inheritance
