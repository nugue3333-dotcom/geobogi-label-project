window.GEOBOKI_PRODUCTS = [
  {
    id: "package-starter-1d",
    category: "package",
    name: "입문형 1D 바코드 패키지",
    image: "assets/products/supply-label.jpg",
    summary: "소형 매장과 온라인 판매의 기본 라벨 발행, 재고 조회 시작을 위한 초안 패키지입니다.",
    badges: ["starter-1d", "Code128", "EAN-13"],
    specs: ["구성: 프린터, 스캐너, Basic label + inventory", "바코드: Code128, EAN-13, Code39", "대상: 기본 라벨 발행과 상품 조회", "확정: 모델, 라벨 규격, 설치 조건"]
  },
  {
    id: "package-warehouse-2d",
    category: "package",
    name: "물류형 2D 바코드 패키지",
    image: "assets/products/supply-other.jpg",
    summary: "입고, 출고, 라벨 발행이 반복되는 물류 업무를 기준으로 장비와 프로그램을 묶는 초안 패키지입니다.",
    badges: ["warehouse-2d", "QR", "DataMatrix"],
    specs: ["구성: 프린터, 스캐너, Inbound/outbound + label", "바코드: Code128, QR, DataMatrix", "대상: 창고, 물류, 반복 출고", "확정: 출력량, 스캔 동선, 설치 범위"]
  },
  {
    id: "package-store-basic",
    category: "package",
    name: "매장형 스캔 조회 패키지",
    image: "assets/products/zebra-ds2200.jpg",
    summary: "상품 조회와 재고 확인이 필요한 매장형 업무를 위한 스캐너 중심 초안 패키지입니다.",
    badges: ["store-basic", "Product lookup", "stock"],
    specs: ["구성: 스캐너 선택, Product lookup + stock", "바코드: Code128, EAN-13", "대상: 매장 상품 조회와 재고 확인", "확정: 입력 방식, 스캐너 품번, 설치 조건"]
  },
  {
    id: "printer-bixolon-xd3-40",
    category: "printer",
    maker: "BIXOLON",
    methods: ["열전사", "감열"],
    name: "XD3-40 Series",
    image: "assets/products/bixolon-xd3-40.png",
    summary: "입문형 4인치 데스크톱 라벨 프린터 후보입니다. 세부 품번에 따라 출력 방식과 옵션을 확인합니다.",
    badges: ["BIXOLON", "4인치", "데스크톱"],
    specs: ["분류: 4인치 데스크톱", "출력: 열전사/감열 품번 확인", "업무: 기본 상품 라벨 발행", "확정: 드라이버, 라벨 폭, 연결 방식"]
  },
  {
    id: "printer-bixolon-xd5-40",
    category: "printer",
    maker: "BIXOLON",
    methods: ["열전사", "감열"],
    name: "XD5-40 Series",
    image: "assets/products/bixolon-xd5-40-clean.png",
    summary: "온라인 판매와 창고 라벨 발행에 맞춰 검토하기 좋은 4인치 데스크톱 후보입니다.",
    badges: ["BIXOLON", "DT/TT 확인", "데스크톱"],
    specs: ["분류: 4인치 데스크톱", "출력: 감열 또는 열전사 옵션 확인", "업무: 송장, 상품, 입출고 라벨", "확정: 해상도, 인터페이스, 재고"]
  },
  {
    id: "printer-bixolon-xd7-20d",
    category: "printer",
    maker: "BIXOLON",
    methods: ["감열"],
    name: "XD7-20d",
    image: "assets/products/bixolon-xd7-20d.png",
    summary: "작은 폭의 감열 라벨이 필요한 업무에 검토하는 2인치 소형 후보입니다.",
    badges: ["BIXOLON", "2인치", "감열"],
    specs: ["분류: 2인치 데스크톱", "출력: 감열 후보", "업무: 소형 라벨, 식별표", "확정: 라벨 폭, 용지 종류, 연결 방식"]
  },
  {
    id: "printer-bixolon-xl5-40",
    category: "printer",
    maker: "BIXOLON",
    methods: ["감열"],
    name: "XL5-40",
    image: "assets/products/bixolon-xl5-40-clean.png",
    summary: "라이너리스 라벨 업무를 검토할 때 상담 후보로 두는 4인치 프린터입니다.",
    badges: ["BIXOLON", "라이너리스", "감열"],
    specs: ["분류: 4인치 라이너리스 후보", "출력: 감열 라벨 상담", "업무: linerless 라벨 검토", "확정: 용지 공급, 커터, 부착 환경"]
  },
  {
    id: "printer-bixolon-xt3-40",
    category: "printer",
    maker: "BIXOLON",
    methods: ["열전사"],
    name: "XT3-40",
    image: "assets/products/bixolon-xt3-40-clean.png",
    summary: "출력량이 늘어나는 현장과 물류 라벨 업무에 검토하는 산업용 후보입니다.",
    badges: ["BIXOLON", "산업용", "열전사"],
    specs: ["분류: 산업용 라벨 프린터", "출력: 열전사 중심 상담", "업무: 반복 발행, 창고 라벨", "확정: 리본, 라벨 폭, 설치 위치"]
  },
  {
    id: "printer-bixolon-xt5-40",
    category: "printer",
    maker: "BIXOLON",
    methods: ["열전사"],
    name: "XT5-40 Series",
    image: "assets/products/bixolon-xt5-40-clean.png",
    summary: "산업용 라벨 발행 환경에서 출력량과 내구 조건을 함께 검토하는 후보입니다.",
    badges: ["BIXOLON", "산업용", "고출력 상담"],
    specs: ["분류: 산업용 4인치 후보", "출력: 열전사 중심 상담", "업무: 대량 라벨 발행", "확정: 해상도, 옵션, 현장 설치 조건"]
  },
  {
    id: "printer-tsc-da",
    category: "printer",
    maker: "TSC",
    methods: ["감열"],
    name: "DA Series",
    image: "assets/products/tsc-da-series.png",
    summary: "DA210, DA220, DA310, DA320 계열을 포함하는 감열 데스크톱 상담 후보입니다.",
    badges: ["TSC", "DA", "감열"],
    specs: ["분류: 4인치 데스크톱", "출력: 감열 후보", "업무: 기본 라벨과 송장", "확정: DA 세부 모델, 해상도, 재고"]
  },
  {
    id: "printer-tsc-dh",
    category: "printer",
    maker: "TSC",
    methods: ["감열"],
    name: "DH Series",
    image: "assets/products/tsc-dh-series.jpg",
    summary: "TSC 4인치 감열 데스크톱 후보입니다. TH가 아니라 DH 모델을 감열 기준으로 표시합니다.",
    badges: ["TSC", "DH", "감열"],
    specs: ["분류: 4인치 데스크톱", "출력: Direct thermal only", "업무: 송장, 상품, 물류 라벨", "확정: DH240T/DH340T 등 세부 품번"]
  },
  {
    id: "printer-tsc-te",
    category: "printer",
    maker: "TSC",
    methods: ["열전사"],
    name: "TE Series",
    image: "assets/products/tsc-te-series.png",
    summary: "열전사 리본을 함께 검토하는 4인치 데스크톱 라벨 프린터 후보입니다.",
    badges: ["TSC", "TE", "열전사"],
    specs: ["분류: 4인치 데스크톱", "출력: 열전사 후보", "업무: 내구 라벨 발행", "확정: 리본, 라벨 재질, 연결 방식"]
  },
  {
    id: "printer-tsc-th",
    category: "printer",
    maker: "TSC",
    methods: ["열전사"],
    name: "TH Series",
    image: "assets/products/tsc-th-series.jpg",
    summary: "TSC 열전사 데스크톱 상담 후보입니다. 감열 분류에는 DH Series를 사용합니다.",
    badges: ["TSC", "TH", "열전사"],
    specs: ["분류: 4인치 데스크톱", "출력: 열전사 후보", "업무: 리본 사용 라벨, 내구 라벨", "확정: TH240/TH340 등 세부 품번"]
  },
  {
    id: "printer-tsc-tx",
    category: "printer",
    maker: "TSC",
    methods: ["열전사"],
    name: "TX Series",
    image: "assets/products/tsc-tx-series.png",
    summary: "작은 글자와 촘촘한 바코드가 필요한 업무에서 해상도 옵션을 확인하는 후보입니다.",
    badges: ["TSC", "TX", "고해상도 상담"],
    specs: ["분류: 데스크톱 라벨 프린터", "출력: 열전사 후보", "업무: 소형 텍스트, 고밀도 코드", "확정: 해상도, 리본, 라벨 폭"]
  },
  {
    id: "printer-tsc-tc",
    category: "printer",
    maker: "TSC",
    methods: ["열전사"],
    name: "TC Series",
    image: "assets/products/tsc-tc-series.png",
    summary: "일반 라벨 발행 업무에서 리본과 라벨 재질 조합을 함께 보는 후보입니다.",
    badges: ["TSC", "TC", "열전사"],
    specs: ["분류: 데스크톱 후보", "출력: 열전사 후보", "업무: 일반 상품 라벨", "확정: 리본 타입, 라벨 재질, 드라이버"]
  },
  {
    id: "printer-tsc-ttp",
    category: "printer",
    maker: "TSC",
    methods: ["열전사"],
    name: "TTP Series",
    image: "assets/products/tsc-ttp-series.png",
    summary: "TTP-244, TTP-247, TTP-345 계열을 포함해 열전사 업무에서 비교하는 후보입니다.",
    badges: ["TSC", "TTP", "열전사"],
    specs: ["분류: 데스크톱 라벨 프린터", "출력: 열전사 후보", "업무: 일반 라벨 발행", "확정: 세부 모델, 해상도, 리본"]
  },
  {
    id: "printer-zebra-zd400",
    category: "printer",
    maker: "Zebra",
    methods: ["열전사", "감열"],
    name: "ZD400 Series",
    image: "assets/products/zebra-zd400.jpg",
    summary: "ZD421, ZD411 계열을 포함해 데스크톱 라벨 발행에서 비교하는 후보입니다.",
    badges: ["Zebra", "ZD400", "데스크톱"],
    specs: ["분류: 데스크톱 라벨 프린터", "출력: 세부 품번별 확인", "업무: 매장, 온라인 판매 라벨", "확정: ZD421/ZD411, 옵션, 연결 방식"]
  },
  {
    id: "printer-zebra-zd600",
    category: "printer",
    maker: "Zebra",
    methods: ["열전사", "감열"],
    name: "ZD600 Series",
    image: "assets/products/zebra-zd600.jpg",
    summary: "ZD621, ZD611 계열을 포함해 고급 데스크톱 라벨 발행 후보로 검토합니다.",
    badges: ["Zebra", "ZD600", "고급형"],
    specs: ["분류: 데스크톱 라인업 후보", "출력: 세부 품번별 확인", "업무: 안정적인 반복 발행", "확정: 옵션, 해상도, 재고"]
  },
  {
    id: "printer-zebra-zt231",
    category: "printer",
    maker: "Zebra",
    methods: ["열전사", "감열"],
    name: "ZT231",
    image: "assets/products/zebra-zt231.jpg",
    summary: "데스크톱보다 높은 출력량이 필요한 업무에서 산업용 후보로 검토합니다.",
    badges: ["Zebra", "ZT231", "산업용"],
    specs: ["분류: 산업용 프린터 후보", "출력: 세부 품번별 확인", "업무: 중간 물량 라벨 발행", "확정: 설치 위치, 라벨 폭, 옵션"]
  },
  {
    id: "printer-zebra-zt400",
    category: "printer",
    maker: "Zebra",
    methods: ["열전사", "감열"],
    name: "ZT400 Series",
    image: "assets/products/zebra-zt400.jpg",
    summary: "산업용 라벨 발행과 현장 내구 조건을 함께 검토하는 제브라 후보입니다.",
    badges: ["Zebra", "ZT400", "산업용"],
    specs: ["분류: 산업용 라인업 후보", "출력: 세부 품번별 확인", "업무: 대량 라벨과 현장 발행", "확정: 옵션, 설치 환경, 유지보수"]
  },
  {
    id: "scanner-zebra-ds2200",
    category: "scanner",
    maker: "Zebra",
    connections: ["유선", "무선"],
    name: "DS2200 Series",
    image: "assets/products/zebra-ds2200.jpg",
    summary: "DS2208, DS2278 계열을 포함해 1D/2D 기본 스캔 업무에 검토하는 후보입니다.",
    badges: ["Zebra", "1D/2D", "유선/무선"],
    specs: ["분류: 일반 핸드헬드", "연결: 유선/무선 품번 확인", "업무: 상품 바코드, QR 스캔", "확정: 거치대, 입력 방식, 충전 구성"]
  },
  {
    id: "scanner-zebra-ds4600",
    category: "scanner",
    maker: "Zebra",
    connections: ["유선"],
    name: "DS4600 Series",
    image: "assets/products/zebra-ds4600.jpg",
    summary: "매장 POS와 일반 카운터 업무에서 검토하는 유선 스캐너 후보입니다.",
    badges: ["Zebra", "유선", "매장"],
    specs: ["분류: 일반 핸드헬드", "연결: 유선 후보", "업무: 매장 스캔, 상품 조회", "확정: 스탠드, 케이블, 입력 방식"]
  },
  {
    id: "scanner-zebra-ds8100",
    category: "scanner",
    maker: "Zebra",
    connections: ["유선", "무선"],
    name: "DS8100 Series",
    image: "assets/products/zebra-ds8100.jpg",
    summary: "빠른 스캔과 고성능 핸드헬드 구성이 필요한 업무에서 검토합니다.",
    badges: ["Zebra", "고성능", "유선/무선"],
    specs: ["분류: 고성능 핸드헬드", "연결: 세부 품번별 확인", "업무: 고빈도 스캔", "확정: 충전 크래들, 거치대, 입력 테스트"]
  },
  {
    id: "scanner-zebra-ds3600",
    category: "scanner",
    maker: "Zebra",
    connections: ["유선", "무선"],
    name: "DS3600 Series",
    image: "assets/products/zebra-ds3600.jpg",
    summary: "창고, 제조, 거친 작업 환경에서 내구 조건을 함께 검토하는 후보입니다.",
    badges: ["Zebra", "산업용", "유선/무선"],
    specs: ["분류: 초견고형 후보", "연결: 세부 품번별 확인", "업무: 창고, 제조, 물류", "확정: 스캔 거리, 코드 종류, 현장 테스트"]
  },
  {
    id: "scanner-honeywell-1470g",
    category: "scanner",
    maker: "Honeywell",
    connections: ["유선"],
    name: "Voyager XP 1470g",
    image: "assets/products/honeywell-voyager-1470g.png",
    summary: "일반 매장과 소형 물류 업무에서 1D/2D 스캔 후보로 검토합니다.",
    badges: ["Honeywell", "유선", "1D/2D"],
    specs: ["분류: 일반 핸드헬드", "연결: 유선 후보", "업무: 상품 스캔, QR 스캔", "확정: 케이블, 스탠드, 입력 방식"]
  },
  {
    id: "scanner-honeywell-1950g",
    category: "scanner",
    maker: "Honeywell",
    connections: ["유선"],
    name: "Xenon XP 1950g",
    image: "assets/products/honeywell-xenon-1950g.png",
    summary: "고성능 일반 업무 스캔 후보로, 프로그램 입력 흐름과 함께 테스트합니다.",
    badges: ["Honeywell", "유선", "고성능"],
    specs: ["분류: 고성능 핸드헬드", "연결: 유선 후보", "업무: 빠른 상품 조회", "확정: 코드 종류, 거리, 입력 방식"]
  },
  {
    id: "scanner-honeywell-1960g",
    category: "scanner",
    maker: "Honeywell",
    connections: ["유선"],
    name: "Xenon Ultra 1960g",
    image: "assets/products/honeywell-xenon-1960g.png",
    summary: "고밀도 코드와 고성능 스캔 업무를 상담할 때 검토하는 후보입니다.",
    badges: ["Honeywell", "유선", "고밀도 상담"],
    specs: ["분류: 고성능 핸드헬드", "연결: 유선 후보", "업무: 고밀도 코드 확인", "확정: 코드 종류, 설정, 입력 테스트"]
  },
  {
    id: "scanner-honeywell-1990i",
    category: "scanner",
    maker: "Honeywell",
    connections: ["유선"],
    name: "Granit XP 1990i",
    image: "assets/products/honeywell-granit-1990i.png",
    summary: "창고와 제조 환경에서 튼튼한 스캔 구성이 필요한 경우 검토합니다.",
    badges: ["Honeywell", "산업용", "유선"],
    specs: ["분류: 견고형 후보", "연결: 유선 후보", "업무: 창고, 제조 스캔", "확정: 스캔 거리, 케이블, 현장 조건"]
  },
  {
    id: "scanner-datalogic-quickscan-2500",
    category: "scanner",
    maker: "Datalogic",
    connections: ["유선", "무선"],
    name: "QuickScan 2500 Series",
    image: "assets/products/datalogic-quickscan-2500.png",
    summary: "입문형 2D 핸드헬드 스캔 업무에서 유선/무선 품번을 비교하는 후보입니다.",
    badges: ["Datalogic", "2D", "유선/무선"],
    specs: ["분류: 일반 핸드헬드", "연결: 시리즈 품번별 확인", "업무: 기본 2D 스캔", "확정: 거치대, 충전 구성, 입력 방식"]
  },
  {
    id: "scanner-datalogic-gryphon-4500",
    category: "scanner",
    maker: "Datalogic",
    connections: ["유선", "무선"],
    name: "Gryphon 4500 Series",
    image: "assets/products/datalogic-gryphon-4500.png",
    summary: "2D 고급형 스캔 업무에서 유선/무선 구성을 비교하는 후보입니다.",
    badges: ["Datalogic", "2D", "고급형"],
    specs: ["분류: 고급 핸드헬드", "연결: 시리즈 품번별 확인", "업무: QR, 상품 코드, 매장 업무", "확정: 크래들, 케이블, 입력 테스트"]
  },
  {
    id: "scanner-datalogic-powerscan-9100",
    category: "scanner",
    maker: "Datalogic",
    connections: ["유선", "무선"],
    name: "PowerScan 9100 Series",
    image: "assets/products/datalogic-powerscan-9100.png",
    summary: "산업용 스캔 환경에서 내구성과 스캔 동선을 확인하는 후보입니다.",
    badges: ["Datalogic", "산업용", "유선/무선"],
    specs: ["분류: 산업용 스캐너 후보", "연결: 시리즈 품번별 확인", "업무: 제조, 물류, 창고", "확정: 현장 거리, 코드 종류, 거치 방식"]
  },
  {
    id: "supply-ribbon",
    category: "supply",
    name: "열전사 리본",
    image: "assets/products/supply-ribbon.jpg",
    summary: "왁스, 왁스/레진, 레진 계열을 라벨 재질과 보관 환경에 맞춰 비교합니다.",
    badges: ["Ribbon", "Wax", "Resin"],
    specs: ["분류: 열전사 소모품", "종류: 왁스, 왁스/레진, 레진", "업무: 내구 라벨 발행", "확정: 폭, 길이, 라벨 재질"]
  },
  {
    id: "supply-label",
    category: "supply",
    name: "바코드 라벨",
    image: "assets/products/supply-label.jpg",
    summary: "감열, 열전사, 아트지, 유포지, 리무버블, 연속지 등 규격을 장비 확정 후 맞춥니다.",
    badges: ["Label", "Tag", "Linerless"],
    specs: ["분류: 라벨/태그", "종류: 감열, 열전사, 합성지 등", "업무: 상품, 송장, 재고 라벨", "확정: 폭, 높이, 지관, 접착력"]
  },
  {
    id: "supply-accessory",
    category: "supply",
    name: "부품과 액세서리",
    image: "assets/products/supply-other.jpg",
    summary: "스캐너 거치대, 케이블, 전원 어댑터, 클리닝 용품, 헤드와 롤러를 모델별로 확인합니다.",
    badges: ["Accessory", "Cleaning", "Cable"],
    specs: ["분류: 모델별 부품", "종류: 거치대, 케이블, 전원, 클리닝", "업무: 설치와 유지관리", "확정: 모델 호환, 재고, 교체 범위"]
  }
];

