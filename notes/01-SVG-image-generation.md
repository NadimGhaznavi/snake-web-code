# Sample Render Code

The code below creates an SVG from the Snake Lab board state data.


```
def render_svg(snapshot: dict, cell_size: int = 32) -> str:
    board = snapshot["board"]
    width, height = board["grid_size"]

    pixel_width = width * cell_size
    pixel_height = height * cell_size

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{pixel_width}" height="{pixel_height}" '
        f'viewBox="0 0 {pixel_width} {pixel_height}">',
        '<rect width="100%" height="100%" fill="#111827"/>',
    ]

    # Grid
    for x in range(width + 1):
        px = x * cell_size
        parts.append(
            f'<line x1="{px}" y1="0" x2="{px}" y2="{pixel_height}" '
            f'stroke="#1f2937" stroke-width="1"/>'
        )

    for y in range(height + 1):
        py = y * cell_size
        parts.append(
            f'<line x1="0" y1="{py}" x2="{pixel_width}" y2="{py}" '
            f'stroke="#1f2937" stroke-width="1"/>'
        )

    # Body
    for x, y in board["snake_body"]:
        parts.append(
            f'<rect x="{x * cell_size + 2}" '
            f'y="{y * cell_size + 2}" '
            f'width="{cell_size - 4}" height="{cell_size - 4}" '
            f'rx="5" fill="#22c55e"/>'
        )

    # Head
    x, y = board["snake_head"]
    parts.append(
        f'<rect x="{x * cell_size + 1}" '
        f'y="{y * cell_size + 1}" '
        f'width="{cell_size - 2}" height="{cell_size - 2}" '
        f'rx="6" fill="#4ade80"/>'
    )

    # Food
    if board["food"] is not None:
        x, y = board["food"]
        cx = x * cell_size + cell_size / 2
        cy = y * cell_size + cell_size / 2

        parts.append(
            f'<circle cx="{cx}" cy="{cy}" '
            f'r="{cell_size * 0.3}" fill="#ef4444"/>'
        )

    parts.append("</svg>")

    return "\n".join(parts)
```