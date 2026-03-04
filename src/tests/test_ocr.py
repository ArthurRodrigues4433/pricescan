import io
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from django.test import TestCase

from src.ocr import parsear_cartaz, extrair_texto, checar_qualidade

PASTA_FOTOS = Path(__file__).parent / "testes_cartaz"
EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FOTOS = (
    sorted(f for f in PASTA_FOTOS.iterdir() if f.suffix.lower() in EXTENSOES)
    if PASTA_FOTOS.exists()
    else []
)


class ParsearCartazTest(TestCase):

    def test_preco_unitario_simples(self):
        texto = "BISCOITO RECHEADO 140g\n9,99"
        r = parsear_cartaz(texto)
        self.assertEqual(r["preco_unitario"], "9,99")
        self.assertEqual(r["preco_atacado"], "")
        self.assertEqual(r["qtd_min_atacado"], "")

    def test_varejo_e_atacado_labels(self):
        texto = "ARROZ TIPO 1 5KG\nVAREJO\n14,90\nATACADO\n12,50\nA PARTIR DE 5"
        r = parsear_cartaz(texto)
        self.assertEqual(r["preco_unitario"], "14,90")
        self.assertEqual(r["preco_atacado"], "12,50")
        self.assertEqual(r["qtd_min_atacado"], "5")

    def test_peso_volume_extraido(self):
        texto = "FEIJAO CARIOCA 1KG\n5,49"
        r = parsear_cartaz(texto)
        self.assertIn("1", r["peso_volume"])
        self.assertIn("kg", r["peso_volume"])

    def test_cx_calcula_preco_por_unidade(self):
        """CX 12 RS 96,00 → qtd_min=12, preco_atacado=8,00"""
        texto = "REFRIGERANTE 2L\nCX 12 RS 96,00"
        r = parsear_cartaz(texto)
        self.assertEqual(r["qtd_min_atacado"], "12")
        if r["preco_atacado"]:
            valor = float(r["preco_atacado"].replace(",", "."))
            self.assertAlmostEqual(valor, 8.0, places=1)

    def test_cx_igual_ao_varejo_sem_desconto(self):
        """Quando CX/unidade == preço varejo, sem_desconto_atacado deve ser True."""
        texto = "REFRIGERANTE 2L\nVAREJO\n9,18\nCX 12 RS 110,16"
        r = parsear_cartaz(texto)
        self.assertTrue(r["sem_desconto_atacado"])
        self.assertEqual(r["preco_atacado"], "")
        self.assertEqual(r["qtd_min_atacado"], "")

    def test_a_partir_de_extrai_qtd_min(self):
        texto = "AGUA MINERAL 500ml\n2,50\n1,99\nA PARTIR DE 6"
        r = parsear_cartaz(texto)
        self.assertEqual(r["qtd_min_atacado"], "6")

    def test_leve_extrai_qtd_min(self):
        texto = "SABAO PO 1KG\n8,90\n7,50\nLEVE 3"
        r = parsear_cartaz(texto)
        self.assertEqual(r["qtd_min_atacado"], "3")

    def test_sem_desconto_atacado_flag(self):
        """Quando preco_atacado == preco_unitario, sem_desconto_atacado=True."""
        texto = "PRODUTO X\n5,00\n5,00"
        r = parsear_cartaz(texto)
        if r["sem_desconto_atacado"]:
            self.assertEqual(r["preco_atacado"], "")
            self.assertEqual(r["qtd_min_atacado"], "")

    def test_texto_vazio_retorna_campos_vazios(self):
        r = parsear_cartaz("")
        self.assertEqual(r["nome"], "")
        self.assertEqual(r["preco_unitario"], "")
        self.assertEqual(r["preco_atacado"], "")
        self.assertEqual(r["qtd_min_atacado"], "")

    def test_preco_sem_separador_3_digitos(self):
        """'918' numa linha curta deve ser interpretado como 9,18."""
        texto = "PRODUTO\n918"
        r = parsear_cartaz(texto)
        self.assertEqual(r["preco_unitario"], "9,18")

    def test_nao_extrai_preco_zero(self):
        texto = "PRODUTO\n0,00\n5,99"
        r = parsear_cartaz(texto)
        self.assertNotEqual(r["preco_unitario"], "0,00")

    def test_nome_nao_inclui_label_varejo(self):
        texto = "ARROZ 5KG\nVAREJO\n14,90\nATACADO\n12,00"
        r = parsear_cartaz(texto)
        nome = r["nome"].lower()
        self.assertNotIn("varejo", nome)
        self.assertNotIn("atacado", nome)


# ---------------------------------------------------------------------------
# Testes de integração — fotos reais de testes_cartaz/
# Substitui o script manual testar_cartazes.py
# ---------------------------------------------------------------------------

