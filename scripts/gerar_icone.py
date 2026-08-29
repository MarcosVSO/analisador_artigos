"""Gera scripts/icone.ico.

Rodar de novo so e preciso se voce quiser mudar o desenho - o .ico fica
versionado junto com o resto.

O desenho: uma folha de artigo com linhas de texto e uma lupa sobreposta,
que e a mesma metafora do botao de detalhes na listagem.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SAIDA = Path(__file__).resolve().parent / "icone.ico"

# O Windows escolhe o tamanho conforme o contexto (barra de tarefas, desktop,
# Alt+Tab). Desenhar cada um em separado, em vez de reduzir o maior, evita o
# borrao nos tamanhos pequenos.
TAMANHOS = (16, 24, 32, 48, 64, 128, 256)

PAPEL = (250, 250, 252, 255)
BORDA = (120, 130, 145, 255)
TEXTO = (150, 160, 175, 255)
DESTAQUE = (37, 99, 235, 255)
VIDRO = (219, 234, 254, 255)


def desenhar(lado: int) -> Image.Image:
    # Desenha 4x maior e reduz: e o jeito barato de ter bordas suaves sem
    # antialias manual em cada primitiva.
    escala = 4
    px = lado * escala
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    u = px / 64  # unidade de grade, para a mesma proporcao em todo tamanho

    # Folha
    folha = [10 * u, 6 * u, 46 * u, 58 * u]
    d.rounded_rectangle(folha, radius=3 * u, fill=PAPEL, outline=BORDA, width=max(1, int(1.2 * u)))

    # Linhas de texto
    largura_linha = max(1, int(2.2 * u))
    for i, comprimento in enumerate((26, 22, 26, 18, 24)):
        y = (14 + i * 7) * u
        d.line(
            [(16 * u, y), ((16 + comprimento) * u, y)],
            fill=TEXTO,
            width=largura_linha,
        )

    # Lupa
    centro = (42 * u, 40 * u)
    raio = 13 * u
    caixa = [
        centro[0] - raio,
        centro[1] - raio,
        centro[0] + raio,
        centro[1] + raio,
    ]
    d.ellipse(caixa, fill=VIDRO, outline=DESTAQUE, width=max(2, int(3 * u)))
    d.line(
        [(centro[0] + raio * 0.72, centro[1] + raio * 0.72), (57 * u, 55 * u)],
        fill=DESTAQUE,
        width=max(2, int(4 * u)),
    )

    return img.resize((lado, lado), Image.LANCZOS)


def main() -> None:
    imagens = [desenhar(t) for t in TAMANHOS]
    maior = imagens[-1]
    maior.save(SAIDA, format="ICO", sizes=[(t, t) for t in TAMANHOS])
    print(f"  icone gerado: {SAIDA}  ({SAIDA.stat().st_size / 1024:.1f} KB)")
    print(f"  tamanhos: {', '.join(f'{t}x{t}' for t in TAMANHOS)}")


if __name__ == "__main__":
    main()
