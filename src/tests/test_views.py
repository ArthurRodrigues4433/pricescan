import io
import os
import shutil
import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from src.models import Compra, ItemCompra


def _fake_png() -> SimpleUploadedFile:
    """Cria um PNG 2×2 pixels em memória para usar como upload de foto."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color=(100, 100, 100)).save(buf, format="PNG")
    return SimpleUploadedFile("cartaz.png", buf.getvalue(), content_type="image/png")


_DADOS_OCR_OK = {
    "nome": "ARROZ",
    "peso_volume": "5kg",
    "preco_unitario": "5,99",
    "preco_atacado": "",
    "qtd_min_atacado": "",
    "sem_desconto_atacado": False,
}


class AuthRedirectTest(TestCase):
    """Rotas protegidas redirecionam para login quando não autenticado."""

    def test_painel_sem_login_redireciona(self):
        resp = self.client.get(reverse("src:painel_compras"))
        self.assertRedirects(
            resp, "/accounts/login/?next=/", fetch_redirect_response=False
        )

    def test_lista_compra_sem_login_redireciona(self):
        resp = self.client.get(reverse("src:lista_compra", args=[999]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])


class PainelComprasViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)

    def test_painel_exibe_feiras_do_usuario(self):
        Compra.objects.create(usuario=self.user, status="ativa")
        outro = User.objects.create_user(username="b@b.com", password="pass1234")
        Compra.objects.create(usuario=outro, status="ativa")

        resp = self.client.get(reverse("src:painel_compras"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["compras"].count(), 1)

    def test_painel_template_correto(self):
        resp = self.client.get(reverse("src:painel_compras"))
        self.assertTemplateUsed(resp, "painel_compras.html")


class CriarCompraViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)

    def test_criar_compra_post_cria_e_redireciona(self):
        resp = self.client.post(reverse("src:criar_compra"))
        self.assertEqual(Compra.objects.filter(usuario=self.user).count(), 1)
        compra = Compra.objects.get(usuario=self.user)
        self.assertRedirects(
            resp,
            reverse("src:lista_compra", args=[compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_criar_compra_get_retorna_405(self):
        resp = self.client.get(reverse("src:criar_compra"))
        self.assertEqual(resp.status_code, 405)

    def test_compra_criada_com_status_ativa(self):
        self.client.post(reverse("src:criar_compra"))
        self.assertEqual(Compra.objects.get(usuario=self.user).status, "ativa")

    def test_criar_compra_com_nome(self):
        self.client.post(reverse("src:criar_compra"), {"nome": "Feira de Janeiro"})
        compra = Compra.objects.get(usuario=self.user)
        self.assertEqual(compra.nome, "Feira de Janeiro")

    def test_criar_compra_com_orcamento(self):
        self.client.post(reverse("src:criar_compra"), {"orcamento": "300,00"})
        compra = Compra.objects.get(usuario=self.user)
        self.assertEqual(compra.orcamento, Decimal("300.00"))

    def test_criar_compra_orcamento_invalido_salva_none(self):
        """Orçamento não numérico deve ser ignorado (None) sem crash."""
        self.client.post(reverse("src:criar_compra"), {"orcamento": "abc"})
        compra = Compra.objects.get(usuario=self.user)
        self.assertIsNone(compra.orcamento)

    def test_criar_compra_orcamento_negativo_salva_none(self):
        """Orçamento <= 0 deve ser ignorado."""
        self.client.post(reverse("src:criar_compra"), {"orcamento": "-50"})
        compra = Compra.objects.get(usuario=self.user)
        self.assertIsNone(compra.orcamento)

    def test_bloqueia_criacao_quando_ja_existe_ativa(self):
        """Não pode criar nova feira se já existe uma ativa."""
        Compra.objects.create(usuario=self.user, status="ativa")
        self.client.post(reverse("src:criar_compra"))
        # Deve continuar com apenas 1 feira
        self.assertEqual(Compra.objects.filter(usuario=self.user).count(), 1)

    def test_bloqueia_criacao_redireciona_para_painel(self):
        """Ao bloquear, redireciona para o painel com mensagem de erro."""
        Compra.objects.create(usuario=self.user, status="ativa")
        resp = self.client.post(reverse("src:criar_compra"))
        self.assertRedirects(
            resp, reverse("src:painel_compras"), fetch_redirect_response=False
        )


class ListaCompraViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="ativa")

    def test_lista_compra_status_200(self):
        resp = self.client.get(reverse("src:lista_compra", args=[self.compra.id]))  # type: ignore
        self.assertEqual(resp.status_code, 200)

    def test_lista_compra_404_outro_usuario(self):
        outro = User.objects.create_user(username="b@b.com", password="pass1234")
        compra_outro = Compra.objects.create(usuario=outro, status="ativa")
        resp = self.client.get(reverse("src:lista_compra", args=[compra_outro.id]))  # type: ignore
        self.assertEqual(resp.status_code, 404)

    def test_lista_exibe_total_geral(self):
        ItemCompra.objects.create(
            compra=self.compra,
            nome="Arroz",
            preco_unitario=Decimal("5.00"),
            quantidade=Decimal("2"),
        )
        resp = self.client.get(reverse("src:lista_compra", args=[self.compra.id]))  # type: ignore
        self.assertContains(resp, "10")

    def test_orcamento_info_none_quando_sem_orcamento(self):
        """Sem orçamento definido, context['orcamento_info'] deve ser None."""
        resp = self.client.get(reverse("src:lista_compra", args=[self.compra.id]))  # type: ignore
        self.assertIsNone(resp.context["orcamento_info"])  # type: ignore

    def test_orcamento_info_presente_quando_com_orcamento(self):
        """Com orçamento definido, orcamento_info deve conter as chaves esperadas."""
        self.compra.orcamento = Decimal("100.00")
        self.compra.save()
        resp = self.client.get(reverse("src:lista_compra", args=[self.compra.id]))  # type: ignore
        info = resp.context["orcamento_info"]  # type: ignore
        self.assertIsNotNone(info)
        for chave in (
            "valor",
            "percentual",
            "percentual_capped",
            "restante",
            "excedido",
            "alerta",
        ):
            self.assertIn(chave, info)

    def test_orcamento_info_alerta_quando_perto_do_limite(self):
        """Quando total >= 85% do orçamento (mas não excede), alerta deve ser True."""
        self.compra.orcamento = Decimal("100.00")
        self.compra.save()
        # Adiciona item que representa 90% do orçamento
        ItemCompra.objects.create(
            compra=self.compra,
            nome="Item",
            preco_unitario=Decimal("90.00"),
            quantidade=Decimal("1"),
        )
        resp = self.client.get(reverse("src:lista_compra", args=[self.compra.id]))  # type: ignore
        info = resp.context["orcamento_info"]  # type: ignore
        self.assertTrue(info["alerta"])
        self.assertFalse(info["excedido"])

    def test_orcamento_info_excedido_quando_total_maior(self):
        """Quando total > orçamento, excedido deve ser True e alerta False."""
        self.compra.orcamento = Decimal("50.00")
        self.compra.save()
        ItemCompra.objects.create(
            compra=self.compra,
            nome="Item caro",
            preco_unitario=Decimal("60.00"),
            quantidade=Decimal("1"),
        )
        resp = self.client.get(reverse("src:lista_compra", args=[self.compra.id]))  # type: ignore
        info = resp.context["orcamento_info"]  # type: ignore
        self.assertTrue(info["excedido"])
        self.assertFalse(info["alerta"])

    def test_orcamento_percentual_capped_em_100(self):
        """percentual_capped não deve ultrapassar 100 mesmo quando total > orçamento."""
        self.compra.orcamento = Decimal("50.00")
        self.compra.save()
        ItemCompra.objects.create(
            compra=self.compra,
            nome="Caro",
            preco_unitario=Decimal("200.00"),
            quantidade=Decimal("1"),
        )
        resp = self.client.get(reverse("src:lista_compra", args=[self.compra.id]))  # type: ignore
        info = resp.context["orcamento_info"]  # type: ignore
        self.assertLessEqual(info["percentual_capped"], 100)


class RemoverItemViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="ativa")
        self.item = ItemCompra.objects.create(
            compra=self.compra,
            nome="Feijão",
            preco_unitario=Decimal("4.00"),
            quantidade=Decimal("1"),
        )

    def test_remover_item_post_remove(self):
        resp = self.client.post(
            reverse("src:remover_item", args=[self.compra.id, self.item.id])  # type: ignore
        )
        self.assertFalse(ItemCompra.objects.filter(id=self.item.id).exists())  # type: ignore
        self.assertRedirects(
            resp,
            reverse("src:lista_compra", args=[self.compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_remover_item_get_retorna_405(self):
        resp = self.client.get(
            reverse("src:remover_item", args=[self.compra.id, self.item.id])  # type: ignore
        )
        self.assertEqual(resp.status_code, 405)

    def test_nao_remove_item_de_compra_finalizada(self):
        self.compra.status = "finalizada"
        self.compra.save()
        resp = self.client.post(
            reverse("src:remover_item", args=[self.compra.id, self.item.id])  # type: ignore
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(ItemCompra.objects.filter(id=self.item.id).exists())  # type: ignore


class FinalizarCompraViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="ativa")

    def test_finalizar_muda_status(self):
        self.client.post(reverse("src:finalizar_compra", args=[self.compra.id]))  # type: ignore
        self.compra.refresh_from_db()
        self.assertEqual(self.compra.status, "finalizada")

    def test_finalizar_redireciona_para_painel(self):
        resp = self.client.post(reverse("src:finalizar_compra", args=[self.compra.id]))  # type: ignore
        self.assertRedirects(
            resp, reverse("src:painel_compras"), fetch_redirect_response=False
        )

    def test_finalizar_get_retorna_405(self):
        resp = self.client.get(reverse("src:finalizar_compra", args=[self.compra.id]))  # type: ignore
        self.assertEqual(resp.status_code, 405)


class ExcluirCompraViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="finalizada")

    def test_excluir_compra_finalizada(self):
        resp = self.client.post(reverse("src:excluir_compra", args=[self.compra.id]))  # type: ignore
        self.assertFalse(Compra.objects.filter(id=self.compra.id).exists())  # type: ignore
        self.assertRedirects(
            resp, reverse("src:painel_compras"), fetch_redirect_response=False
        )

    def test_nao_excluir_compra_ativa(self):
        compra_ativa = Compra.objects.create(usuario=self.user, status="ativa")
        resp = self.client.post(reverse("src:excluir_compra", args=[compra_ativa.id]))  # type: ignore
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Compra.objects.filter(id=compra_ativa.id).exists())  # type: ignore


class RegisterViewTest(TestCase):
    def test_get_exibe_formulario(self):
        resp = self.client.get(reverse("src:register"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "registration/register.html")

    def test_post_valido_cria_usuario(self):
        resp = self.client.post(
            reverse("src:register"),
            {
                "email": "novo@teste.com",
                "password1": "SenhaSegura123!",
                "password2": "SenhaSegura123!",
            },
        )
        self.assertTrue(User.objects.filter(username="novo@teste.com").exists())
        self.assertRedirects(resp, reverse("login"), fetch_redirect_response=False)

    def test_post_email_duplicado_nao_cria(self):
        User.objects.create_user(username="dup@t.com", email="dup@t.com", password="X")
        self.client.post(
            reverse("src:register"),
            {
                "email": "dup@t.com",
                "password1": "SenhaSegura123!",
                "password2": "SenhaSegura123!",
            },
        )
        self.assertEqual(User.objects.filter(username="dup@t.com").count(), 1)

    def test_redirect_se_ja_autenticado(self):
        user = User.objects.create_user(username="x@x.com", password="pass1234")
        self.client.force_login(user)
        resp = self.client.get(reverse("src:register"))
        self.assertRedirects(
            resp, reverse("src:painel_compras"), fetch_redirect_response=False
        )


class AdicionarProdutoViewTest(TestCase):
    """Adicionar produto redireciona para o scanner OCR."""

    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="ativa")

    def test_redireciona_para_scanner(self):
        resp = self.client.get(reverse("src:adicionar_produto", args=[self.compra.id]))  # type: ignore
        self.assertRedirects(
            resp,
            reverse("src:escanear_cartaz", args=[self.compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_404_compra_finalizada(self):
        self.compra.status = "finalizada"
        self.compra.save()
        resp = self.client.get(reverse("src:adicionar_produto", args=[self.compra.id]))  # type: ignore
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Views do fluxo OCR
# ---------------------------------------------------------------------------


class EscanearCartazViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="ativa")
        self.url = reverse("src:escanear_cartaz", args=[self.compra.id])  # type: ignore
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_retorna_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "escanear_cartaz.html")

    def test_get_compra_finalizada_retorna_404(self):
        self.compra.status = "finalizada"
        self.compra.save()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_post_sem_foto_rerenderiza_formulario(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "escanear_cartaz.html")

    @patch(
        "src.views.ocr_module.checar_qualidade",
        return_value=(False, "Foto muito escura."),
    )
    def test_post_qualidade_ruim_mostra_mensagem_de_erro(self, _mock_qual):
        with patch("src.views._TMP_DIR", self.tmpdir):
            resp = self.client.post(self.url, {"foto": _fake_png()})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "escanear_cartaz.html")
        mensagens = [str(m) for m in resp.wsgi_request._messages]  # type: ignore
        self.assertTrue(any("escura" in m for m in mensagens))

    @patch("src.views.ocr_module.checar_qualidade", return_value=(True, ""))
    @patch(
        "src.views.ocr_module.extrair_texto", side_effect=Exception("Tesseract ausente")
    )
    def test_post_ocr_exception_mostra_mensagem_de_erro(self, _mock_ocr, _mock_qual):
        with patch("src.views._TMP_DIR", self.tmpdir):
            resp = self.client.post(self.url, {"foto": _fake_png()})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "escanear_cartaz.html")
        mensagens = [str(m) for m in resp.wsgi_request._messages]  # type: ignore
        self.assertTrue(any("OCR" in m for m in mensagens))

    @patch("src.views.ocr_module.checar_qualidade", return_value=(True, ""))
    @patch("src.views.ocr_module.extrair_texto", return_value="ARROZ 5KG\n5,99")
    @patch("src.views.ocr_module.parsear_cartaz")
    def test_post_sucesso_renderiza_confirmar_produto(
        self, mock_parse, _mock_ocr, _mock_qual
    ):
        mock_parse.return_value = dict(_DADOS_OCR_OK)
        with patch("src.views._TMP_DIR", self.tmpdir):
            resp = self.client.post(self.url, {"foto": _fake_png()})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "confirmar_produto.html")


class ConfirmarProdutoViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="ativa")
        self.url = reverse("src:confirmar_produto", args=[self.compra.id])  # type: ignore

    def test_get_redireciona_para_escanear(self):
        resp = self.client.get(self.url)
        self.assertRedirects(
            resp,
            reverse("src:escanear_cartaz", args=[self.compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_post_invalido_rerenderiza_confirmar_produto(self):
        # Sem 'nome' e sem 'preco_unitario' → formulário inválido
        resp = self.client.post(self.url, {"caminho_tmp": "", "foto_url": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "confirmar_produto.html")

    def test_post_valido_renderiza_informar_quantidade(self):
        resp = self.client.post(
            self.url,
            {
                "nome": "Arroz",
                "preco_unitario": "5.99",
                "caminho_tmp": "",
                "foto_url": "",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "informar_quantidade.html")
        self.assertEqual(resp.context["nome"], "Arroz")  # type: ignore


class InformarQuantidadeViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="ativa")
        self.url = reverse("src:informar_quantidade", args=[self.compra.id])  # type: ignore

    def test_get_redireciona_para_escanear(self):
        resp = self.client.get(self.url)
        self.assertRedirects(
            resp,
            reverse("src:escanear_cartaz", args=[self.compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_post_sem_quantidade_rerenderiza(self):
        resp = self.client.post(
            self.url,
            {
                "nome": "Arroz",
                "preco_unitario": "5.99",
                "caminho_tmp": "",
                "foto_url": "",
                # quantidade ausente
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "informar_quantidade.html")

    def test_post_sem_preco_unitario_rerenderiza(self):
        resp = self.client.post(
            self.url,
            {
                "nome": "Arroz",
                "preco_unitario": "",
                "quantidade": "2",
                "caminho_tmp": "",
                "foto_url": "",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "informar_quantidade.html")

    def test_post_valido_sem_foto_cria_item_e_redireciona(self):
        resp = self.client.post(
            self.url,
            {
                "nome": "Feijao",
                "preco_unitario": "4.50",
                "quantidade": "3",
                "caminho_tmp": "",
                "foto_url": "",
            },
        )
        self.assertEqual(ItemCompra.objects.filter(compra=self.compra).count(), 1)
        item = ItemCompra.objects.get(compra=self.compra)
        self.assertEqual(item.nome, "Feijao")
        self.assertRedirects(
            resp,
            reverse("src:lista_compra", args=[self.compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_post_com_preco_atacado_e_qtd_min(self):
        """Salva item com preco_atacado e qtd_min_atacado corretamente."""
        resp = self.client.post(
            self.url,
            {
                "nome": "Oleo",
                "preco_unitario": "8.00",
                "preco_atacado": "6.50",
                "qtd_min_atacado": "6",
                "quantidade": "2",
                "caminho_tmp": "",
                "foto_url": "",
            },
        )
        item = ItemCompra.objects.get(compra=self.compra)
        self.assertEqual(item.preco_atacado, Decimal("6.50"))
        self.assertEqual(item.qtd_min_atacado, 6)

    def test_post_com_foto_tmp_salva_e_remove_arquivo(self):
        """Quando caminho_tmp existe, o arquivo é anexado ao item e o tmp é removido."""
        from django.test import override_settings

        media_tmpdir = tempfile.mkdtemp()
        try:
            # Cria arquivo temporário que simula o cartaz escaneado
            foto_tmpdir = tempfile.mkdtemp()
            caminho_tmp = os.path.join(foto_tmpdir, "cartaz.png")
            # grava um PNG mínimo
            from PIL import Image as PILImage

            PILImage.new("RGB", (2, 2)).save(caminho_tmp)

            with override_settings(MEDIA_ROOT=media_tmpdir):
                resp = self.client.post(
                    self.url,
                    {
                        "nome": "Biscoito",
                        "preco_unitario": "3.50",
                        "quantidade": "1",
                        "caminho_tmp": caminho_tmp,
                        "foto_url": f"/media/tmp/cartaz.png",
                    },
                )

            self.assertEqual(ItemCompra.objects.filter(compra=self.compra).count(), 1)
            self.assertRedirects(
                resp,
                reverse("src:lista_compra", args=[self.compra.id]),  # type: ignore
                fetch_redirect_response=False,
            )
            # Arquivo temporário deve ter sido apagado
            self.assertFalse(os.path.exists(caminho_tmp))
        finally:
            shutil.rmtree(media_tmpdir, ignore_errors=True)
            shutil.rmtree(foto_tmpdir, ignore_errors=True)

    def test_nao_excede_orcamento_salva_normalmente(self):
        """Item dentro do orçamento é salvo sem nenhum bloqueio."""
        self.compra.orcamento = Decimal("200.00")
        self.compra.save()
        resp = self.client.post(
            self.url,
            {
                "nome": "Arroz",
                "preco_unitario": "10.00",
                "quantidade": "3",
                "caminho_tmp": "",
                "foto_url": "",
                "confirmar_excesso": "0",
            },
        )
        self.assertEqual(ItemCompra.objects.filter(compra=self.compra).count(), 1)
        self.assertRedirects(
            resp,
            reverse("src:lista_compra", args=[self.compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_excede_orcamento_rerenderiza_com_flag(self):
        """Item que extrapola orçamento deve rerenderizar informar_quantidade com excedeu_orcamento=True."""
        self.compra.orcamento = Decimal("20.00")
        self.compra.save()
        resp = self.client.post(
            self.url,
            {
                "nome": "Produto caro",
                "preco_unitario": "30.00",
                "quantidade": "1",
                "caminho_tmp": "",
                "foto_url": "",
                "confirmar_excesso": "0",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "informar_quantidade.html")
        self.assertTrue(resp.context["excedeu_orcamento"])  # type: ignore
        # Item NÃO deve ter sido criado
        self.assertEqual(ItemCompra.objects.filter(compra=self.compra).count(), 0)

    def test_excede_orcamento_context_tem_valores_corretos(self):
        """O contexto retornado ao exceder orçamento deve conter excesso, item_total e total_novo."""
        self.compra.orcamento = Decimal("25.00")
        self.compra.save()
        resp = self.client.post(
            self.url,
            {
                "nome": "Caro",
                "preco_unitario": "30.00",
                "quantidade": "1",
                "caminho_tmp": "",
                "foto_url": "",
                "confirmar_excesso": "0",
            },
        )
        self.assertIn("excesso", resp.context)  # type: ignore
        self.assertIn("item_total", resp.context)  # type: ignore
        self.assertIn("total_novo", resp.context)  # type: ignore
        self.assertIn("orcamento", resp.context)  # type: ignore

    def test_confirmar_excesso_salva_mesmo_ultrapassando_orcamento(self):
        """Com confirmar_excesso=1 o item é salvo mesmo excedendo o orçamento."""
        self.compra.orcamento = Decimal("10.00")
        self.compra.save()
        resp = self.client.post(
            self.url,
            {
                "nome": "Muito caro",
                "preco_unitario": "50.00",
                "quantidade": "1",
                "caminho_tmp": "",
                "foto_url": "",
                "confirmar_excesso": "1",
            },
        )
        self.assertEqual(ItemCompra.objects.filter(compra=self.compra).count(), 1)
        self.assertRedirects(
            resp,
            reverse("src:lista_compra", args=[self.compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_sem_orcamento_nao_bloqueia_item(self):
        """Sem orçamento definido, qualquer item é salvo sem verificação de orçamento."""
        # compra sem orcamento (None por padrão)
        resp = self.client.post(
            self.url,
            {
                "nome": "Qualquer",
                "preco_unitario": "999.00",
                "quantidade": "10",
                "caminho_tmp": "",
                "foto_url": "",
            },
        )
        self.assertEqual(ItemCompra.objects.filter(compra=self.compra).count(), 1)
        self.assertRedirects(
            resp,
            reverse("src:lista_compra", args=[self.compra.id]),  # type: ignore
            fetch_redirect_response=False,
        )

    def test_post_com_foto_tmp_silencia_erro_ao_remover(self):
        """Se os.remove lançar OSError o except silencia o erro e a view redireciona."""
        from django.test import override_settings

        media_tmpdir = tempfile.mkdtemp()
        try:
            foto_tmpdir = tempfile.mkdtemp()
            caminho_tmp = os.path.join(foto_tmpdir, "cartaz2.png")
            from PIL import Image as PILImage

            PILImage.new("RGB", (2, 2)).save(caminho_tmp)

            with override_settings(MEDIA_ROOT=media_tmpdir):
                with patch(
                    "src.views.os.remove", side_effect=OSError("permissão negada")
                ):
                    resp = self.client.post(
                        self.url,
                        {
                            "nome": "Macarrao",
                            "preco_unitario": "2.00",
                            "quantidade": "1",
                            "caminho_tmp": caminho_tmp,
                            "foto_url": "",
                        },
                    )

            # Mesmo com erro em os.remove, a view deve redirecionar normalmente
            self.assertRedirects(
                resp,
                reverse("src:lista_compra", args=[self.compra.id]),  # type: ignore
                fetch_redirect_response=False,
            )
        finally:
            shutil.rmtree(media_tmpdir, ignore_errors=True)
            shutil.rmtree(foto_tmpdir, ignore_errors=True)


class ExcluirCompraGetTest(TestCase):
    """Garante que GET em excluir_compra retorna 405."""

    def setUp(self):
        self.user = User.objects.create_user(username="a@a.com", password="pass1234")
        self.client.force_login(self.user)
        self.compra = Compra.objects.create(usuario=self.user, status="finalizada")

    def test_get_retorna_405(self):
        resp = self.client.get(
            reverse("src:excluir_compra", args=[self.compra.id])  # type: ignore
        )
        self.assertEqual(resp.status_code, 405)
