import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="전국 고령화 지도 & 타임라인", layout="wide")
st.title("🗺️ 전국 연도별 고령화율 지도")
st.caption("연도별 슬라이더를 조절하여 시군구별 65세 이상 인구 비율 변화를 확인해보세요.")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():
    return pd.read_csv(POP_URL, dtype={"코드": str})

@st.cache_data(show_spinner="지도 경계를 불러오는 중입니다...")
def load_geojson():
    return requests.get(GEO_URL, timeout=30).json()

df = load_population()
geojson = load_geojson()

# 1. 연도 선택 슬라이더 (사용자가 연도를 조절할 수 있도록 변경)
years = sorted(df["연도"].unique())
selected_year = st.slider(
    "📅 조회할 연도를 선택하세요",
    min_value=int(min(years)),
    max_value=int(max(years)),
    value=int(max(years)),
    step=1
)

df_year = df[df["연도"] == selected_year].copy()

# 2. 인구 계산
total_cols = [c for c in df_year.columns if c.startswith("계_")]

def age_of(col):
    m = re.match(r"계_(\d+)세", col)
    return int(m.group(1)) if m else None

elderly_cols = [c for c in total_cols if age_of(c) is not None and age_of(c) >= 65]

df_year["전체인구"] = df_year[total_cols].sum(axis=1)
df_year["고령인구"] = df_year[elderly_cols].sum(axis=1)

# 3. 시군구 단위 집계
df_year["시군구코드"] = df_year["코드"].str[:5]
grouped = df_year.groupby("시군구코드")[["전체인구", "고령인구"]].sum().reset_index()
grouped["고령화율"] = (grouped["고령인구"] / grouped["전체인구"] * 100).round(2)

# GeoJSON 매핑
names = pd.DataFrame([
    {
        "시군구코드": str(f["properties"]["코드"]),
        "시군구": f["properties"]["시군구"],
        "시도": f["properties"]["시도"],
    }
    for f in geojson["features"]
])
merged = grouped.merge(names, on="시군구코드", how="left")

# 4. 상단 요약 지표 (Metric Cards)
m1, m2, m3 = st.columns(3)
avg_rate = (merged["고령인구"].sum() / merged["전체인구"].sum() * 100).round(2)
max_row = merged.loc[merged["고령화율"].idxmax()]
min_row = merged.loc[merged["고령화율"].idxmin()]

m1.metric(f"{selected_year}년 전국 평균 고령화율", f"{avg_rate}%")
m2.metric("고령화율 가장 높은 곳", f"{max_row['시도']} {max_row['시군구']}", f"{max_row['고령화율']}%")
m3.metric("고령화율 가장 낮은 곳", f"{min_row['시도']} {min_row['시군구']}", f"{min_row['고령화율']}%")

st.markdown("---")

# 5. 단계구분도 (연속 스펙트럼 색상으로 변경하여 변화를 자연스럽게 표현)
fig = px.choropleth(
    merged,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="고령화율",
    range_color=[10, 45],  # 연도 변경 시 비교가 쉽도록 범주 범위 고정
    color_continuous_scale="Reds",
    hover_name="시군구",
    hover_data={"고령화율": ":.2f%", "시도": True, "전체인구": ":,", "고령인구": ":,", "시군구코드": False},
    labels={"고령화율": "고령화 비율(%)"}
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    margin=dict(l=0, r=0, t=10, b=0),
    height=650,
)

st.plotly_chart(fig, use_container_width=True)

# 6. 하단 순위 표
c1, c2 = st.columns(2)
cols = ["시도", "시군구", "고령화율", "전체인구", "고령인구"]

with c1:
    st.subheader("🔴 고령화율 높은 곳 TOP 10")
    st.dataframe(merged.nlargest(10, "고령화율")[cols].reset_index(drop=True), use_container_width=True)

with c2:
    st.subheader("🟢 고령화율 낮은 곳 TOP 10")
    st.dataframe(merged.nsmallest(10, "고령화율")[cols].reset_index(drop=True), use_container_width=True)
