from lib.hornacinas.models import HornacinaInput, MaterialInfo, Piece

HANGING_HARDWARE_DISCOUNT_MM = 21
RODAPIE_CLEARANCE_MM = 5

MATERIALS: dict[str, MaterialInfo] = {
    "LAC": MaterialInfo(code="LAC", espesor_mm=18, composicion="MDF"),
    "WOO": MaterialInfo(code="WOO", espesor_mm=19, composicion="MDF"),
    "LAM": MaterialInfo(code="LAM", espesor_mm=19, composicion="PLY"),
    "LIN": MaterialInfo(code="LIN", espesor_mm=20, composicion="PLY"),
}


def get_material_info(material_code: str) -> MaterialInfo:
    code = (material_code or "").strip().upper()
    if code not in MATERIALS:
        raise ValueError(f"MaterialCode inválido: {material_code}")
    return MATERIALS[code]


def build_pieces(inp: HornacinaInput, material: MaterialInfo) -> list[Piece]:
    ancho_int = inp.ancho_mm - 2 * material.espesor_mm
    alto_int = inp.alto_mm - 2 * material.espesor_mm

    fondo_balda = inp.fondo_mm - material.espesor_mm
    if inp.herraje_colgar:
        fondo_balda -= HANGING_HARDWARE_DISCOUNT_MM

    if inp.rodapie_mm > 0:
        alto_rod = inp.rodapie_mm - RODAPIE_CLEARANCE_MM
        alto_trasera = alto_int - inp.rodapie_mm
    else:
        alto_rod = 0
        alto_trasera = alto_int

    prefix = f"H{inp.h_index}"

    pieces: list[Piece] = [
        Piece(nomenclatura=f"{prefix}-LAT1", largo_mm=inp.fondo_mm, ancho_mm=inp.alto_mm),
        Piece(nomenclatura=f"{prefix}-LAT2", largo_mm=inp.fondo_mm, ancho_mm=inp.alto_mm),
        Piece(nomenclatura=f"{prefix}-TAP", largo_mm=inp.fondo_mm, ancho_mm=ancho_int),
        Piece(nomenclatura=f"{prefix}-BAS", largo_mm=inp.fondo_mm, ancho_mm=ancho_int),
    ]

    for idx in range(1, inp.num_baldas + 1):
        pieces.append(Piece(nomenclatura=f"{prefix}-BLD{idx}", largo_mm=fondo_balda, ancho_mm=ancho_int))

    if inp.rodapie_mm > 0:
        pieces.append(Piece(nomenclatura=f"{prefix}-ROD", largo_mm=alto_rod, ancho_mm=ancho_int))

    pieces.append(Piece(nomenclatura=f"{prefix}-TRA", largo_mm=alto_trasera, ancho_mm=ancho_int))
    return pieces
