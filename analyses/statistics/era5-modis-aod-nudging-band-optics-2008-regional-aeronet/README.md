# CAM7 vs AERONET Daily Regional AOD Statistics (2008)

These tables summarize the paired daily regional means used in the accepted CAM7-versus-AERONET time-series plots.

Source products: `/glade/work/fillmore/Data/CERES-SARB-CAM7/runs/era5-modis-aod-nudging-band-optics-2008-regional-aeronet/products/regional_aeronet_band_comparison`

AERONET is the reference and CAM7 is the comparison. Mean bias (MB) is `CAM7 - AERONET`; mean error (ME) is the mean absolute error. N is the number of paired regional days. Regional daily values first average matched hours within each site and then give each active site equal weight. The wavelength summary pools those regional daily values with equal weight per available region-day.

The visible comparison uses AERONET 500 nm because its routine coverage is much broader than the nominally closer 551 nm specialty channel. South Atlantic Ocean and Southern Africa have no 1640 nm paired days.

## Wavelength summary

| CAM band | CAM7 nm | AERONET nm | Regions | N | AERONET mean | CAM7 mean | MB | ME | RMSE | R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ultraviolet (SW02) | 340 | 340 | 12 | 3869 | 0.3833 | 0.3777 | -0.0057 | 0.0948 | 0.1527 | 0.8636 |
| Visible (SW05) | 546 | 500 | 12 | 3872 | 0.2727 | 0.2270 | -0.0457 | 0.0744 | 0.1184 | 0.8828 |
| Near Infrared (SW08) | 842 | 870 | 12 | 3757 | 0.1753 | 0.1345 | -0.0408 | 0.0516 | 0.0795 | 0.9079 |
| Shortwave Infrared (SW11) | 1660 | 1640 | 10 | 2331 | 0.1033 | 0.0667 | -0.0366 | 0.0485 | 0.0898 | 0.8783 |

## Ultraviolet: CAM7 340 nm vs AERONET 340 nm

| Region | N | Site-days | Hourly pairs | Mean sites/day | AERONET mean | CAM7 mean | MB | ME | RMSE | R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| North Atlantic Ocean | 365 | 1521 | 11512 | 4.17 | 0.1782 | 0.2273 | 0.0491 | 0.0633 | 0.0800 | 0.8348 |
| South Atlantic Ocean | 64 | 64 | 268 | 1.00 | 0.4122 | 0.3870 | -0.0252 | 0.0685 | 0.0927 | 0.9482 |
| North Indian Ocean | 296 | 506 | 3584 | 1.71 | 0.5751 | 0.4784 | -0.0967 | 0.1792 | 0.2710 | 0.7026 |
| North Africa (Sahara) | 361 | 1252 | 10194 | 3.47 | 0.3440 | 0.3564 | 0.0124 | 0.1097 | 0.1501 | 0.7517 |
| Southern Africa | 321 | 470 | 3497 | 1.46 | 0.4479 | 0.3399 | -0.1080 | 0.1512 | 0.2208 | 0.9014 |
| Eastern US | 358 | 2923 | 18022 | 8.16 | 0.2824 | 0.2827 | 0.0003 | 0.0397 | 0.0518 | 0.9404 |
| Western US | 365 | 3462 | 23849 | 9.48 | 0.1757 | 0.1679 | -0.0078 | 0.0302 | 0.0487 | 0.8710 |
| Canada | 344 | 1839 | 12191 | 5.35 | 0.1695 | 0.2133 | 0.0438 | 0.0590 | 0.0742 | 0.8192 |
| South America | 358 | 1668 | 10896 | 4.66 | 0.2794 | 0.2219 | -0.0575 | 0.0756 | 0.1050 | 0.8506 |
| Middle East | 365 | 1426 | 11576 | 3.91 | 0.4670 | 0.4979 | 0.0310 | 0.0694 | 0.0969 | 0.8797 |
| East Asia | 365 | 2481 | 13810 | 6.80 | 0.7466 | 0.7096 | -0.0370 | 0.1138 | 0.1574 | 0.8579 |
| India | 307 | 764 | 5156 | 2.49 | 0.6091 | 0.7104 | 0.1013 | 0.1911 | 0.2654 | 0.7864 |

## Visible: CAM7 546 nm vs AERONET 500 nm

| Region | N | Site-days | Hourly pairs | Mean sites/day | AERONET mean | CAM7 mean | MB | ME | RMSE | R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| North Atlantic Ocean | 365 | 1510 | 11446 | 4.14 | 0.1409 | 0.1645 | 0.0237 | 0.0391 | 0.0516 | 0.8667 |
| South Atlantic Ocean | 64 | 64 | 269 | 1.00 | 0.2820 | 0.2811 | -0.0009 | 0.0479 | 0.0607 | 0.9459 |
| North Indian Ocean | 296 | 506 | 3708 | 1.71 | 0.3951 | 0.2936 | -0.1015 | 0.1339 | 0.1960 | 0.6882 |
| North Africa (Sahara) | 361 | 1258 | 10325 | 3.48 | 0.2825 | 0.2482 | -0.0343 | 0.0819 | 0.1194 | 0.8206 |
| Southern Africa | 322 | 471 | 3525 | 1.46 | 0.2672 | 0.1727 | -0.0945 | 0.1075 | 0.1571 | 0.8977 |
| Eastern US | 358 | 2963 | 18437 | 8.28 | 0.1726 | 0.1570 | -0.0156 | 0.0302 | 0.0385 | 0.9304 |
| Western US | 365 | 3470 | 23924 | 9.51 | 0.1149 | 0.0877 | -0.0272 | 0.0307 | 0.0438 | 0.8436 |
| Canada | 346 | 1857 | 12305 | 5.37 | 0.1109 | 0.1065 | -0.0045 | 0.0267 | 0.0397 | 0.7500 |
| South America | 361 | 1830 | 12074 | 5.07 | 0.1684 | 0.1267 | -0.0417 | 0.0542 | 0.0719 | 0.8161 |
| Middle East | 365 | 1433 | 11813 | 3.93 | 0.3681 | 0.3127 | -0.0554 | 0.0701 | 0.0936 | 0.9054 |
| East Asia | 365 | 2586 | 14730 | 7.08 | 0.5583 | 0.4281 | -0.1302 | 0.1398 | 0.1784 | 0.8507 |
| India | 304 | 806 | 5693 | 2.65 | 0.4614 | 0.4193 | -0.0421 | 0.1303 | 0.1823 | 0.8171 |

