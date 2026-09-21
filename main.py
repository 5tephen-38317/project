import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="전국 고령화 · 학원가 지도",
    layout="wide"
)

st.title("🗺️ 전국 고령화 · 학원가 지도")
st.caption(
    "시군구별 고령화율과 학원 분포를 비교하여 지역별 교육 인프라를 분석합니다."
)

POP_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/population_yearly.csv.gz"
)

GEO_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/boundaries/sigungu_kr.geojson"
)


# ============================================================
# 1. 주민등록 인구 데이터
# ============================================================

@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():

    return pd.read_csv(
        POP_URL,
        dtype={"코드": str}
    )


# ============================================================
# 2. 지도 경계 데이터
# ============================================================

@st.cache_data(show_spinner="지도 경계를 불러오는 중입니다...")
def load_geojson():

    response = requests.get(
        GEO_URL,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# 3. 학원 데이터
#
# academy.csv를 app.py와 같은 폴더에 넣어주세요.
#
# 주소가 들어 있는 열을 자동으로 찾습니다.
# ============================================================

@st.cache_data(show_spinner="학원 데이터를 불러오는 중입니다...")
def load_academy():

    try:

        df = pd.read_csv(
            "academy.csv",
            encoding="utf-8-sig"
        )

    except UnicodeDecodeError:

        df = pd.read_csv(
            "academy.csv",
            encoding="cp949"
        )

    return df


# ============================================================
# 데이터 불러오기
# ============================================================

try:

    population = load_population()

except Exception as e:

    st.error("인구 데이터를 불러오지 못했습니다.")
    st.exception(e)
    st.stop()


try:

    geojson = load_geojson()

except Exception as e:

    st.error("지도 경계 데이터를 불러오지 못했습니다.")
    st.exception(e)
    st.stop()


# ============================================================
# 4. 최신 연도 인구 데이터 계산
# ============================================================

latest_year = int(
    population["연도"].max()
)

df = population[
    population["연도"] == latest_year
].copy()


# ============================================================
# 5. 전체 인구 / 65세 이상 인구 계산
# ============================================================

total_cols = [
    c for c in df.columns
    if c.startswith("계_")
]


def age_of(col):

    m = re.match(
        r"계_(\d+)세",
        col
    )

    return int(m.group(1)) if m else None


elderly_cols = [
    c for c in total_cols
    if age_of(c) is not None
    and age_of(c) >= 65
]


df["전체인구"] = df[
    total_cols
].sum(axis=1)


df["고령인구"] = df[
    elderly_cols
].sum(axis=1)


# ============================================================
# 6. 읍면동 → 시군구 코드
# ============================================================

df["시군구코드"] = (
    df["코드"]
    .astype(str)
    .str[:5]
)


grouped = (
    df
    .groupby("시군구코드")[
        ["전체인구", "고령인구"]
    ]
    .sum()
    .reset_index()
)


grouped["고령화율"] = (
    grouped["고령인구"]
    / grouped["전체인구"]
    * 100
).round(2)


# ============================================================
# 7. 지도에서 시군구 이름 가져오기
# ============================================================

names = pd.DataFrame([

    {
        "시군구코드": str(
            f["properties"]["코드"]
        ),

        "시군구": f["properties"]["시군구"],

        "시도": f["properties"]["시도"]
    }

    for f in geojson["features"]

])


merged = grouped.merge(
    names,
    on="시군구코드",
    how="left"
)


# ============================================================
# 8. 고령화 단계
# ============================================================

BINS = [
    0,
    19,
    23,
    28,
    38,
    100
]

LABELS = [
    "19% 미만",
    "19~23%",
    "23~28%",
    "28~38%",
    "38% 이상"
]

COLORS = {

    "19% 미만": "#fee6ce",

    "19~23%": "#fdc086",

    "23~28%": "#f79646",

    "28~38%": "#e8590c",

    "38% 이상": "#a63603"
}


merged["단계"] = pd.cut(
    merged["고령화율"],
    bins=BINS,
    labels=LABELS,
    right=False
)


# ============================================================
# 9. 고령화 지도
# ============================================================

st.header("👵 전국 고령화 지도")

fig_old = px.choropleth(

    merged,

    geojson=geojson,

    locations="시군구코드",

    featureidkey="properties.코드",

    color="단계",

    category_orders={
        "단계": LABELS
    },

    color_discrete_map=COLORS,

    hover_name="시군구",

    hover_data={

        "고령화율": True,

        "시도": True,

        "전체인구": True,

        "고령인구": True,

        "시군구코드": False,

        "단계": False
    },

    labels={
        "고령화율": "65세 이상 비율(%)",
        "전체인구": "전체 인구",
        "고령인구": "65세 이상 인구"
    }
)


fig_old.update_geos(
    fitbounds="locations",
    visible=False
)


fig_old.update_layout(

    margin=dict(
        l=0,
        r=0,
        t=10,
        b=0
    ),

    height=700,

    legend_title_text=(
        f"65세 이상 비율 ({latest_year}년)"
    )
)


st.plotly_chart(
    fig_old,
    use_container_width=True
)


# ============================================================
# 10. 고령화 TOP / LOW
# ============================================================

c1, c2 = st.columns(2)


cols_old = [
    "시도",
    "시군구",
    "고령화율"
]


with c1:

    st.subheader(
        "🔴 고령화율 높은 지역 TOP 10"
    )

    st.dataframe(

        merged
        .nlargest(
            10,
            "고령화율"
        )[cols_old]
        .reset_index(drop=True),

        use_container_width=True
    )


with c2:

    st.subheader(
        "🟢 고령화율 낮은 지역 TOP 10"
    )

    st.dataframe(

        merged
        .nsmallest(
            10,
            "고령화율"
        )[cols_old]
        .reset_index(drop=True),

        use_container_width=True
    )


# ============================================================
# 11. 학원 데이터
# ============================================================

st.divider()

st.header("🏫 전국 학원가 분석")


try:

    academy = load_academy()

except FileNotFoundError:

    st.warning(
        """
        `academy.csv` 파일을 찾을 수 없습니다.

        공공데이터포털의 학원·교습소 데이터를 다운로드한 뒤
        파일명을 `academy.csv`로 변경하여
        `app.py`와 같은 폴더에 넣어주세요.
        """
    )

    st.stop()

except Exception as e:

    st.error(
        "학원 데이터를 읽는 과정에서 오류가 발생했습니다."
    )

    st.exception(e)

    st.stop()


# ============================================================
# 12. 학원 데이터의 주소 열 자동 탐색
# ============================================================

possible_address_columns = [

    "주소",

    "도로명주소",

    "소재지주소",

    "학원주소",

    "소재지도로명주소",

    "도로명전체주소",

    "주소(도로명)"

]


address_column = None


for col in possible_address_columns:

    if col in academy.columns:

        address_column = col

        break


if address_column is None:

    st.error(
        """
        학원 데이터에서 주소 열을 찾지 못했습니다.

        현재 CSV의 열 이름:
        """
    )

    st.write(
        list(academy.columns)
    )

    st.stop()


# ============================================================
# 13. 주소에서 시도 / 시군구 추출
# ============================================================

academy[address_column] = (
    academy[address_column]
    .fillna("")
    .astype(str)
)


def extract_region(address):

    address = address.strip()

    if not address:

        return None, None

    parts = address.split()

    if len(parts) < 2:

        return None, None

    sido = parts[0]

    sigungu = parts[1]

    # 특별시 / 광역시 / 특별자치시 / 도
    # 이름 처리

    sido_clean = sido

    # 세종특별자치시처럼
    # 시군구가 따로 없는 경우

    if (
        sido_clean == "세종특별자치시"
    ):

        return sido_clean, "세종특별자치시"


    return sido_clean, sigungu


academy[
    ["학원시도", "학원시군구"]
] = academy[
    address_column
].apply(
    lambda x: pd.Series(
        extract_region(x)
    )
)


# ============================================================
# 14. 시군구 이름 정리
# ============================================================

def normalize_sigungu(x):

    if pd.isna(x):

        return x

    x = str(x).strip()

    return x


academy["학원시군구"] = (
    academy["학원시군구"]
    .apply(normalize_sigungu)
)


merged["시군구"] = (
    merged["시군구"]
    .astype(str)
    .str.strip()
)


# ============================================================
# 15. 시도 + 시군구 기준으로 학원 수 계산
# ============================================================

academy_grouped = (

    academy
    .dropna(
        subset=[
            "학원시도",
            "학원시군구"
        ]
    )

    .groupby(
        [
            "학원시도",
            "학원시군구"
        ]
    )

    .size()

    .reset_index(
        name="학원수"
    )
)


# ============================================================
# 16. 지도 데이터와 연결
# ============================================================

merged["검색시도"] = (
    merged["시도"]
    .astype(str)
    .str.strip()
)


merged["검색시군구"] = (
    merged["시군구"]
    .astype(str)
    .str.strip()
)


academy_grouped["학원시도"] = (
    academy_grouped["학원시도"]
    .astype(str)
    .str.strip()
)


academy_grouped["학원시군구"] = (
    academy_grouped["학원시군구"]
    .astype(str)
    .str.strip()
)


academy_merged = merged.merge(

    academy_grouped,

    left_on=[
        "검색시도",
        "검색시군구"
    ],

    right_on=[
        "학원시도",
        "학원시군구"
    ],

    how="left"
)


academy_merged["학원수"] = (
    academy_merged["학원수"]
    .fillna(0)
    .astype(int)
)


# ============================================================
# 17. 학원 밀도 계산
#
# 학원 밀도 =
# 학원 수 / 전체 인구 × 1000
# ============================================================

academy_merged["학원밀도"] = (

    academy_merged["학원수"]

    / academy_merged["전체인구"]

    * 1000

).round(2)


# ============================================================
# 18. 학원 지도용 분위수 구간
# ============================================================

try:

    academy_merged[
        "학원수구간"
    ] = pd.qcut(

        academy_merged["학원수"],

        q=5,

        labels=[
            "매우 적음",
            "적음",
            "보통",
            "많음",
            "매우 많음"
        ],

        duplicates="drop"

    )

except Exception:

    academy_merged[
        "학원수구간"
    ] = "자료 부족"


# ============================================================
# 19. 학원 밀도 구간
# ============================================================

try:

    academy_merged[
        "학원밀도구간"
    ] = pd.qcut(

        academy_merged["학원밀도"],

        q=5,

        labels=[
            "매우 낮음",
            "낮음",
            "보통",
            "높음",
            "매우 높음"
        ],

        duplicates="drop"

    )

except Exception:

    academy_merged[
        "학원밀도구간"
    ] = "자료 부족"


# ============================================================
# 20. 학원 지도 탭
# ============================================================

tab1, tab2 = st.tabs(
    [
        "🏫 학원 수",
        "📊 인구 대비 학원 밀도"
    ]
)


# ============================================================
# 21. 학원 수 지도
# ============================================================

with tab1:

    st.subheader(
        "시군구별 학원 수"
    )

    fig_academy = px.choropleth(

        academy_merged,

        geojson=geojson,

        locations="시군구코드",

        featureidkey="properties.코드",

        color="학원수",

        color_continuous_scale="Oranges",

        hover_name="시군구",

        hover_data={

            "시도": True,

            "학원수": True,

            "전체인구": True,

            "학원밀도": True,

            "시군구코드": False
        },

        labels={

            "학원수": "학원 수",

            "전체인구": "전체 인구",

            "학원밀도":
                "인구 1,000명당 학원 수"
        }
    )


    fig_academy.update_geos(

        fitbounds="locations",

        visible=False
    )


    fig_academy.update_layout(

        margin=dict(
            l=0,
            r=0,
            t=10,
            b=0
        ),

        height=700
    )


    st.plotly_chart(

        fig_academy,

        use_container_width=True
    )


# ============================================================
# 22. 학원 밀도 지도
# ============================================================

with tab2:

    st.subheader(
        "인구 1,000명당 학원 수"
    )

    st.caption(
        "학원 수 ÷ 전체 인구 × 1,000"
    )


    fig_density = px.choropleth(

        academy_merged,

        geojson=geojson,

        locations="시군구코드",

        featureidkey="properties.코드",

        color="학원밀도",

        color_continuous_scale="Oranges",

        hover_name="시군구",

        hover_data={

            "시도": True,

            "학원수": True,

            "전체인구": True,

            "학원밀도": True,

            "시군구코드": False
        },

        labels={

            "학원수": "학원 수",

            "전체인구": "전체 인구",

            "학원밀도":
                "인구 1,000명당 학원 수"
        }
    )


    fig_density.update_geos(

        fitbounds="locations",

        visible=False
    )


    fig_density.update_layout(

        margin=dict(
            l=0,
            r=0,
            t=10,
            b=0
        ),

        height=700
    )


    st.plotly_chart(

        fig_density,

        use_container_width=True
    )


# ============================================================
# 23. 학원가 TOP 10
# ============================================================

st.subheader(
    "📊 지역별 학원가 TOP 10"
)


c3, c4 = st.columns(2)


academy_cols = [

    "시도",

    "시군구",

    "학원수",

    "학원밀도"

]


with c3:

    st.markdown(
        "### 🏫 학원 수가 많은 지역 TOP 10"
    )

    st.dataframe(

        academy_merged

        .nlargest(
            10,
            "학원수"
        )[academy_cols]

        .reset_index(
            drop=True
        ),

        use_container_width=True
    )


with c4:

    st.markdown(
        "### 📈 인구 대비 학원 밀도가 높은 지역 TOP 10"
    )

    st.dataframe(

        academy_merged

        .nlargest(
            10,
            "학원밀도"
        )[academy_cols]

        .reset_index(
            drop=True
        ),

        use_container_width=True
    )


# ============================================================
# 24. 고령화율 × 학원밀도 산점도
# ============================================================

st.divider()

st.header(
    "👵 고령화율 × 🏫 학원밀도"
)

st.write(
    "지역의 고령화 정도와 인구 대비 학원 밀도의 관계를 비교합니다."
)


scatter = px.scatter(

    academy_merged,

    x="고령화율",

    y="학원밀도",

    size="학원수",

    hover_name="시군구",

    hover_data={

        "시도": True,

        "고령화율": True,

        "학원수": True,

        "학원밀도": True,

        "전체인구": True
    },

    labels={

        "고령화율":
            "65세 이상 인구 비율(%)",

        "학원밀도":
            "인구 1,000명당 학원 수",

        "학원수":
            "학원 수",

        "전체인구":
            "전체 인구"
    },

    title=(
        "시군구별 고령화율과 학원 밀도"
    )
)


scatter.update_layout(

    height=650,

    margin=dict(
        l=20,
        r=20,
        t=60,
        b=20
    )
)


st.plotly_chart(

    scatter,

    use_container_width=True
)


# ============================================================
# 25. 해석 주의사항
# ============================================================

st.info(
    """
📌 해석 시 주의

고령화율과 학원 밀도 사이에 통계적 관계가 나타나더라도
그 자체만으로 고령화가 학원 수를 감소시키거나 증가시킨다는
인과관계를 의미하지 않습니다.

지역의 인구 규모, 학생 인구, 소득 수준, 도시 규모,
교육 수요 등 다양한 요인이 함께 영향을 줄 수 있습니다.
"""
)


# ============================================================
# 26. 데이터 기준
# ============================================================

st.caption(
    f"주민등록 인구 기준 연도: {latest_year}년"
)

st.caption(
    "학원 데이터는 academy.csv에 포함된 자료 기준입니다."
)
