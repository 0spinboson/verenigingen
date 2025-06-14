# Debug Scripts

Debug and troubleshooting scripts organized by component.

## Board Member Debugging (`board/`)

- **`debug_board_addition.py`** - Debug board member addition issues
- **`debug_board_console.py`** - Interactive board member debugging console
- **`debug_chapter_membership.py`** - Debug chapter membership issues

## Employee Debugging (`employee/`)

- **`debug_employee_creation.py`** - Debug employee record creation issues

## Chapter Debugging (`chapter/`)

- **`bench_debug_chapter.py`** - Debug chapter-related issues using bench context

## Usage

Run debug scripts to troubleshoot specific issues:

```bash
# Debug board member addition
python scripts/debug/board/debug_board_addition.py

# Debug employee creation
python scripts/debug/employee/debug_employee_creation.py

# Debug chapter issues
python scripts/debug/chapter/bench_debug_chapter.py
```

## Adding Debug Scripts

When adding new debug scripts:

1. Place in appropriate component subdirectory
2. Include clear documentation of what the script debugs
3. Add usage examples
4. Include error handling and informative output