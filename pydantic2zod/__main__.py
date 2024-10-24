"""Minimal Pydantic to zod compiler.

```sh
pydantic2zod > model.ts
```

Pydantic - declarative data classes in Python.
zod - declarative data classes in TypeScript.

Compilation is a 2 step process:

1. Parse Pydantic declarations - Python code.
2. Generate zod declarations - TypeScript code.
"""

import logging
from pathlib import Path
from typing import Optional

import rich
import typer
from rich.logging import RichHandler

from pydantic2zod._compiler import Compiler

_logger = logging.getLogger(__name__)


def main(
    file: str,
    out_to: Optional[str],
    silent: bool = typer.Option(
        False, "-s", "--silent", help="If true, don't print the logs."
    ),
) -> None:
    if not silent:
        logging.basicConfig(
            level="INFO", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
        )
    try:
        zod_src_code = Compiler().parse(file).to_zod()
        if out_to:
            Path(out_to).write_text(zod_src_code)
            rich.print(f"Saved to: '{out_to}'")
        else:
            rich.print(zod_src_code)
    except Exception:
        _logger.exception("Compiler failed:")


if __name__ == "__main__":
    typer.run(main)
