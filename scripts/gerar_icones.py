"""Gera os ícones do PWA (PNG) sem dependências externas. Uso: python -m scripts.gerar_icones

Desenho: quadrado azul (#1877F2) com cantos arredondados e um "T" branco. A versão "maskable" ocupa a área
inteira (o sistema recorta o formato) e mantém o "T" dentro da zona segura de 80%.
"""
import struct
import zlib
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent / "app" / "views" / "static" / "icons"
AZUL = (0x18, 0x77, 0xF2)
BRANCO = (0xFF, 0xFF, 0xFF)
SS = 4  # supersampling para bordas suaves


def _dentro_retangulo_arredondado(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _pixel(u, v, maskable):
    """u, v em [0, 1). Retorna (r, g, b, a)."""
    if maskable:
        fundo = True
        escala, ox = 0.62, 0.19  # "T" dentro da zona segura
    else:
        fundo = _dentro_retangulo_arredondado(u, v, 0.0, 0.0, 1.0, 1.0, 0.22)
        escala, ox = 0.70, 0.15
    if not fundo:
        return (0, 0, 0, 0)
    # coordenadas locais do "T" (0..1 dentro da caixa do glifo)
    tx, ty = (u - ox) / escala, (v - ox) / escala
    barra = _dentro_retangulo_arredondado(tx, ty, 0.10, 0.12, 0.90, 0.32, 0.05)
    haste = _dentro_retangulo_arredondado(tx, ty, 0.38, 0.12, 0.62, 0.90, 0.05)
    return (*BRANCO, 255) if (barra or haste) else (*AZUL, 255)


def _render(tamanho, maskable=False):
    linhas = []
    for y in range(tamanho):
        linha = bytearray([0])  # filtro PNG "None"
        for x in range(tamanho):
            acc = [0, 0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    u = (x + (sx + 0.5) / SS) / tamanho
                    v = (y + (sy + 0.5) / SS) / tamanho
                    r, g, b, a = _pixel(u, v, maskable)
                    acc[0] += r * a
                    acc[1] += g * a
                    acc[2] += b * a
                    acc[3] += a
            n = SS * SS
            alpha = acc[3] / n
            if acc[3]:
                linha += bytes((round(acc[0] / acc[3]), round(acc[1] / acc[3]), round(acc[2] / acc[3]), round(alpha)))
            else:
                linha += b"\x00\x00\x00\x00"
        linhas.append(bytes(linha))
    return b"".join(linhas)


def _png(tamanho, dados):
    def chunk(tipo, conteudo):
        c = tipo + conteudo
        return struct.pack(">I", len(conteudo)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", tamanho, tamanho, 8, 6, 0, 0, 0)  # RGBA 8 bits
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(dados, 9)) + chunk(b"IEND", b"")


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<rect width="100" height="100" rx="22" fill="#1877F2"/>
<rect x="22" y="23.4" width="56" height="14" rx="3.5" fill="#fff"/>
<rect x="41.6" y="23.4" width="16.8" height="54.6" rx="3.5" fill="#fff"/>
</svg>
"""

ARQUIVOS = {
    "icon-192.png": (192, False),
    "icon-512.png": (512, False),
    "maskable-512.png": (512, True),
    "apple-touch-icon.png": (180, True),  # iOS aplica os cantos sozinho
    "favicon-32.png": (32, False),
}


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nome, (tam, mask) in ARQUIVOS.items():
        (DESTINO / nome).write_bytes(_png(tam, _render(tam, mask)))
        print("gerado", nome)
    (DESTINO / "icon.svg").write_text(SVG, encoding="utf-8")
    print("gerado icon.svg")


if __name__ == "__main__":
    main()
