from datetime import date

from sp1_aod_pipeline.config import RunConfig


YAML = """\
modis_dir: /data/modis
viirs_dir: /data/viirs
out_dir: /data/out
stage_root: /data/stage
start: 2020-06-15
end: 2020-06-16
viirs_qa_min: 3
modis_ee_land: [0.05, 0.15]
"""


def test_from_yaml(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text(YAML)
    cfg = RunConfig.from_yaml(str(p))
    assert cfg.modis_dir == "/data/modis"
    assert cfg.start == date(2020, 6, 15)
    assert cfg.end == date(2020, 6, 16)
    assert cfg.viirs_qa_min == 3
    assert cfg.modis_qa_min == 1
    assert cfg.aod_min == 0.0 and cfg.aod_max == 5.0
    assert cfg.sigma_max == 5.0
    assert cfg.modis_ee_land == (0.05, 0.15)
    assert cfg.sigma_floor == 1e-3
    assert cfg.modis_product == "MOD04_L2"
    assert cfg.modis_product_aqua == "MYD04_L2"
    assert cfg.collection == "6.1"
    assert cfg.viirs_collection == "2"
