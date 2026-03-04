import os
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import (
    UserCreationForm,
)  # noqa: F401 (mantido por compatibilidade)
from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from .forms import (
    ItemCompraForm,
    RegisterForm,
    EscanearCartazForm,
    ConfirmarProdutoForm,
    InformarQuantidadeForm,
)
from .models import Compra, ItemCompra
from . import ocr as ocr_module


def register(request):
    if request.user.is_authenticated:
        return redirect("src:painel_compras")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Conta criada com sucesso! Faça login para continuar."
            )
            return redirect("login")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def painel_compras(request):
    from django.db.models import Count

    base_qs = Compra.objects.filter(usuario=request.user)

    compras = base_qs.annotate(num_itens=Count("itens")).order_by("-data")

    total_feiras = base_qs.count()
    feiras_ativas = base_qs.filter(status="ativa").count()
    total_em_aberto = sum(c.total() for c in compras if c.status == "ativa")

    return render(
        request,
        "painel_compras.html",
        {
            "compras": compras,
            "total_feiras": total_feiras,
            "feiras_ativas": feiras_ativas,
            "total_em_aberto": total_em_aberto,
        },
    )


@login_required
def criar_compra(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    # Impede criar nova feira enquanto houver uma ativa
    if Compra.objects.filter(usuario=request.user, status="ativa").exists():
        messages.error(request, "Finalize a feira ativa antes de criar uma nova.")
        return redirect("src:painel_compras")
    nome = request.POST.get("nome", "").strip()
    orcamento_str = request.POST.get("orcamento", "").strip()
    orcamento = None
    if orcamento_str:
        try:
            orcamento = Decimal(orcamento_str.replace(",", "."))
            if orcamento <= 0:
                orcamento = None
        except (InvalidOperation, TypeError):
            orcamento = None
    nova_compra = Compra.objects.create(
        usuario=request.user, status="ativa", nome=nome, orcamento=orcamento
    )
    return redirect("src:lista_compra", compra_id=nova_compra.id)  # type: ignore


@login_required
def adicionar_produto(request, compra_id):
    # O fluxo de adição agora é 100% via OCR — redireciona direto para o scanner
    get_object_or_404(Compra, id=compra_id, usuario=request.user, status="ativa")
    return redirect("src:escanear_cartaz", compra_id=compra_id)


@login_required
def lista_compra(request, compra_id):
    compra = get_object_or_404(Compra, id=compra_id, usuario=request.user)
    itens = compra.itens.all()  # type: ignore
    total_geral = compra.total()

    # Resumo para o painel expandido do rodapé mobile
    qtd_com_desc = 0
    total_com_desc = Decimal("0")
    qtd_sem_desc = 0
    total_sem_desc = Decimal("0")
    for item in itens:
        subtotal = item.preco_total()
        # atacado = tem preco_atacado, qtd_min configurados E quantidade atinge o mínimo
        if (
            item.preco_atacado
            and item.qtd_min_atacado
            and item.quantidade >= item.qtd_min_atacado
        ):
            qtd_com_desc += 1
            total_com_desc += subtotal
        else:
            qtd_sem_desc += 1
            total_sem_desc += subtotal
    resumo_itens = {
        "com_desconto": {"qtd": qtd_com_desc, "total": total_com_desc},
        "sem_desconto": {"qtd": qtd_sem_desc, "total": total_sem_desc},
    }

    orcamento_info = None
    if compra.orcamento:
        percentual = float(total_geral / compra.orcamento * 100)
        restante = compra.orcamento - total_geral
        orcamento_info = {
            "valor": compra.orcamento,
            "percentual": round(percentual, 1),
            "percentual_capped": min(round(percentual, 1), 100),
            "restante": restante,
            "excedido": total_geral > compra.orcamento,
            "alerta": percentual >= 85 and total_geral <= compra.orcamento,
        }

    return render(
        request,
        "lista_compra.html",
        {
            "compra": compra,
            "itens": itens,
            "total_geral": total_geral,
            "orcamento_info": orcamento_info,
            "resumo_itens": resumo_itens,
        },
    )


@login_required
def remover_item(request, compra_id, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )
    item = get_object_or_404(ItemCompra, id=item_id, compra=compra)
    item.delete()
    return redirect("src:lista_compra", compra_id=compra_id)


@login_required
def editar_quantidade(request, compra_id, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    compra = get_object_or_404(Compra, id=compra_id, usuario=request.user, status="ativa")
    item = get_object_or_404(ItemCompra, id=item_id, compra=compra)
    try:
        nova_qtd = Decimal(str(request.POST.get("nova_quantidade", "")).replace(",", "."))
        if nova_qtd <= 0:
            raise ValueError
    except (ValueError, InvalidOperation):
        return redirect("src:lista_compra", compra_id=compra_id)
    item.quantidade = nova_qtd
    item.save(update_fields=["quantidade"])
    return redirect("src:lista_compra", compra_id=compra_id)


@login_required
def finalizar_compra(request, compra_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )
    compra.status = "finalizada"
    compra.save(update_fields=["status"])
    return redirect("src:painel_compras")


# ---------------------------------------------------------------------------
# Views do módulo OCR
# ---------------------------------------------------------------------------

_TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "media", "tmp")


@login_required
def escanear_cartaz(request, compra_id):
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )

    if request.method == "POST":
        form = EscanearCartazForm(request.POST, request.FILES)
        if form.is_valid():
            foto = request.FILES["foto"]

            # Salva temporariamente
            os.makedirs(_TMP_DIR, exist_ok=True)
            nome_tmp = f"tmp_{request.user.id}_{compra_id}_{foto.name}"
            caminho_tmp = os.path.join(_TMP_DIR, nome_tmp)
            with open(caminho_tmp, "wb") as f:
                for chunk in foto.chunks():
                    f.write(chunk)

            # Checagem de qualidade
            from_arquivo = request.POST.get("fonte") == "arquivo"
            ok, motivo = ocr_module.checar_qualidade(
                caminho_tmp, checar_resolucao=not from_arquivo
            )
            if not ok:
                os.remove(caminho_tmp)
                messages.error(request, motivo)
                return render(
                    request,
                    "escanear_cartaz.html",
                    {"form": EscanearCartazForm(), "compra": compra},
                )

            # OCR + parser
            try:
                texto = ocr_module.extrair_texto(caminho_tmp)
            except Exception as e:
                os.remove(caminho_tmp)
                messages.error(
                    request,
                    f"Erro no OCR: {e}. Verifique se o Tesseract está instalado em C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
                )
                return render(
                    request,
                    "escanear_cartaz.html",
                    {"form": EscanearCartazForm(), "compra": compra},
                )

            dados = ocr_module.parsear_cartaz(texto)
            dados["caminho_tmp"] = caminho_tmp

            def _br_to_decimal(s: str) -> str | None:
                """Converte 'R$ 9,18' / '9,18' → '9.18' para DecimalField do Django."""
                if not s:
                    return None
                return s.replace(".", "").replace(",", ".")

            confirm_form = ConfirmarProdutoForm(
                initial={
                    "nome": dados["nome"],
                    "peso_volume": dados["peso_volume"],
                    "preco_unitario": _br_to_decimal(dados["preco_unitario"]),
                    "preco_atacado": _br_to_decimal(dados["preco_atacado"]),
                    "qtd_min_atacado": dados["qtd_min_atacado"] or None,
                }
            )

            return render(
                request,
                "confirmar_produto.html",
                {
                    "form": confirm_form,
                    "compra": compra,
                    "caminho_tmp": caminho_tmp,
                    "foto_url": f"/media/tmp/{nome_tmp}",
                    "texto_ocr": texto,
                    "sem_desconto_atacado": dados.get("sem_desconto_atacado", False),
                },
            )
    else:
        form = EscanearCartazForm()

    return render(request, "escanear_cartaz.html", {"form": form, "compra": compra})


