from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ItemCompraForm
from .models import Compra, ItemCompra


@login_required
def criar_compra(request):
    nova_compra = Compra.objects.create(usuario=request.user, status="ativa")
    return redirect("adicionar_produto", compra_id=nova_compra.id)


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
            return redirect("adicionar_produto", compra_id=compra_id)
    else:
        form = ItemCompraForm()
    return render(request, "adicionar_produto.html", {"form": form, "compra": compra})


@login_required
def lista_compra(request, compra_id):
    compra = get_object_or_404(Compra, id=compra_id, usuario=request.user)
    itens = compra.itens.all()
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
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )
    item = get_object_or_404(ItemCompra, id=item_id, compra=compra)

    if request.method == "POST":
        item.delete()

    return redirect("lista_compra", compra_id=compra_id)


@login_required
def finalizar_compra(request, compra_id):
    compra = get_object_or_404(
        Compra, id=compra_id, usuario=request.user, status="ativa"
    )

    if request.method == "POST":
        compra.status = "finalizada"
        compra.save(update_fields=["status"])
        return redirect("criar_compra")

    return redirect("lista_compra", compra_id=compra_id)
