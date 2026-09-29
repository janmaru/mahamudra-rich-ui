from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    frame_border_style: str = "bright_blue"
    slot_border_style: str = "blue"
    panel_border_style: str = "magenta"
    table_border_style: str = "green"
    scatter_border_style: str = "bright_blue"
    title_style: str = "bold bright_white"
    slot_title_style: str = "bold bright_cyan"
    table_header_style: str = "bold bright_yellow"
    muted_style: str = "dim"
    action_disabled_style: str = "dim yellow"