@login_required
def confirmar_produto(request, compra_id):
    """Etapa 1 — valida os dados do OCR e exibe tela de quantidade."""
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )

    if request.method != "POST":
        return redirect("src:escanear_cartaz", compra_id=compra_id)

    form = ConfirmarProdutoForm(request.POST, request.FILES)
    caminho_tmp = request.POST.get("caminho_tmp", "")
    foto_url = request.POST.get("foto_url", "")

    if not form.is_valid():
        return render(
            request,
            "confirmar_produto.html",
            {
                "form": form,
                "compra": compra,
                "caminho_tmp": caminho_tmp,
                "foto_url": foto_url,
            },
        )

    d = form.cleaned_data
    qtd_form = InformarQuantidadeForm()
    texto_ocr = request.POST.get("texto_ocr", "")

    return render(
        request,
        "informar_quantidade.html",
        {
            "qtd_form": qtd_form,
            "compra": compra,
            "nome": d["nome"],
            "peso_volume": d.get("peso_volume", ""),
            "preco_unitario": d["preco_unitario"],
            "preco_atacado": d.get("preco_atacado") or "",
            "qtd_min_atacado": d.get("qtd_min_atacado") or "",
            "caminho_tmp": caminho_tmp,
            "foto_url": foto_url,
            "texto_ocr": texto_ocr,
        },
    )


