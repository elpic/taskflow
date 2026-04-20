---
name: taskflow-ruby-standards
description: "Ruby language standards and preferred tooling for all taskflow agents"
---

# Ruby Standards

All agents MUST follow these conventions when working with Ruby.

## Package Management
- **USE**: `Bundler` (NOT manually managing gems, NOT system gems)
- `bundle init` to create a new `Gemfile`
- `bundle add <gem>` to add dependencies
- `bundle install` to install from `Gemfile.lock`
- `bundle exec <command>` to run commands in the bundle context
- `bundle update <gem>` to update a specific gem
- `Gemfile` and `Gemfile.lock` both committed to version control

## Type Checking
- **USE**: `Sorbet` (NOT RBS alone, NOT steep)
- `bundle exec srb init` to set up Sorbet in a project
- `bundle exec srb tc` to type-check
- Use `T.let`, `T.must`, `sig` blocks for type annotations
- `typed: strict` in all new files (NOT `typed: false`, NOT `typed: true` unless upgrading)
- Run `bundle exec tapioca gem` to generate RBI files for gems

## Linting & Formatting
- **USE**: `RuboCop` (NOT Standard alone, NOT Reek alone)
- `bundle exec rubocop` to lint
- `bundle exec rubocop -a` to auto-correct safe offenses
- `bundle exec rubocop -A` to auto-correct all offenses (use with care)
- `.rubocop.yml` at the repo root for configuration
- Enable `rubocop-rspec`, `rubocop-sorbet` extensions where applicable

## Testing
- **USE**: RSpec + factory_bot (NOT Minitest, NOT Test::Unit, NOT fixtures)
- `bundle exec rspec` to run tests
- `bundle exec rspec spec/path/to/file_spec.rb` to run a single file
- Tests in `spec/` directory mirroring `lib/` or `app/` structure
- Use `factory_bot` for test data (NOT hardcoded hashes, NOT fixtures)
- Use `let` and `subject` for DRY setup; prefer `described_class`
- Use `expect(...).to` syntax (NOT `should` syntax)

## Version
- Target Ruby 3.3+ unless the project specifies otherwise
- Specify in `.ruby-version` and `Gemfile`:
  ```ruby
  ruby "~> 3.3"
  ```
- Use modern syntax: pattern matching (`case/in`), endless methods, numbered block parameters

## Project Structure
- `lib/` for library code, `app/` for Rails applications
- `spec/` for tests with `spec/spec_helper.rb` and `spec/rails_helper.rb`
- `Gemfile`, `Gemfile.lock`, `.rubocop.yml`, `.ruby-version` at repo root
- `sorbet/` directory for Sorbet RBI files (committed)

## Key Patterns
- Prefer immutable value objects (use `Data.define` for simple structs in Ruby 3.2+)
- `Struct` or `Data` for data containers (NOT OpenStruct)
- Dependency injection via constructor arguments (hexagonal: plain Ruby objects as adapters)
- Service objects for complex business logic: single `#call` method
- Use `dry-monads` `Result` type for operations that can fail (NOT raising exceptions for expected failures)
