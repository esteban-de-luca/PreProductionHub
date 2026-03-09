from translator import build_non_mec_reference_from_mec


def test_non_mec_reference_from_mec_sp_case():
    assert build_non_mec_reference_from_mec("MEC_SP-12345_JuanPer") == "SP-12345_JuanPer"


def test_non_mec_reference_from_mec_eu_case():
    assert build_non_mec_reference_from_mec("MEC_EU-19968_Virgini") == "EU-19968_Virgini"


def test_non_mec_reference_fallback_without_mec_prefix():
    assert build_non_mec_reference_from_mec("EU-19968_Virgini") == "EU-19968_Virgini"
