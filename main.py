import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="전국 고령화 데이터 분석",
    page_icon="📊",
    layout="wide"
)


# =========================================================
# 디자인
# =========================================================

st.markdown("""
<style>

.main {
    background-color: #ffffff;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1 {
    font-weight: 800;
}

h2 {
    font-weight: 700;
}

.metric-card {
    padding: 20px;
    border-radius: 15px;
    background: #f7f8fa;
    text-align: center;
}

.small-text {
    color: #666666;
    font-size: 0.9rem;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# 데이터 주소
# =========================================================

POP_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/population_yearly.csv.gz"
)

GEO_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/boundaries/sigungu_kr.geojson"
)


# =========================================================
# 데이터 불러오기
# =========================================================

@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():

    df = pd.read_csv(
        POP_URL,
        dtype={"코드": str}
    )

    return df


@st.cache_data(show_spinner="대한민국 지도를 불러오는 중입니다...")
def load_geojson():

    response = requests.get(
        GEO_URL,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


population = load_population()
geojson = load_geojson()


# =========================================================
# 연도 목록
# =========================================================

years = sorted(
    population["연도"]
    .dropna()
    .astype(int)
    .unique()
)


latest_year = years[-1]


# =========================================================
# 고령화율 계산 함수
# =========================================================

def calculate_population(year):

    df = population[
        population["연도"].astype(int) == year
    ].copy()


    # 전체 연령별 인구 컬럼
    total_columns = [
        col
        for col in df.columns
        if col.startswith("계_")
    ]


    # 65세 이상 연령 찾기
    elderly_columns = []

    for col in total_columns:

        match = re.match(
            r"계_(\d+)세",
            col
        )

        if match:

            age = int(
                match.group(1)
            )

            if age >= 65:

                elderly_columns.append(
                    col
                )


    # 전체 인구
    df["전체인구"] = df[
        total_columns
    ].sum(axis=1)


    # 65세 이상 인구
    df["고령인구"] = df[
        elderly_columns
    ].sum(axis=1)


    # 행정구역 코드
    df["시군구코드"] = (
        df["코드"]
        .astype(str)
        .str[:5]
    )


    # 시군구 단위 합산
    result = (

        df

        .groupby("시군구코드")

        [
            [
                "전체인구",
                "고령인구"
            ]
        ]

        .sum()

        .reset_index()
    )


    # 고령화율
    result["고령화율"] = (

        result["고령인구"]
        /
        result["전체인구"]
        *
        100

    ).round(2)


    return result


# =========================================================
# 지도 이름 데이터
# =========================================================

name_data = []

for feature in geojson["features"]:

    properties = feature["properties"]

    name_data.append({

        "시군구코드":
            str(properties["코드"]),

        "시군구":
            properties["시군구"],

        "시도":
            properties["시도"]

    })


names = pd.DataFrame(
    name_data
)


# =========================================================
# 현재 연도 데이터
# =========================================================

current = calculate_population(
    latest_year
)


current = current.merge(
    names,
    on="시군구코드",
    how="left"
)


# =========================================================
# 제목
# =========================================================

st.title(
    "🇰🇷 대한민국 고령화 데이터 분석"
)

st.markdown(
    "전국 시군구의 **65세 이상 인구 비율**을 데이터로 비교하고 "
    "지역별 고령화 현상을 탐색합니다."
)


# =========================================================
# 핵심 지표
# =========================================================

national_population = (
    current["전체인구"].sum()
)

national_elderly = (
    current["고령인구"].sum()
)

national_rate = (
    national_elderly
    /
    national_population
    *
    100
)


highest = current.loc[
    current["고령화율"].idxmax()
]

lowest = current.loc[
    current["고령화율"].idxmin()
]


c1, c2, c3, c4 = st.columns(4)


with c1:

    st.metric(
        "분석 기준 연도",
        f"{latest_year}년"
    )


with c2:

    st.metric(
        "전국 고령화율",
        f"{national_rate:.2f}%"
    )


with c3:

    st.metric(
        "가장 높은 지역",
        highest["시군구"],
        f"{highest['고령화율']:.2f}%"
    )


with c4:

    st.metric(
        "가장 낮은 지역",
        lowest["시군구"],
        f"{lowest['고령화율']:.2f}%"
    )


# =========================================================
# 지도
# =========================================================

st.divider()

st.header(
    "🗺️ 전국 시군구별 고령화율"
)

st.caption(
    "65세 이상 인구가 전체 인구에서 차지하는 비율"
)


# 단계 구분
bins = [
    0,
    19,
    23,
    28,
    38,
    100
]

labels = [
    "19% 미만",
    "19~23%",
    "23~28%",
    "28~38%",
    "38% 이상"
]


current["고령화단계"] = pd.cut(
    current["고령화율"],
    bins=bins,
    labels=labels,
    right=False
)


fig_map = px.choropleth(

    current,

    geojson=geojson,

    locations="시군구코드",

    featureidkey="properties.코드",

    color="고령화단계",

    category_orders={
        "고령화단계": labels
    },

    color_discrete_sequence=[
        "#E8F3F8",
        "#B9DCEB",
        "#78B9D0",
        "#E6A86B",
        "#C95A4A"
    ],

    hover_name="시군구",

    hover_data={

        "시도": True,

        "고령화율": True,

        "전체인구": ":,",

        "고령인구": ":,",

        "시군구코드": False,

        "고령화단계": False
    },

    labels={

        "시도": "시도",

        "고령화율":
            "고령화율 (%)",

        "전체인구":
            "전체 인구",

        "고령인구":
            "65세 이상 인구"
    }
)


fig_map.update_geos(
    fitbounds="locations",
    visible=False
)


fig_map.update_layout(
    height=720,

    margin=dict(
        l=0,
        r=0,
        t=20,
        b=0
    ),

    legend_title_text="고령화율"
)


st.plotly_chart(
    fig_map,
    width="stretch"
)


# =========================================================
# TOP / LOW
# =========================================================

st.divider()

st.header(
    "📊 지역별 고령화율 비교"
)


left, right = st.columns(2)


table_columns = [
    "시도",
    "시군구",
    "고령화율"
]


with left:

    st.subheader(
        "🔴 고령화율이 높은 지역"
    )

    top10 = (

        current

        .nlargest(
            10,
            "고령화율"
        )

        [table_columns]

        .reset_index(drop=True)
    )

    top10.index = (
        top10.index + 1
    )

    st.dataframe(
        top10,
        width="stretch"
    )


with right:

    st.subheader(
        "🔵 고령화율이 낮은 지역"
    )

    low10 = (

        current

        .nsmallest(
            10,
            "고령화율"
        )

        [table_columns]

        .reset_index(drop=True)
    )

    low10.index = (
        low10.index + 1
    )

    st.dataframe(
        low10,
        width="stretch"
    )


# =========================================================
# 고령화율 분포
# =========================================================

st.divider()

st.header(
    "📈 전국 고령화율 분포"
)

st.caption(
    "각 시군구의 고령화율이 어느 구간에 집중되어 있는지 확인합니다."
)


fig_hist = px.histogram(

    current,

    x="고령화율",

    nbins=25,

    labels={
        "고령화율":
            "고령화율 (%)",
        "count":
            "시군구 수"
    },

    title="시군구별 고령화율 분포"

)


fig_hist.add_vline(
    x=national_rate,
    line_dash="dash",
    annotation_text=(
        f"전국 평균 {national_rate:.2f}%"
    )
)


fig_hist.update_layout(
    height=500
)


st.plotly_chart(
    fig_hist,
    width="stretch"
)


# =========================================================
# 지역 상세 분석
# =========================================================

st.divider()

st.header(
    "🔎 지역 상세 분석"
)


region_names = sorted(

    (
        current["시도"]
        + " "
        + current["시군구"]
    )

    .dropna()

    .unique()
)


selected_region = st.selectbox(
    "지역",
    region_names
)


region = current[
    (
        current["시도"]
        + " "
        + current["시군구"]
    )
    == selected_region
].iloc[0]


r1, r2, r3 = st.columns(3)


with r1:

    st.metric(
        "전체 인구",
        f"{int(region['전체인구']):,}명"
    )


with r2:

    st.metric(
        "65세 이상 인구",
        f"{int(region['고령인구']):,}명"
    )


with r3:

    difference = (
        region["고령화율"]
        - national_rate
    )

    st.metric(
        "고령화율",
        f"{region['고령화율']:.2f}%",
        f"{difference:+.2f}%p (전국 대비)"
    )


# =========================================================
# 연도별 변화
# =========================================================

st.divider()

st.header(
    "📅 연도에 따른 고령화율 변화"
)

st.caption(
    "같은 지역의 고령화율이 시간에 따라 어떻게 변했는지 확인합니다."
)


trend_code = region[
    "시군구코드"
]


trend_data = []


for year in years:

    year_df = calculate_population(
        year
    )

    target = year_df[
        year_df["시군구코드"]
        == trend_code
    ]

    if not target.empty:

        trend_data.append({

            "연도":
                year,

            "고령화율":
                target.iloc[0][
                    "고령화율"
                ]

        })


trend_df = pd.DataFrame(
    trend_data
)


fig_trend = px.line(

    trend_df,

    x="연도",

    y="고령화율",

    markers=True,

    labels={

        "연도":
            "연도",

        "고령화율":
            "고령화율 (%)"
    },

    title=(
        f"{selected_region}의 고령화율 변화"
    )
)


fig_trend.update_layout(
    height=500
)


st.plotly_chart(
    fig_trend,
    width="stretch"
)


# =========================================================
# 탐구 포인트
# =========================================================

st.divider()

st.header(
    "💡 데이터에서 생각해 볼 질문"
)

q1, q2 = st.columns(2)


with q1:

    st.markdown("""
### ① 지역 차이

왜 같은 시점에 존재하는 지역들 사이에서도
고령화율에 큰 차이가 나타날까?

- 인구 이동
- 산업 구조
- 도시 규모
- 주거 환경
- 출생률 등의 요인을 추가로 탐색할 수 있다.
""")


with q2:

    st.markdown("""
### ② 시간적 변화

한 지역의 고령화율은 시간이 지나면서
어떤 방향으로 변화하는가?

특정 지역의 변화 속도가 전국 평균과
어떻게 다른지도 비교할 수 있다.
""")


# =========================================================
# 데이터 출처
# =========================================================

st.divider()

st.caption(
    "인구 데이터: 행정구역별 연도별 주민등록 인구 데이터"
)

st.caption(
    "지도 경계: 시군구 GeoJSON 데이터"
)

st.caption(
    "※ 고령화율 = 65세 이상 인구 ÷ 전체 인구 × 100"
)
