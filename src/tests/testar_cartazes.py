"""
testar_cartazes.py
Testa o OCR em cada foto da pasta testes_cartaz/ e exibe o resultado.

Uso:
    python testar_cartazes.py
    python testar_cartazes.py testes_cartaz/foto_especifica.jpg
"""

import os
import sys
from pathlib import Path

# Configura o Django sem servidor
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pricescan.settings")
import django

django.setup()

from src.ocr import extrair_texto, parsear_cartaz

PASTA = Path(__file__).parent / "testes_cartaz"
EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

if __name__ == "__main__":
    # Se passou um arquivo específico como argumento, usa só ele
    if len(sys.argv) > 1:
        fotos = [Path(sys.argv[1])]
    else:
        fotos = sorted(f for f in PASTA.iterdir() if f.suffix.lower() in EXTENSOES)

    if not fotos:
        print(f"Nenhuma foto encontrada em {PASTA}")
        print("Coloque imagens .jpg/.png na pasta testes_cartaz/ e rode novamente.")
        sys.exit(0)

    SEP = "─" * 60

    for foto in fotos:
        print(f"\n{SEP}")
        print(f"📷  {foto.name}")
        print(SEP)

        try:
            texto = extrair_texto(str(foto))
        except Exception as e:
            print(f"  ERRO ao extrair texto: {e}")
            continue

        print("── Texto bruto OCR ──")
        for linha in texto.splitlines():
            print(f"  {linha}")

        print("\n── Campos extraídos ──")
        r = parsear_cartaz(texto)
        print(f"  nome:          {r['nome']}")
        print(f"  peso_volume:   {r['peso_volume']}")
        print(f"  preco_unit:    {r['preco_unitario']}")
        print(f"  preco_atac:    {r['preco_atacado']}")
        print(f"  qtd_min:       {r['qtd_min_atacado']}")
        if r.get("sem_desconto_atacado"):
            print("  ⚠  sem desconto no atacado (prices iguais)")

    print(f"\n{SEP}")
    print(f"Total: {len(fotos)} foto(s) processada(s).")
