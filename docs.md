# pydantic2zod

Translates [pydantic](pydantic-docs.helpmanual.io/) -> [zod](zod.dev/) declarations.

## Installation

```sh
pip install git+https://github.com/argyle-engineering/pydantic2zod
```

## CLI

The compiler must be run within the same Python environment as your project:
```sh
$ cd my-project
$ poetry run python -m pydantic2zod my_project.models
```

## As a library

Translating **pydantic** declarations to **zod** out ouf the box may not work for
more sophisticated cases. Then you can use `pydantic2zod` as a library to implement
your own specific compiler:
```py
# my_project/scripts/pydantic_to_zod.py

import pydantic2zod

class Compiler(pydantic2zod.Compiler):
    ...

ts_src = Compiler().parse("examples.eshop").to_zod()
print(ts_src)
```

Now lets say we want to omit some models as they may not be relative in your TypeScript code:
```py
class Compiler(pydantic2zod.Compiler):
    IGNORE_TYPES = {"examples.eshop.Order"}
```

Or we can rename others:
```py
class Compiler(pydantic2zod.Compiler):
    MODEL_RENAME_RULES = {"examples.eshop.Product": "Item"}
```

We can also manually edit the models and individual fields:
```py
class Compiler(pydantic2zod.Compiler):
    MODEL_RENAME_RULES = {"examples.eshop.Product": "Item"}

    def _modify_models(self, pydantic_models: list[ClassDecl]) -> list[ClassDecl]:
        for model in pydantic_models:
            if model.name == "Item":
                for f in model.fields:
                    # In pydantic declarations Product.description is optional.
                    # Lets make it required in zod.
                    if f.name == "description":
                        f.type = BuiltinType(name="str")

        return pydantic_models
```

We could even generate new models on the fly this way.

See a more complete example at `examples/compiler_scripting.py`.