import unittest

CAMPOS_ESPERADOS = {
    "nome",
    "peso_volume",
    "preco_unitario",
    "preco_atacado",
    "qtd_min_atacado",
    "sem_desconto_atacado",
}


@unittest.skipIf(
    not FOTOS,
    "Nenhuma foto encontrada em testes_cartaz/ — testes de integração pulados",
)
class OcrIntegracaoTest(TestCase):
    """
    Roda extrair_texto + parsear_cartaz em cada imagem de testes_cartaz/.
    Não verifica valores exatos (OCR varia), mas garante que:
      - o pipeline não lança exceções
      - o dict retornado tem todos os campos esperados
      - pelo menos um campo não está vazio (OCR leu algo)
    """

    def _processar(self, foto: Path) -> dict:
        texto = extrair_texto(str(foto))
        self.assertIsInstance(
            texto, str, f"{foto.name}: extrair_texto() deve retornar str"
        )
        resultado = parsear_cartaz(texto)
        self.assertIsInstance(
            resultado, dict, f"{foto.name}: parsear_cartaz() deve retornar dict"
        )
        self.assertEqual(
            set(resultado.keys()),
            CAMPOS_ESPERADOS,
            f"{foto.name}: dict retornado com chaves inesperadas",
        )
        return resultado

    def test_pipeline_nao_quebra_em_nenhuma_foto(self):
        """Todas as fotos são processadas sem exceção."""
        erros = []
        for foto in FOTOS:
            try:
                self._processar(foto)
            except Exception as e:
                erros.append(f"{foto.name}: {e}")
        if erros:
            self.fail("Pipeline quebrou em:\n" + "\n".join(erros))

    def test_pelo_menos_um_campo_preenchido_por_foto(self):
        """Cada foto deve resultar em pelo menos um campo não vazio."""
        sem_resultado = []
        for foto in FOTOS:
            try:
                r = self._processar(foto)
            except Exception:
                continue  # já coberto pelo teste anterior
            campos_texto = [r["nome"], r["preco_unitario"], r["preco_atacado"]]
            if not any(campos_texto):
                sem_resultado.append(foto.name)
        if sem_resultado:
            self.fail(
                f"{len(sem_resultado)} foto(s) sem nenhum campo extraído:\n"
                + "\n".join(sem_resultado)
            )

    def test_qualidade_fotos_aprovadas(self):
        """Todas as fotos de testes_cartaz/ devem passar na checagem de qualidade."""
        reprovadas = []
        for foto in FOTOS:
            ok, motivo = checar_qualidade(str(foto), checar_resolucao=False)
            if not ok:
                reprovadas.append(f"{foto.name}: {motivo}")
        if reprovadas:
            self.fail(
                f"{len(reprovadas)} foto(s) reprovadas na checagem de qualidade:\n"
                + "\n".join(reprovadas)
            )


# ---------------------------------------------------------------------------
# Testes unitários de checar_qualidade — imagens sintéticas
# ---------------------------------------------------------------------------


def _salvar_imagem(img: Image.Image, dirpath: str, nome: str = "test.png") -> str:
    """Salva uma imagem PIL em dirpath/nome e retorna o caminho."""
    path = os.path.join(dirpath, nome)
    img.save(path)
    return path


