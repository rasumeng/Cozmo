from pathlib import Path
from PIL import Image
from rich.color import Color as RichColor
from rich.style import Style
from rich.text import Text

SPRITE_PATH = Path(__file__).resolve().parents[2] / "Cozmo-sprite.png"

ALPHA_THRESHOLD = 16  # lower than before; blend rather than hard-cut where possible


def _rgba_to_rich(rgba: tuple[int, int, int, int]) -> RichColor | None:
    r, g, b, a = rgba
    if a < ALPHA_THRESHOLD:
        return None
    return RichColor.from_rgb(r, g, b)


def render_sprite(width: int | None = None, height: int | None = None) -> Text:
    """Convert Cozmo-sprite.png to ANSI half-block art.

    If width/height are omitted, they're derived from the source image's
    aspect ratio (accounting for terminal cells being ~2x taller than wide).
    """
    img = Image.open(SPRITE_PATH).convert("RGBA")
    src_w, src_h = img.size

    if width is None and height is None:
        height = 16  # sensible default row count
    if height is None:
        height = round(width * (src_h / src_w) * 0.5)
    if width is None:
        width = round(height * (src_w / src_h) * 2)

    # NEAREST keeps pixel-art edges crisp instead of blurring them
    img = img.resize((width, height * 2), Image.NEAREST)
    px = img.load()

    result = Text()
    for y in range(0, height * 2, 2):
        for x in range(width):
            upper = _rgba_to_rich(px[x, y])
            lower = _rgba_to_rich(px[x, y + 1]) if y + 1 < img.height else None

            if upper is None and lower is None:
                result.append(" ")  # transparent, no bg forced
            elif upper == lower:
                result.append(" ", Style(bgcolor=upper))
            elif lower is None:
                result.append("▀", Style(color=upper))
            elif upper is None:
                result.append("▄", Style(color=lower))
            else:
                result.append("▀", Style(color=upper, bgcolor=lower))
        result.append("\n")
    return result


if __name__ == "__main__":
    from rich.console import Console
    console = Console()
    console.print(render_sprite())          # auto-sized from aspect ratio
    console.print(render_sprite(width=32, height=16))  # near-1:1 pixel mapping