def test_sp1_package_imports():
    import sp1_aod_pipeline

    assert sp1_aod_pipeline.__version__ == "1.0.0"


def test_davinci_monet_is_pinned():
    # SP1 depends on davinci_monet being importable in this env.
    import davinci_monet
    import davinci_monet.datasets  # noqa: F401  # register dataset readers
    from davinci_monet.core.registry import source_registry
    from davinci_monet.io.download.earthdata import CollectionSpec, stage_collection
    from davinci_monet.pairing.grid_binning import bin_swath_to_grid, edges_from_centers

    assert davinci_monet is not None
    assert CollectionSpec is not None
    assert stage_collection is not None
    assert bin_swath_to_grid is not None
    assert edges_from_centers is not None
    assert "modis_l2_aod" in source_registry.list()