## Near Infrared: CAM7 842 nm vs AERONET 870 nm

| Region | N | Site-days | Hourly pairs | Mean sites/day | AERONET mean | CAM7 mean | MB | ME | RMSE | R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| North Atlantic Ocean | 365 | 2049 | 15524 | 5.61 | 0.1642 | 0.1501 | -0.0142 | 0.0273 | 0.0390 | 0.9352 |
| South Atlantic Ocean | 65 | 65 | 270 | 1.00 | 0.1389 | 0.1853 | 0.0464 | 0.0561 | 0.0700 | 0.8958 |
| North Indian Ocean | 296 | 506 | 3717 | 1.71 | 0.2109 | 0.1554 | -0.0555 | 0.0663 | 0.0917 | 0.7694 |
| North Africa (Sahara) | 365 | 2553 | 21051 | 6.99 | 0.3102 | 0.2217 | -0.0885 | 0.0892 | 0.1067 | 0.9311 |
| Southern Africa | 199 | 312 | 1720 | 1.57 | 0.1045 | 0.0639 | -0.0406 | 0.0435 | 0.0575 | 0.7732 |
| Eastern US | 361 | 3571 | 22726 | 9.89 | 0.0748 | 0.0744 | -0.0004 | 0.0170 | 0.0237 | 0.8782 |
| Western US | 365 | 3604 | 25084 | 9.87 | 0.0589 | 0.0415 | -0.0174 | 0.0191 | 0.0237 | 0.8155 |
| Canada | 346 | 1855 | 12299 | 5.36 | 0.0567 | 0.0463 | -0.0103 | 0.0177 | 0.0299 | 0.5874 |
| South America | 361 | 1819 | 11956 | 5.04 | 0.0839 | 0.0628 | -0.0211 | 0.0303 | 0.0391 | 0.6999 |
| Middle East | 365 | 1672 | 13737 | 4.58 | 0.2985 | 0.2057 | -0.0928 | 0.0972 | 0.1290 | 0.9278 |
| East Asia | 365 | 3131 | 17933 | 8.58 | 0.2904 | 0.2172 | -0.0732 | 0.0774 | 0.1063 | 0.8593 |
| India | 304 | 809 | 5735 | 2.66 | 0.2632 | 0.2104 | -0.0528 | 0.0836 | 0.1158 | 0.8238 |

## Shortwave Infrared: CAM7 1660 nm vs AERONET 1640 nm

| Region | N | Site-days | Hourly pairs | Mean sites/day | AERONET mean | CAM7 mean | MB | ME | RMSE | R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| North Atlantic Ocean | 310 | 526 | 3793 | 1.70 | 0.0653 | 0.0686 | 0.0034 | 0.0269 | 0.0370 | 0.7485 |
| North Indian Ocean | 139 | 139 | 1127 | 1.00 | 0.1539 | 0.0958 | -0.0580 | 0.0647 | 0.0990 | 0.8622 |
| North Africa (Sahara) | 193 | 276 | 2228 | 1.43 | 0.0727 | 0.0922 | 0.0196 | 0.0435 | 0.0558 | 0.7639 |
| Eastern US | 333 | 1039 | 6402 | 3.12 | 0.0328 | 0.0207 | -0.0121 | 0.0135 | 0.0193 | 0.7739 |
| Western US | 190 | 221 | 1594 | 1.16 | 0.0438 | 0.0348 | -0.0090 | 0.0174 | 0.0261 | 0.8247 |
| Canada | 342 | 1449 | 10056 | 4.24 | 0.0268 | 0.0129 | -0.0139 | 0.0147 | 0.0257 | 0.4829 |
| South America | 9 | 9 | 41 | 1.00 | 0.0307 | 0.0067 | -0.0240 | 0.0240 | 0.0260 | 0.4531 |
| Middle East | 346 | 791 | 5484 | 2.29 | 0.2870 | 0.1474 | -0.1396 | 0.1412 | 0.1895 | 0.8999 |
| East Asia | 343 | 874 | 4970 | 2.55 | 0.1100 | 0.0721 | -0.0379 | 0.0437 | 0.0670 | 0.7573 |
| India | 126 | 189 | 1253 | 1.50 | 0.1539 | 0.0735 | -0.0804 | 0.0828 | 0.1252 | 0.9146 |

Machine-readable tables: [`wavelength_statistics.csv`](wavelength_statistics.csv) and [`regional_statistics.csv`](regional_statistics.csv).

Generated by `scripts/summarize_2008_regional_aeronet_band_comparison.py` using DAVINCI metric definitions.
