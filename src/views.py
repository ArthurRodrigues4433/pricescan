from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import (
    UserCreationForm,
)  # noqa: F401 (mantido por compatibilidade)
from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ItemCompraForm, RegisterForm
from .models import Compra, ItemCompra


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
    compras = Compra.objects.filter(usuario=request.user).order_by("-data")
    return render(request, "painel_compras.html", {"compras": compras})


@login_required
def criar_compra(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    nova_compra = Compra.objects.create(usuario=request.user, status="ativa")
    return redirect("src:lista_compra", compra_id=nova_compra.id)  # type: ignore


@login_required
def adicionar_produto(request, compra_id):

    # Receba a compra via URL
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )

    if request.method == "POST":
        form = ItemCompraForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.compra = compra
            item.save()
            messages.success(request, f'"{item.nome}" adicionado com sucesso.')
            return redirect("src:adicionar_produto", compra_id=compra_id)
    else:
        form = ItemCompraForm()
    return render(request, "adicionar_produto.html", {"form": form, "compra": compra})


@login_required
def lista_compra(request, compra_id):
    compra = get_object_or_404(Compra, id=compra_id, usuario=request.user)
    itens = compra.itens.all()  # type: ignore
    total_geral = compra.total()
    return render(
        request,
        "lista_compra.html",
        {
            "compra": compra,
            "itens": itens,
            "total_geral": total_geral,
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
def finalizar_compra(request, compra_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )
    compra.status = "finalizada"
    compra.save(update_fields=["status"])
    return redirect("src:painel_compras")


@login_required
def excluir_compra(request, compra_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="finalizada"
    )
    compra.delete()
    return redirect("src:painel_compras")
