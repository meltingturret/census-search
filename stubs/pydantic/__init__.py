"""Minimal pydantic stub for testing."""
from typing import Any, Optional, get_type_hints
import dataclasses

class BaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        # Apply defaults from class annotations
        for name, default in self._field_defaults().items():
            if not hasattr(self, name):
                setattr(self, name, default() if callable(default) else default)

    def _field_defaults(self):
        defaults = {}
        for cls in reversed(type(self).__mro__):
            for k, v in vars(cls).items():
                if not k.startswith('_') and not callable(v) and not isinstance(v, (classmethod, staticmethod, property)):
                    defaults[k] = v
        return defaults

    def model_dump(self):
        result = {}
        for cls in type(self).__mro__:
            for k in vars(cls):
                if not k.startswith('_') and not callable(getattr(cls, k, None)) and not isinstance(vars(cls).get(k), (classmethod, staticmethod, property)):
                    if hasattr(self, k):
                        result[k] = getattr(self, k)
        return result