@login_required
def informar_quantidade(request, compra_id):
    """Etapa 2 — recebe a quantidade, calcula o total e salva o item."""
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )

    if request.method != "POST":
        return redirect("src:escanear_cartaz", compra_id=compra_id)

    qtd_form = InformarQuantidadeForm(request.POST)

    # Recupera dados da etapa 1 via POST oculto
    nome = request.POST.get("nome", "")
    peso_volume = request.POST.get("peso_volume", "")
    caminho_tmp = request.POST.get("caminho_tmp", "")
    foto_url = request.POST.get("foto_url", "")
    texto_ocr = request.POST.get("texto_ocr", "")

    def _decimal(val):
        try:
            return Decimal(str(val).replace(",", "."))
        except (InvalidOperation, TypeError):
            return None

    preco_unitario = _decimal(request.POST.get("preco_unitario"))
    preco_atacado = _decimal(request.POST.get("preco_atacado")) or None
    qtd_min_str = request.POST.get("qtd_min_atacado", "")
    qtd_min_atacado = int(qtd_min_str) if qtd_min_str.isdigit() else None

    if not qtd_form.is_valid() or not preco_unitario:
        return render(
            request,
            "informar_quantidade.html",
            {
                "qtd_form": qtd_form,
                "compra": compra,
                "nome": nome,
                "peso_volume": peso_volume,
                "preco_unitario": preco_unitario,
                "preco_atacado": preco_atacado or "",
                "qtd_min_atacado": qtd_min_atacado or "",
                "caminho_tmp": caminho_tmp,
                "foto_url": foto_url,
            },
        )

    quantidade = qtd_form.cleaned_data["quantidade"]

    # Calcular total do item antes de salvar
    if preco_atacado and qtd_min_atacado and quantidade >= qtd_min_atacado:
        item_total = preco_atacado * quantidade
    else:
        item_total = preco_unitario * quantidade

    # Verificar orçamento — pede confirmação se for exceder
    if compra.orcamento and request.POST.get("confirmar_excesso") != "1":
        total_atual = compra.total()
        total_novo = total_atual + item_total
        if total_novo > compra.orcamento:
            excesso = total_novo - compra.orcamento
            return render(
                request,
                "informar_quantidade.html",
                {
                    "qtd_form": qtd_form,
                    "compra": compra,
                    "nome": nome,
                    "peso_volume": peso_volume,
                    "preco_unitario": preco_unitario,
                    "preco_atacado": preco_atacado or "",
                    "qtd_min_atacado": qtd_min_atacado or "",
                    "caminho_tmp": caminho_tmp,
                    "foto_url": foto_url,
                    "texto_ocr": texto_ocr,
                    "excedeu_orcamento": True,
                    "excesso": excesso,
                    "item_total": item_total,
                    "orcamento": compra.orcamento,
                    "total_novo": total_novo,
                },
            )

    # Salva a foto definitivamente em media/produtos/
    foto_field = None
    if caminho_tmp and os.path.exists(caminho_tmp):
        from django.core.files import File

        with open(caminho_tmp, "rb") as f:
            nome_arquivo = os.path.basename(caminho_tmp).replace(
                f"tmp_{request.user.id}_{compra_id}_", ""
            )
            foto_field = File(f, name=nome_arquivo)
            item = ItemCompra(
                compra=compra,
                nome=nome,
                peso_volume=peso_volume,
                preco_unitario=preco_unitario,
                preco_atacado=preco_atacado,
                qtd_min_atacado=qtd_min_atacado,
                quantidade=quantidade,
                ocr_texto=texto_ocr,
            )
            item.foto.save(nome_arquivo, foto_field, save=False)
            item.save()
        # Remove o arquivo temporário
        try:
            os.remove(caminho_tmp)
        except OSError:
            pass
    else:
        item = ItemCompra.objects.create(
            compra=compra,
            nome=nome,
            peso_volume=peso_volume,
            preco_unitario=preco_unitario,
            preco_atacado=preco_atacado,
            qtd_min_atacado=qtd_min_atacado,
            quantidade=quantidade,
            ocr_texto=texto_ocr,
        )

    messages.success(request, f'"{item.nome}" adicionado com sucesso.')
    return redirect("src:lista_compra", compra_id=compra_id)


@login_required
def excluir_compra(request, compra_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="finalizada"
    )
    compra.delete()
    return redirect("src:painel_compras")
