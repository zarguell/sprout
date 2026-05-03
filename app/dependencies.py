"""Application dependencies, including dual JSON+form data parsing."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError


def form_or_json(model_class: type[BaseModel]) -> callable:
    """Factory that returns a dependency which parses request body as
    form-encoded data or JSON, depending on Content-Type header.

    Usage in route:
        data: MyModel = Depends(form_or_json(MyModel))

    Handles three cases:
    - application/x-www-form-urlencoded: parse form fields, coerce to model
    - application/json: parse JSON body
    - No body / unknown content type: return model with default values
    """

    async def _parser(request: Request) -> BaseModel:
        content_type = (request.headers.get("content-type") or "").lower()

        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            raw: dict[str, Any] = {}
            for key in form:
                values = form.getlist(key)
                raw[key] = values[0] if len(values) == 1 else values
            try:
                return model_class(**raw)
            except ValidationError as e:
                raise RequestValidationError(errors=e.errors()) from e
        else:
            body = await request.body()
            if body:
                import json
                try:
                    return model_class(**json.loads(body))
                except ValidationError as e:
                    raise RequestValidationError(errors=e.errors()) from e
            return model_class()

    return _parser