---
name: taskflow-php-standards
description: "PHP language standards and preferred tooling for all taskflow agents"
---

# PHP Standards

All agents MUST follow these conventions when working with PHP.

## Package Management
- **USE**: `Composer` (NOT PEAR, NOT manual inclusion)
- `composer init` to create a new `composer.json`
- `composer require <vendor/package>` to add dependencies
- `composer require --dev <vendor/package>` to add dev dependencies
- `composer install` to install from `composer.lock`
- `composer update <vendor/package>` to update a specific package
- `composer.json` and `composer.lock` both committed to version control
- Use PSR-4 autoloading in `composer.json`

## Type Checking
- **USE**: `PHPStan` at level 9 (NOT Psalm, NOT Phan)
- `vendor/bin/phpstan analyse` to type-check
- `phpstan.neon` at the repo root for configuration:
  ```neon
  parameters:
      level: 9
      paths:
          - src
  ```
- `vendor/bin/phpstan analyse --generate-baseline` to create a baseline for legacy code
- All new code must pass level 9 with zero errors (no baseline entries)

## Linting & Formatting
- **USE**: `php-cs-fixer` with PER-CS 2.0 ruleset (NOT PHP_CodeSniffer, NOT manual formatting)
- `vendor/bin/php-cs-fixer fix` to format
- `vendor/bin/php-cs-fixer fix --dry-run --diff` to check formatting (used in CI)
- `.php-cs-fixer.php` at the repo root:
  ```php
  <?php
  return (new PhpCsFixer\Config())
      ->setRules(['@PER-CS2.0' => true])
      ->setFinder(PhpCsFixer\Finder::create()->in(__DIR__ . '/src'));
  ```

## Testing
- **USE**: PHPUnit + Mockery (NOT Prophecy, NOT plain PHPUnit mocks for complex cases)
- `vendor/bin/phpunit` to run tests
- `vendor/bin/phpunit --filter TestClassName` to run a single test class
- Tests in `tests/` directory mirroring `src/` structure
- `phpunit.xml` or `phpunit.xml.dist` at repo root for configuration
- Use Mockery: `Mockery::mock(ServiceInterface::class)` for mocking
- Use `tearDown(): void { Mockery::close(); }` in test classes using Mockery

## Version
- Target PHP 8.3+ unless the project specifies otherwise
- Declare strict types in every file: `declare(strict_types=1);`
- Use modern syntax: readonly classes, enums, fibers, first-class callable syntax, named arguments

## Project Structure
- `src/` for production code, `tests/` for test code
- `composer.json`, `composer.lock`, `phpstan.neon`, `.php-cs-fixer.php` at repo root
- Namespaces match directory structure under `src/`
- One class per file, filename matches class name

## Key Patterns
- Readonly classes and properties for value objects and DTOs
- Enums for fixed sets of values (NOT class constants for domain enums)
- Interfaces as ports (hexagonal architecture) — inject interfaces, not concrete classes
- `never` return type for methods that always throw
- Named arguments for clarity when calling functions with many parameters
- Union types and intersection types over docblock-only annotations
