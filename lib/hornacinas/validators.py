from lib.hornacinas.models import HornacinaInput, MaterialInfo
from lib.hornacinas.rules import HANGING_HARDWARE_DISCOUNT_MM, RODAPIE_CLEARANCE_MM


def validate_input(inp: HornacinaInput, material: MaterialInfo) -> list[str]:
    errors: list[str] = []

    ancho_int = inp.ancho_mm - 2 * material.espesor_mm
    alto_int = inp.alto_mm - 2 * material.espesor_mm

    fondo_balda = inp.fondo_mm - material.espesor_mm
    if inp.herraje_colgar:
        fondo_balda -= HANGING_HARDWARE_DISCOUNT_MM

    if ancho_int <= 0:
        errors.append(
            f"Ancho interior inválido: {inp.ancho_mm} - 2×{material.espesor_mm} = {ancho_int} mm (debe ser > 0)."
        )

    if alto_int <= 0:
        errors.append(
            f"Alto interior inválido: {inp.alto_mm} - 2×{material.espesor_mm} = {alto_int} mm (debe ser > 0)."
        )

    if fondo_balda <= 0:
        if inp.herraje_colgar:
            errors.append(
                f"Fondo de balda inválido: {inp.fondo_mm} - {material.espesor_mm} - {HANGING_HARDWARE_DISCOUNT_MM} = {fondo_balda} mm (debe ser > 0)."
            )
        else:
            errors.append(
                f"Fondo de balda inválido: {inp.fondo_mm} - {material.espesor_mm} = {fondo_balda} mm (debe ser > 0)."
            )

    if inp.rodapie_mm > 0:
        alto_rod = inp.rodapie_mm - RODAPIE_CLEARANCE_MM
        alto_trasera = alto_int - inp.rodapie_mm

        if alto_rod <= 0:
            errors.append(
                f"Altura de rodapié inválida: {inp.rodapie_mm} - {RODAPIE_CLEARANCE_MM} = {alto_rod} mm (debe ser > 0)."
            )

        if alto_trasera <= 0:
            errors.append(
                f"Altura de trasera inválida: {alto_int} - {inp.rodapie_mm} = {alto_trasera} mm (debe ser > 0)."
            )

    return errors
