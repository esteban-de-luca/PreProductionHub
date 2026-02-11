from dataclasses import dataclass


@dataclass(frozen=True)
class HornacinaInput:
    project_id: str
    h_index: int
    ancho_mm: int
    alto_mm: int
    fondo_mm: int
    num_baldas: int
    material_code: str
    color: str
    herraje_colgar: bool
    rodapie_mm: int


@dataclass(frozen=True)
class MaterialInfo:
    code: str
    espesor_mm: int
    composicion: str


@dataclass(frozen=True)
class Piece:
    nomenclatura: str
    largo_mm: int
    ancho_mm: int
