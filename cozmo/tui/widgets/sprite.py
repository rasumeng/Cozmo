from pathlib import Path
from PIL import Image
from rich.color import Color as RichColor
from rich.style import Style
from rich.text import Text

SPRITE_PATH = Path(__file__).resolve().parents[3] / "Cozmo-sprite.png"

ALPHA_THRESHOLD = 16


def _rgba_to_rich(rgba: tuple[int, int, int, int]) -> RichColor | None:
    r, g, b, a = rgba
    if a < ALPHA_THRESHOLD:
        return None
    return RichColor.from_rgb(r, g, b)


def render_sprite(width: int | None = None, height: int | None = None) -> Text:
    img = Image.open(SPRITE_PATH).convert("RGBA")
    src_w, src_h = img.size

    if width is None and height is None:
        width = src_w
        height = src_h // 2
    if height is None:
        height = round(width * (src_h / src_w) * 0.5)
    if width is None:
        width = round(height * (src_w / src_h) * 2)

    if (width, height * 2) != img.size:
        img = img.resize((width, height * 2), Image.NEAREST)
    px = img.load()

    result = Text()
    for y in range(0, height * 2, 2):
        for x in range(width):
            upper = _rgba_to_rich(px[x, y])
            lower = _rgba_to_rich(px[x, y + 1]) if y + 1 < img.height else None

            if upper is None and lower is None:
                result.append(" ")
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
    console.print(render_sprite())
    console.print(render_sprite(width=40, height=12))
