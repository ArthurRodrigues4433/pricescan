from django.shortcuts import render, redirect
from .forms import ItemCompraForm
from .models import Compra


def adicionar_produto(request):
    compra = Compra.objects.last()

    if not compra:

        compra = Compra.objects.create(usuario=request.user)

    if request.method == "POST":
        form = ItemCompraForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.compra = compra
            item.save()
            return redirect("lista_compra")
    else:
        form = ItemCompraForm()
    return render(request, "adicionar_produto.html", {"form": form})


def lista_compra(request):
    compra = Compra.objects.last()
    itens = compra.itens.all() if compra else []
    total_geral = compra.total() if compra else 0
    return render(
        request,
        "lista_compra.html",
        {
            "compra": compra,
            "itens": itens,
            "total_geral": total_geral,
        },
    )
