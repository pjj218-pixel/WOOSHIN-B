"""제조사 공식 제품 자료에서 확인한 GMAW 솔리드 와이어 목록."""

MAKERS = ("KISWEL", "KOWEL", "ESAB", "HYUNDAI")

# 같은 AWS 분류의 카탈로그 제품만 기재한다. 재고·국내 공급 여부는 별도 확인.
PRODUCTS = {
    "409": (
        {"maker": "KISWEL", "name": "M-409Cb", "aws": "ER409Nb", "url": "https://en.kiswel.com/product/product_view.asp?idx=1373"},
        {"maker": "ESAB", "name": "OK Autrod 409Nb", "aws": "ER409Nb", "url": "https://esab.com/lv/eur_en/products-solutions/product/filler-metals/stainless-steel/mig-wires-tig-rods-gmaw-gtaw/ok-autrod-409nb/"},
    ),
    "304L": (
        {"maker": "KISWEL", "name": "M-308LSi", "aws": "ER308LSi", "url": "https://en.kiswel.com/product/product_view.asp?idx=1385"},
        {"maker": "KOWEL", "name": "KWT/M-308LSi", "aws": "ER308LSi", "url": "https://www.kowel.co.kr/files/2015/03/%EC%8A%A4%ED%85%8C%EC%9D%B8%EB%A6%AC%EC%8A%A4%EA%B0%95-%EC%9A%A9%EC%A0%91%EC%9E%AC%EB%A3%8CMSDS_2022.08.26-R.4.pdf"},
        {"maker": "ESAB", "name": "OK Autrod 308LSi", "aws": "ER308LSi", "url": "https://esab.com/ae/mea_en/products-solutions/product/filler-metals/stainless-steel/mig-wires-tig-rods-gmaw-gtaw/ok-autrod-308lsi/"},
        {"maker": "HYUNDAI", "name": "SM-308LSi", "aws": "ER308LSi", "url": "https://hyundaiwelding.com/data/file/consumables/catalog/SM-308LSi_en_eng.pdf"},
    ),
    "304": (
        {"maker": "KISWEL", "name": "M-308", "aws": "ER308", "url": "https://en.kiswel.com/product/product_view.asp?idx=1388"},
        {"maker": "KOWEL", "name": "KWT/M-308", "aws": "ER308", "url": "https://www.kowel.co.kr/files/2015/03/%EC%8A%A4%ED%85%8C%EC%9D%B8%EB%A6%AC%EC%8A%A4%EA%B0%95-%EC%9A%A9%EC%A0%91%EC%9E%AC%EB%A3%8CMSDS_2022.08.26-R.4.pdf"},
        {"maker": "HYUNDAI", "name": "SM-308", "aws": "ER308", "url": "https://www.hyundaiwelding.com/data/file/consumables/catalog/SM-308_en_eng.pdf"},
    ),
    "dissimilar": (
        {"maker": "KISWEL", "name": "M-309LSi", "aws": "ER309LSi", "url": "https://www.kiswel.com/Data/Product/eng/M-309LSi.PDF"},
        {"maker": "KOWEL", "name": "KWT/M-309LSi", "aws": "ER309LSi", "url": "https://www.kowel.co.kr/files/2015/03/%EC%8A%A4%ED%85%8C%EC%9D%B8%EB%A6%AC%EC%8A%A4%EA%B0%95-%EC%9A%A9%EC%A0%91%EC%9E%AC%EB%A3%8CMSDS_2022.08.26-R.4.pdf"},
        {"maker": "ESAB", "name": "Exaton 309Si/309LSi", "aws": "ER309LSi", "url": "https://esab.com/us/nam_en/products-solutions/product/filler-metals/stainless-steel/mig-wires-tig-rods-gmaw-gtaw/exaton-309si-309lsi-gmaw/"},
        {"maker": "HYUNDAI", "name": "SM-309LSi", "aws": "ER309LSi", "url": "https://www.hyundaiwelding.com/data/file/consumables/ttr/SM-309LSi.pdf"},
    ),
}
