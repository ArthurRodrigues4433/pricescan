from django.contrib import admin
from .models import Compra, ItemCompra


@admin.register(ItemCompra)
class ItemCompraAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nome",
        "peso_volume",
        "preco_unitario",
        "preco_atacado",
        "qtd_min_atacado",
        "quantidade",
    )
    readonly_fields = ("ocr_texto",)
    fieldsets = (
        ("Produto", {"fields": ("compra", "nome", "peso_volume", "foto")}),
        (
            "Preços",
            {
                "fields": (
                    "preco_unitario",
                    "preco_atacado",
                    "qtd_min_atacado",
                    "quantidade",
                )
            },
        ),
        ("OCR (diagnóstico)", {"fields": ("ocr_texto",), "classes": ("collapse",)}),
    )


admin.site.register(Compra)
