from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Action:
    id: str
    label: str | None = None
    key: str | None = None
    available: bool = True
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class TextSegment:
    text: str
    style: str | None = None


@dataclass(frozen=True)
class PanelItem:
    segments: tuple[TextSegment, ...]


@dataclass(frozen=True)
class BlockMeta:
    source: str | None = None
    updated_at: datetime | None = None
    interval_seconds: int | None = None


@dataclass(frozen=True)
class BlockLayout:
    spans: dict[str, int] | None = None
    min_width: int | None = None
    equal_height: bool | None = None
    pin_footer: bool | None = None


@dataclass(frozen=True)
class StackResponsive:
    directions: dict[str, str] | None = None


@dataclass(frozen=True)
class PanelBlock:
    title: str | None
    bind: str
    layout: BlockLayout | None = None
    actions: tuple[Action, ...] = ()


@dataclass(frozen=True)
class TableBlock:
    title: str | None
    bind: str
    layout: BlockLayout | None = None
    actions: tuple[Action, ...] = ()


@dataclass(frozen=True)
class PhotoCardBlock:
    title: str | None
    bind: str
    mode: str = "native_hint"
    hint: str | None = None
    layout: BlockLayout | None = None
    actions: tuple[Action, ...] = ()


@dataclass(frozen=True)
class Scatter2DOptions:
    width: int | None = None
    height: int | None = None
    plane: str = "auto"


@dataclass(frozen=True)
class Scatter2DBlock:
    title: str | None
    bind: str
    options: Scatter2DOptions | None = None
    layout: BlockLayout | None = None
    actions: tuple[Action, ...] = ()


@dataclass(frozen=True)
class StackBlock:
    direction: str
    children: tuple["Block", ...]
    layout: BlockLayout | None = None
    responsive: StackResponsive | None = None
    actions: tuple[Action, ...] = ()


Block = PanelBlock | TableBlock | PhotoCardBlock | Scatter2DBlock | StackBlock


@dataclass(frozen=True)
class Slot:
    name: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class Frame:
    title: str | None
    slots: tuple[Slot, ...]
    actions: tuple[Action, ...] = ()
