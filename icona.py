"""Icona dell'app (due auricolari stilizzati), disegnata con Pillow.

Usata per l'icona vicino all'orologio e, col comando sotto, per il file .ico del .exe:
    python icona.py      -> crea icona.ico
"""
from PIL import Image, ImageDraw


def crea_icona(lato=64):
    k = 4  # disegno 4 volte più grande e poi rimpicciolisco: bordi lisci
    L = lato * k
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # sfondo: cerchio scuro, stile Apple
    d.ellipse((0, 0, L - 1, L - 1), fill=(28, 28, 30, 255))
    bianco = (255, 255, 255, 255)
    for cx in (0.36, 0.64):  # due auricolari: testa tonda + gambo
        x = cx * L
        r = 0.13 * L
        d.ellipse((x - r, 0.22 * L, x + r, 0.22 * L + 2 * r), fill=bianco)
        g = 0.045 * L
        gx = x + (0.06 * L if cx < 0.5 else -0.06 * L)
        d.rounded_rectangle((gx - g, 0.38 * L, gx + g, 0.78 * L), radius=g, fill=bianco)
    return img.resize((lato, lato), Image.LANCZOS)


if __name__ == "__main__":
    crea_icona(256).save("icona.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                             (64, 64), (128, 128), (256, 256)])
    print("Creato icona.ico")
