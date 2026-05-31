from functools import lru_cache

from pydantic import BaseModel, RootModel


@lru_cache(maxsize=None)  # noqa: UP033
def pydantic_list(model: type[BaseModel]) -> type[RootModel]:
    """Build a cached ``RootModel`` wrapping ``list[model]``.

    drf-spectacular's pydantic extension expects a ``BaseModel`` *class* as the
    response. Passing ``Model(many=True)`` (DRF style) instantiates the pydantic
    model instead, which later crashes schema generation when the extension reads
    ``target.__name__``. Wrapping the model in a ``RootModel`` lets pydantic emit a
    proper array JSON schema that references the item component.
    """
    wrapper = RootModel[list[model]]
    wrapper.__name__ = f"{model.__name__}List"
    return wrapper
