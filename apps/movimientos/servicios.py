from django.db import transaction
from django.db.models import F

from apps.catalogos.models import Cuenta
from apps.movimientos.models import MetodoPago, Movimiento

METODO_POR_TIPO_DE_CUENTA = {
    Cuenta.Tipo.EFECTIVO: MetodoPago.EFECTIVO,
    Cuenta.Tipo.DEBITO: MetodoPago.TARJETA_DEBITO,
    Cuenta.Tipo.CREDITO: MetodoPago.TARJETA_CREDITO,
}


def metodo_para_cuenta(cuenta):
    if cuenta is None:
        return MetodoPago.EFECTIVO
    return METODO_POR_TIPO_DE_CUENTA.get(cuenta.tipo, MetodoPago.TRANSFERENCIA)


def valores_sugeridos(concepto):
    """RF-MOV-01: valores que el concepto precarga en la captura (todos opcionales)."""
    return {
        "categoria": concepto.categoria_id,
        "cuenta": concepto.cuenta_id,
        "persona": concepto.persona_id,
        "domicilio": concepto.domicilio_id,
        "es_hormiga": concepto.es_hormiga,
        "metodo_pago": metodo_para_cuenta(concepto.cuenta),
    }


@transaction.atomic
def guardar_movimiento(movimiento, usuario=None):
    """Valida y guarda. Aplica RN-14 revirtiendo antes el efecto anterior si ya existía."""
    movimiento.full_clean()
    if movimiento.pk:
        anterior = Movimiento.objects.select_for_update().get(pk=movimiento.pk)
        _aplicar_efecto(anterior, revertir=True)
    if usuario is not None and movimiento.creado_por_id is None:
        movimiento.creado_por = usuario
    movimiento.save()
    _aplicar_efecto(movimiento)
    return movimiento


@transaction.atomic
def eliminar_movimiento(movimiento):
    _aplicar_efecto(movimiento, revertir=True)
    movimiento.delete()


def _aplicar_efecto(movimiento, revertir=False):
    """RN-14: el pago de deuda reduce el saldo de la tarjeta o préstamo destino."""
    if movimiento.tipo != Movimiento.Tipo.PAGO_DEUDA:
        return
    cambio = movimiento.monto if revertir else -movimiento.monto
    Cuenta.objects.filter(pk=movimiento.cuenta_destino_id).update(
        saldo_actual=F("saldo_actual") + cambio
    )
