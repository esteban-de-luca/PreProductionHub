from translator import build_mec_reference


def test_mec_reference_expected_example():
    assert build_mec_reference("EU-19968_Virginie van Haute") == "MEC_EU-19968_Virgini"


def test_mec_reference_max_len_20():
    result = build_mec_reference("SP-12345_Juan Perez")
    assert result == "MEC_SP-12345_JuanPer"
    assert len(result) <= 20


def test_mec_reference_fallback_without_project_id():
    result = build_mec_reference("Proyecto sin id")
    assert result == "MEC_Proyectosinid"
    assert len(result) <= 20