window.GEOBOKI_USE_CASES = [
  {
    id: "manufacturing-ingredient",
    title: "제조 표시·성분 라벨",
    subtitle: "식품, 화장품, 생활용품의 성분·제조일·로트 정보를 라벨로 발행합니다.",
    fields: ["제품명", "성분", "제조일", "유통기한", "LOT"],
    sample: "성분표시"
  },
  {
    id: "warehouse-stock",
    title: "물류 재고관리 라벨",
    subtitle: "입고, 출고, 보관 위치, 박스 번호를 스캔 가능한 코드로 묶어 관리합니다.",
    fields: ["SKU", "입고일", "위치", "수량", "박스ID"],
    sample: "재고관리"
  },
  {
    id: "retail-product",
    title: "매장 상품·가격 라벨",
    subtitle: "상품 코드, 판매가, 매대 위치, 바코드를 상품 라벨로 정리합니다.",
    fields: ["상품코드", "판매가", "매대", "바코드"],
    sample: "상품라벨"
  },
  {
    id: "materials-inout",
    title: "자재 입출고 라벨",
    subtitle: "자재명, 규격, 거래처, 입출고 상태를 라벨과 스캔 조회 흐름으로 연결합니다.",
    fields: ["자재명", "규격", "거래처", "상태", "수량"],
    sample: "입출고"
  }
];
