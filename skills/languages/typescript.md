---
name: taskflow-typescript-standards
description: "TypeScript language standards and preferred tooling for all taskflow agents"
---

# TypeScript Standards

All agents MUST follow these conventions when working with TypeScript.

## Package Management
- **USE**: `pnpm` (NOT npm, NOT yarn)
- `pnpm add <package>` to add dependencies
- `pnpm remove <package>` to remove
- `pnpm install` to install from lockfile
- `pnpm dlx` instead of `npx`

## Runtime
- **USE**: `Node.js 24 LTS` (current default)
- Consider `Bun` for new projects if performance matters

## Type Checking & Build
- **USE**: `tsc` (TypeScript compiler) for type checking
- Strict mode enabled: `"strict": true` in tsconfig.json
- Use `satisfies` operator for type-safe object literals
- Prefer `type` over `interface` unless extending

## Linting & Formatting
- **USE**: `Biome` (NOT eslint + prettier)
- `pnpm biome check .` to lint + format check
- `pnpm biome format --write .` to format
- Configure in `biome.json`

## Testing
- **USE**: `vitest` (NOT jest)
- `pnpm vitest` to run tests
- Built-in coverage, TypeScript support, ESM native

## Key Patterns
- Prefer `const` over `let`, never `var`
- Use `Record<K, V>` over `{ [key: string]: V }`
- Use discriminated unions over type assertions
- Prefer `Map`/`Set` over plain objects for collections
- Use `zod` for runtime validation at boundaries
- Use `as const` for literal types
