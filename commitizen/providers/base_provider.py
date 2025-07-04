from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

import tomlkit

from commitizen.config.base_config import BaseConfig


class VersionProvider(ABC):
    """
    Abstract base class for version providers.

    Each version provider should inherit and implement this class.
    """

    config: BaseConfig

    def __init__(self, config: BaseConfig) -> None:
        self.config = config

    @abstractmethod
    def get_version(self) -> str:
        """
        Get the current version
        """

    @abstractmethod
    def set_version(self, version: str) -> None:
        """
        Set the new current version
        """


class FileProvider(VersionProvider):
    """
    Base class for file-based version providers
    """

    filename: ClassVar[str]

    @property
    def file(self) -> Path:
        return Path() / self.filename


class JsonProvider(FileProvider):
    """
    Base class for JSON-based version providers
    """

    indent: ClassVar[int] = 2

    def get_version(self) -> str:
        document = json.loads(self.file.read_text())
        return self.get(document)

    def set_version(self, version: str) -> None:
        document = json.loads(self.file.read_text())
        self.set(document, version)
        self.file.write_text(json.dumps(document, indent=self.indent) + "\n")

    def get(self, document: Mapping[str, str]) -> str:
        return document["version"]

    def set(self, document: dict[str, Any], version: str) -> None:
        document["version"] = version


class TomlProvider(FileProvider):
    """
    Base class for TOML-based version providers
    """

    def get_version(self) -> str:
        document = tomlkit.parse(self.file.read_text())
        return self.get(document)

    def set_version(self, version: str) -> None:
        document = tomlkit.parse(self.file.read_text())
        self.set(document, version)
        self.file.write_text(tomlkit.dumps(document))

    def get(self, document: tomlkit.TOMLDocument) -> str:
        return document["project"]["version"]  # type: ignore[index,return-value]

    def set(self, document: tomlkit.TOMLDocument, version: str) -> None:
        document["project"]["version"] = version  # type: ignore[index]
