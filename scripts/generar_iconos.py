"""Genera los íconos PNG de la PWA. Se corre una vez; los PNG quedan en el repositorio.

docker run --rm -v "${PWD}:/app" -w /app ghcr.io/astral-sh/uv:python3.12-bookworm-slim \
    uv run --no-project --with pillow python scripts/generar_iconos.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VERDE = (5, 150, 105)  # emerald-600, el color de la navegación
BLANCO = (255, 255, 255)
DESTINO = Path(__file__).resolve().parent.parent / "static" / "iconos"


def icono(lado, *, redondeado, escala_texto):
    if redondeado:
        imagen = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        ImageDraw.Draw(imagen).rounded_rectangle(
            (0, 0, lado - 1, lado - 1), radius=lado // 5, fill=VERDE
        )
    else:
        imagen = Image.new("RGB", (lado, lado), VERDE)
    fuente = ImageFont.load_default(size=int(lado * escala_texto))
    ImageDraw.Draw(imagen).text((lado / 2, lado / 2), "$", font=fuente, fill=BLANCO, anchor="mm")
    return imagen


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    icono(192, redondeado=True, escala_texto=0.62).save(DESTINO / "icono-192.png")
    icono(512, redondeado=True, escala_texto=0.62).save(DESTINO / "icono-512.png")
    # Maskable: fondo completo y el símbolo dentro de la zona segura (80 % central).
    icono(512, redondeado=False, escala_texto=0.45).save(DESTINO / "icono-maskable-512.png")
    # iPhone no usa transparencia: fondo completo.
    icono(180, redondeado=False, escala_texto=0.6).save(DESTINO / "icono-180.png")


if __name__ == "__main__":
    main()
