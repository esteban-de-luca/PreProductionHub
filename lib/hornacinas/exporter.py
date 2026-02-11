import pandas as pd

from lib.hornacinas.models import HornacinaInput, MaterialInfo, Piece


def to_dataframe(inp: HornacinaInput, material: MaterialInfo, pieces: list[Piece]) -> pd.DataFrame:
    rows: list[dict[str, str | int]] = []

    for piece in pieces:
        if piece.nomenclatura.endswith("-TRA"):
            dim_1 = piece.ancho_mm
            dim_2 = piece.largo_mm
        else:
            dim_1 = piece.largo_mm
            dim_2 = piece.ancho_mm

        rows.append(
            {
                "A": inp.project_id,
                "B": "H",
                "C": piece.nomenclatura,
                "D": "H",
                "E": dim_1,
                "F": dim_2,
                "G": material.composicion,
                "H": material.code,
                "I": inp.color,
                "J": "hor.",
            }
        )

    return pd.DataFrame(rows, columns=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"])


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")
