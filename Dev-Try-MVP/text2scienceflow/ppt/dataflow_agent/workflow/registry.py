from __future__ import annotations

from typing import Callable, Dict


class RuntimeRegistry:
    _workflows: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, factory: Callable) -> None:
        if name in cls._workflows:
            if cls._workflows[name] is factory:
                return
            raise ValueError(
                f"Workflow '{name}' already registered by "
                f"{cls._workflows[name]} (now trying {factory})"
            )
        cls._workflows[name] = factory

    @classmethod
    def get(cls, name: str) -> Callable:
        try:
            return cls._workflows[name]
        except KeyError as exc:
            raise KeyError(
                f"Workflow '{name}' 不存在，可选值: {list(cls._workflows)}"
            ) from exc

    @classmethod
    def all(cls) -> Dict[str, Callable]:
        return dict(cls._workflows)


def register(name: str):
    def _decorator(func_or_cls):
        RuntimeRegistry.register(name, func_or_cls)
        return func_or_cls

    return _decorator

