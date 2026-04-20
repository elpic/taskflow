---
name: taskflow-csharp-standards
description: "C# language standards and preferred tooling for all taskflow agents"
---

# C# Standards

All agents MUST follow these conventions when working with C#.

## Package Management
- **USE**: `dotnet CLI` (NOT Visual Studio GUI package manager, NOT manual .csproj editing)
- `dotnet new <template>` to create projects
- `dotnet add package <package>` to add NuGet dependencies
- `dotnet remove package <package>` to remove dependencies
- `dotnet restore` to install from lockfile
- `dotnet build` to compile
- `dotnet run` to run the application

## Linting & Formatting
- **USE**: `dotnet format` with `.editorconfig` (NOT StyleCop standalone, NOT ReSharper CLI)
- `dotnet format` to format and fix style issues
- `dotnet format --verify-no-changes` to check formatting (used in CI)
- `.editorconfig` at the repo root for style rules (NOT per-project config files)
- Example `.editorconfig` base rules:
  ```ini
  [*.cs]
  indent_style = space
  indent_size = 4
  end_of_line = lf
  charset = utf-8-bom
  trim_trailing_whitespace = true
  insert_final_newline = true
  dotnet_sort_system_directives_first = true
  ```

## Testing
- **USE**: xUnit + FluentAssertions + NSubstitute (NOT NUnit, NOT MSTest, NOT Moq, NOT Shouldly)
- `dotnet test` to run tests
- `dotnet test --logger "console;verbosity=detailed"` for verbose output
- Tests in a separate `*.Tests` project under `tests/`
- Use `[Fact]` for single-case tests, `[Theory]` + `[InlineData]` for parameterized tests
- Use FluentAssertions: `result.Should().Be(expected)` (NOT `Assert.Equal`)
- Use NSubstitute: `Substitute.For<IService>()` for mocking interfaces

## Version
- Target .NET 10 / C# 14 unless the project specifies otherwise
- Set in `.csproj`:
  ```xml
  <PropertyGroup>
      <TargetFramework>net10.0</TargetFramework>
      <LangVersion>14</LangVersion>
      <Nullable>enable</Nullable>
      <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  ```
- Use modern syntax: primary constructors, collection expressions, `required` members, pattern matching

## Project Structure
- Solution file (`.sln`) at the repo root
- `src/` for production projects, `tests/` for test projects
- Each project in its own subdirectory: `src/ProjectName/ProjectName.csproj`
- Namespaces match folder structure
- One class per file, filename matches class name

## Key Patterns
- Records for immutable data transfer objects (NOT classes with only getters)
- Nullable reference types enabled (`<Nullable>enable</Nullable>`) — treat warnings as errors
- Dependency injection via `IServiceCollection` (hexagonal: interfaces as ports)
- `IAsyncEnumerable<T>` for streaming data (NOT `List<T>` for large sequences)
- `CancellationToken` passed through all async call chains
- `Result<T>` pattern for domain errors (NOT throwing exceptions for expected failures)