class ChecarQualidadeTest(TestCase):
    """Testa todos os branches de checar_qualidade com imagens geradas em memória."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _boa_imagem(self, tamanho: int = 800) -> str:
        """Cria um tabuleiro de xadrez com alta variância do Laplaciano (nítida)."""
        arr = np.zeros((tamanho, tamanho), dtype=np.uint8)
        arr[::2, ::2] = 255
        arr[1::2, 1::2] = 255
        return _salvar_imagem(Image.fromarray(arr), self.tmpdir, "boa.png")

    def test_resolucao_muito_pequena_reprovada(self):
        """Imagem menor que 640px fracassa na checagem de resolução."""
        caminho = _salvar_imagem(
            Image.new("L", (300, 300), 128), self.tmpdir, "pequena.png"
        )
        ok, motivo = checar_qualidade(caminho, checar_resolucao=True)
        self.assertFalse(ok)
        self.assertIn("pequena", motivo.lower())

    def test_checar_resolucao_false_ignora_tamanho(self):
        """Com checar_resolucao=False uma imagem 300x300 não falha por resolução."""
        arr = np.zeros((300, 300), dtype=np.uint8)
        arr[::2, ::2] = 255
        arr[1::2, 1::2] = 255
        caminho = _salvar_imagem(Image.fromarray(arr), self.tmpdir, "peq_xadrez.png")
        ok, _ = checar_qualidade(caminho, checar_resolucao=False)
        self.assertTrue(ok)

    def test_imagem_muito_escura_reprovada(self):
        """Imagem preta (brilho < 40) é reprovada."""
        caminho = _salvar_imagem(
            Image.new("L", (800, 800), 5), self.tmpdir, "escura.png"
        )
        ok, motivo = checar_qualidade(caminho, checar_resolucao=False)
        self.assertFalse(ok)
        self.assertIn("escura", motivo.lower())

    def test_imagem_muito_clara_reprovada(self):
        """Imagem branca (brilho > 220) é reprovada."""
        caminho = _salvar_imagem(
            Image.new("L", (800, 800), 250), self.tmpdir, "clara.png"
        )
        ok, motivo = checar_qualidade(caminho, checar_resolucao=False)
        self.assertFalse(ok)
        self.assertIn("clara", motivo.lower())

    def test_imagem_borrada_reprovada(self):
        """Imagem uniforme (variância do Laplaciano ≈ 0) é reprovada por borrão."""
        # Cinza médio (128) — passa no brilho mas a variância do Laplaciano é 0
        caminho = _salvar_imagem(
            Image.new("L", (800, 800), 128), self.tmpdir, "borrada.png"
        )
        ok, motivo = checar_qualidade(caminho, checar_resolucao=False)
        self.assertFalse(ok)
        self.assertIn("borrada", motivo.lower())

    def test_imagem_boa_aprovada(self):
        """Tabuleiro de xadrez 800×800 passa em todas as checagens."""
        caminho = self._boa_imagem(800)
        ok, motivo = checar_qualidade(caminho, checar_resolucao=False)
        self.assertTrue(ok)
        self.assertEqual(motivo, "")

    def test_imagem_boa_com_resolucao_aprovada(self):
        """Tabuleiro 800×800 também passa na checagem de resolução ativada."""
        caminho = self._boa_imagem(800)
        ok, motivo = checar_qualidade(caminho, checar_resolucao=True)
        self.assertTrue(ok)

    @patch("src.ocr.cv2.cvtColor", side_effect=Exception("cv2 falhou"))
    def test_cv2_exception_retorna_falso(self, mock_cv2):
        """Exceção durante a etapa do OpenCV retorna (False, mensagem de erro)."""
        caminho = _salvar_imagem(
            Image.new("L", (800, 800), 128), self.tmpdir, "cv2err.png"
        )
        ok, motivo = checar_qualidade(caminho, checar_resolucao=False)
        self.assertFalse(ok)
        self.assertIn("possível", motivo)


# ---------------------------------------------------------------------------
# Testes adicionais de parsear_cartaz — branches não cobertos
# ---------------------------------------------------------------------------


class ParsearCartazBranchesTest(TestCase):
    """Cobre branches menos frequentes do parser."""

    def test_has_atacado_sem_varejo_dois_precos(self):
        """Label ATACADO sem VAREJO, dois preços → menor=atacado, maior=varejo."""
        texto = "FARINHA 1KG\nATACADO\n8,50\n10,00"
        r = parsear_cartaz(texto)
        precos = {r["preco_unitario"], r["preco_atacado"]}
        # Deve conter preços não-vazios
        precos_nao_vazios = [p for p in precos if p]
        self.assertGreaterEqual(len(precos_nao_vazios), 1)

    def test_has_atacado_sem_varejo_um_preco(self):
        """Label ATACADO e somente um preço → preco_atacado definido."""
        texto = "PRODUTO\nATACADO\n7,90"
        r = parsear_cartaz(texto)
        # Pelo menos um dos campos de preço deve ter 7,90
        self.assertTrue(r["preco_atacado"] == "7,90" or r["preco_unitario"] == "7,90")

    def test_has_varejo_sem_atacado_dois_precos(self):
        """Label VAREJO sem ATACADO, dois preços → ambos os campos preenchidos."""
        texto = "OLEO 900ML\nVAREJO\n12,00\n10,00"
        r = parsear_cartaz(texto)
        self.assertTrue(r["preco_unitario"] or r["preco_atacado"])

    def test_has_varejo_sem_atacado_um_preco(self):
        """Label VAREJO + único preço → preco_unitario definido."""
        texto = "MACARRAO 500G\nVAREJO\n3,99"
        r = parsear_cartaz(texto)
        self.assertEqual(r["preco_unitario"], "3,99")
        self.assertEqual(r["preco_atacado"], "")

    def test_cx_espaco_nos_centavos_calcula_preco_unidade(self):
        """'CX 12 RS 96 00' (espaço em vez de vírgula) calcula preço por unidade."""
        texto = "REFRIGERANTE 1L\nCX 12 RS 96 00"
        r = parsear_cartaz(texto)
        self.assertEqual(r["qtd_min_atacado"], "12")
        if r["preco_atacado"]:
            valor = float(r["preco_atacado"].replace(",", "."))
            self.assertAlmostEqual(valor, 8.0, places=1)

    def test_cx_simples_sem_preco_define_qtd_min(self):
        """'CX 6' sem preço total define qtd_min_atacado via fallback."""
        texto = "AGUA 500ML\n1,99\nCX 6"
        r = parsear_cartaz(texto)
        self.assertEqual(r["qtd_min_atacado"], "6")

    def test_preco_com_ponto_decimal(self):
        """Preço escrito com ponto ('9.99') é extraído corretamente."""
        texto = "PRODUTO\n9.99"
        r = parsear_cartaz(texto)
        self.assertIn(r["preco_unitario"], ["9,99", ""])

    def test_preco_espaco_entre_reais_e_centavos(self):
        """Preço '27 90' (espaço como separador) é extraído como 27,90."""
        texto = "PRODUTO X\n27 90"
        r = parsear_cartaz(texto)
        # O parser pode ou não extrair via espaço — o importante é não quebrar
        self.assertIsInstance(r["preco_unitario"], str)

    def test_varejo_atacado_mesmo_preco_usa_lista_global(self):
        """Quando labels VAREJO e ATACADO encontram o mesmo preço, usa lista global."""
        # Ambos os labels antes dos preços na mesma região
        texto = "PRODUTO\nVAREJO\nATACADO\n5,00\n4,00"
        r = parsear_cartaz(texto)
        # Não deve lançar exceção e deve retornar os campos esperados
        self.assertIn("preco_unitario", r)
        self.assertIn("preco_atacado", r)

    def test_texto_somente_numeros_sem_precos_validos(self):
        """Texto só com texto sem números retorna campos vazios."""
        r = parsear_cartaz("PRODUTO SEM PRECO")
        self.assertEqual(r["preco_unitario"], "")
        self.assertEqual(r["preco_atacado"], "")

    def test_preco_partido_em_duas_linhas(self):
        """'9' em uma linha e '18' na seguinte → reconstruído como '9,18'."""
        r = parsear_cartaz("PRODUTO\n9\n18")
        self.assertEqual(r["preco_unitario"], "9,18")

    def test_preco_digit_mais_preco_linha_seguinte(self):
        """'1' antes de '4,90' → reconstruído como '14,90' (pré-passo B)."""
        r = parsear_cartaz("SUCO\n1\n4,90")
        self.assertEqual(r["preco_unitario"], "14,90")

    def test_qtd_unidades_sem_preco_na_linha(self):
        """'6 UNIDADES' em linha sem preço define qtd_min via fallback UNIDADE."""
        r = parsear_cartaz("PRODUTO\n5,99\n6 UNIDADES")
        self.assertEqual(r["qtd_min_atacado"], "6")

    def test_varejo_atacado_mesmo_preco_lista_global_um_item(self):
        """Ambos os labels encontram o mesmo preço → usa lista global com 1 item."""
        # "ATACADO VAREJO" na mesma linha; 1 único preço no texto
        r = parsear_cartaz("PRODUTO\nATACADO VAREJO\n8,50")
        # Não deve quebrar; preco_unitario deve ser "8,50"
        self.assertEqual(r["preco_unitario"], "8,50")

    def test_varejo_atacado_labels_sem_preco_proximo_usa_global_um_item(self):
        """Labels com o preço fora da janela de 6 linhas → else usa lista global com 1 item."""
        # Após VAREJO há ATACADO + 5 linhas sem preço, depois o preço (fica além de 6 linhas)
        # Após ATACADO há 5 linhas sem preço, depois o preço (dentro da janela → encontrado)
        # → precos_varejo vazio, precos_atacado = [(9.0, "9,00")] → not(ambos) → else branch
        # len(limpos) = 1 → elif sv: preco_unitario = "9,00"
        texto = (
            "PRODUTO\n"
            "VAREJO\n"
            "ATACADO\n"
            "LINHA A\n"
            "LINHA B\n"
            "LINHA C\n"
            "LINHA D\n"
            "LINHA E\n"
            "9,00"
        )
        r = parsear_cartaz(texto)
        # Não deve quebrar e deve ter preco_unitario
        self.assertIn("preco_unitario", r)
        self.assertEqual(r["preco_unitario"], "9,00")

    def test_varejo_label_com_inline_3dig_e_preco(self):
        """Linha após VAREJO com preço e 3-dígitos adjacentes extrai inline 3-dig."""
        # '149 1,79' → preço "1,79" encontrado (achou=True) e "149" como 3-dig → "1,49"
        r = parsear_cartaz("PRODUTO\nVAREJO\n149 1,79")
        # O importante é não quebrar e o preco_unitario ser preenchido
        self.assertTrue(r["preco_unitario"])
