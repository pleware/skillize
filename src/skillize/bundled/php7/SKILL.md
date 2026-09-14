---
name: php7
conflicts: [php8]
description: >
  Write and review PHP that must parse on PHP 7.2–7.4 (treat 7.4 as the
  default). Use when editing PHP, Composer, PHPUnit, or Laravel 5–7 in a
  tree whose pin is major 7. Never together with php8. Never emit PHP 8
  syntax (match, named arguments, constructor property promotion, union
  types, mixed, attributes, enums, readonly, nullsafe, str_contains).
---

# PHP 7 (7.2–7.4)

This tree runs **PHP 7**. Code you add must parse on the pinned minor.
The market default is PHP 8 — do not copy it here.

## Detect the pin first

Read, in this order, and stop at the first exact version:

1. `mise.toml` `[tools] php`
2. `composer.json` `require.php` (the lowest number in a range is the floor)
3. `.devtools.yaml` / a `php74` style alias
4. `php -v` only if nothing else exists

Then pick a **ceiling**:

| Pin | Ceiling | Also forbidden (on top of all PHP 8) |
| --- | --- | --- |
| 7.4, `^7.4`, `php74` | 7.4 | nothing extra from the 7.4 list below |
| 7.3 | 7.3 | typed properties, arrow functions, `??=`, unpacking with string keys |
| 7.2, `^7.2` | 7.2 | everything 7.3 plus: trailing commas in calls, `array_key_first` / `array_key_last`, `is_countable`, `JSON_THROW_ON_ERROR`, flexible heredoc |

If the pin is missing, assume **7.4** and say so. If the pin is `8.x`, stop
and use `php8` instead. Never load both.

## Hard ban — PHP 8 syntax

These do not parse on 7.4. Do not write them, not even in new files.

- `match`, named arguments, constructor property promotion
- union types (`int|string`), `mixed`, `never`, nullable union (`int|null` is fine as `?int` — that is 7.1)
- attributes (`#[...]`)
- enums, `readonly`, fibers, intersection types, DNF types
- nullsafe `?->`
- `throw` as an expression
- first-class callables (`strlen(...)`)
- `str_contains`, `str_starts_with`, `str_ends_with` (use `strpos` / `substr`)
- `array_is_list`, `enum` casts, property hooks, asymmetric visibility
- `#[Override]`, `json_validate`
- typed class constants, constants in traits, readonly classes

Do not "modernise" a 7.x file to 8.x unless the user is running a
migration turn with an explicit PHP 8 pin.

## Allowed on 7.4 (the default)

Use these when the ceiling is 7.4 and the surrounding file already would:

- scalar / return types, `?Type`, `void`, `iterable`, `object` (7.2)
- `??`, `??=`, `<=>`, short arrays `[]`, `...` unpacking (string keys: 7.4)
- typed properties, arrow `fn`, covariant returns / contravariant params
- trailing commas in grouped `use` (7.2) and in call argument lists (7.3)
- `array_key_first` / `array_key_last`, `is_countable` (7.3)
- `JSON_THROW_ON_ERROR` (7.3)
- multi-catch, class-constant visibility, anonymous classes
- `WeakReference` (7.4). Not `WeakMap` (8.0).

Do **not** add `declare(strict_types=1);` to a file that does not already
have it. Legacy trees mix strict and weak files; match the file.

## Style that belongs in 7.x

- `array()` and `[]` are both fine; match the file.
- Prefer `===` / `!==`. Do not use `==` for new comparisons.
- Visibility on every method and property you touch.
- Constructor: assign properties in the body. No promotion.
- Errors: existing code often uses return codes or exceptions — match the
  module. Do not invent a new Result type or a PHP 8 `throw` expression.
- Strings: `sprintf` / concatenation. No str_contains.
- JSON: `json_decode($raw, true)` plus `json_last_error()` unless the file
  already uses `JSON_THROW_ON_ERROR` (7.3+).

### Replacements for habits copied from PHP 8

```php
// NO (8.0+)                    YES (7.4)
str_contains($h, $n)            strpos($h, $n) !== false
str_starts_with($h, $n)         substr($h, 0, strlen($n)) === $n
str_ends_with($h, $n)           substr($h, -strlen($n)) === $n
$a?->foo()                      $a !== null ? $a->foo() : null
fn (int|string $x) => $x        // pick one type, or skip the hint
public function __construct(    public function __construct(string $name)
    public string $name,        {
) {}                                $this->name = $name;
                                }
match ($x) { ... }              switch ($x) { ... }
```

On **7.2** also avoid arrow functions, typed properties, and `??=`
(`$a = $a ?? $b` instead).

## Frameworks and tests

Old Laravel (5.x / 6.x / 7.x) may sit on this pin. Do **not** emit Laravel
8+ / 11+ / 13 idioms:

- no `bootstrap/app.php` with `Application::configure`
- no Pest 2/3/4, no PHPUnit 10+
- no model enums, no constructor promotion in controllers
- no `$request->enum()`, no `Rule::enum`

PHPUnit: 8.x or 9.x is the 7.4-era range. `TestCase` methods stay
`function testFoo(): void` with `$this->assertSame`. No attributes
(`#[Test]`).

Composer: do not bump `require.php` to `^8.0` from this skill. Do not add
packages that require PHP 8.

Rector / PHPStan: only with `--dry-run` unless the user asked to apply, and
only rule sets that target the detected ceiling (`php74` / `php72`), never
`php80`+.

## What this skill is not

- Not `php8`. That is a different skill, from a PHP 8 pack.
- Not a Laravel 13 / Horizon / Pest skill.
- Not permission to rewrite a 7.2 hub as if it were 7.4 — honour the pin.
