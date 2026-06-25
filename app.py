import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.analytics import (
    FilterState,
    apply_activity_filters_with_context,
    apply_customer_filters,
    apply_sales_filters,
    compute_kpis,
    generate_insights,
)
from utils.data_loader import load_all_data

st.set_page_config(
    page_title="영업 대시보드",
    page_icon="📊",
    layout="wide",
)

COLORS = {
    "revenue": "#2563eb",
    "order": "#7c3aed",
    "receivable": "#dc2626",
    "positive": "#16a34a",
    "negative": "#dc2626",
    "hold": "#ea580c",
    "complete": "#16a34a",
    "progress": "#2563eb",
    "cancel": "#dc2626",
}

RESULT_COLORS = {"긍정": COLORS["positive"], "부정": COLORS["negative"], "보류": COLORS["hold"]}
STATUS_COLORS = {"완료": COLORS["complete"], "진행중": COLORS["progress"], "취소": COLORS["cancel"]}


def format_currency(value: float) -> str:
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:,.0f}"


def render_kpi_row(kpis) -> None:
    cols = st.columns(6)
    metrics = [
        ("총 매출", kpis.total_revenue, kpis.revenue_delta, format_currency),
        ("총 수주", kpis.total_orders, kpis.orders_delta, format_currency),
        ("미수금", kpis.total_receivable, kpis.receivable_delta, format_currency),
        ("거래 건수", kpis.transaction_count, kpis.transaction_delta, lambda v: f"{int(v):,}"),
        ("완료율", kpis.completion_rate, None, lambda v: f"{v:.1f}%"),
        ("긍정 활동률", kpis.positive_activity_rate, None, lambda v: f"{v:.1f}%"),
    ]
    for col, (label, value, delta, fmt) in zip(cols, metrics):
        with col:
            if delta is not None:
                st.metric(label, fmt(value), f"{delta:+.1f}%")
            else:
                st.metric(label, fmt(value))


def render_sales_tab(sales: pd.DataFrame) -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("분기별 매출 추이")
        if "분기" in sales.columns and len(sales) > 0:
            quarterly = (
                sales.groupby("분기", as_index=False)["매출금액"]
                .sum()
                .sort_values("분기")
            )
            fig = px.line(
                quarterly,
                x="분기",
                y="매출금액",
                markers=True,
                color_discrete_sequence=[COLORS["revenue"]],
            )
            fig.update_layout(yaxis_title="매출금액 (원)", xaxis_title="분기")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("표시할 매출 추이 데이터가 없습니다.")

        st.subheader("제품군별 매출")
        if len(sales) > 0:
            product = sales.groupby("제품군", as_index=False)["매출금액"].sum()
            fig = px.pie(
                product,
                names="제품군",
                values="매출금액",
                hole=0.4,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("지역별 매출")
        if len(sales) > 0:
            region = (
                sales.groupby("지역", as_index=False)["매출금액"]
                .sum()
                .sort_values("매출금액")
            )
            fig = px.bar(
                region,
                x="매출금액",
                y="지역",
                orientation="h",
                color_discrete_sequence=[COLORS["revenue"]],
            )
            fig.update_layout(xaxis_title="매출금액 (원)", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("수주상태 분포")
        if len(sales) > 0:
            status = sales.groupby(["지역", "수주상태"], as_index=False).size()
            fig = px.bar(
                status,
                x="지역",
                y="size",
                color="수주상태",
                color_discrete_map=STATUS_COLORS,
                barmode="stack",
            )
            fig.update_layout(yaxis_title="건수", xaxis_title="지역")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("담당영업별 실적")
    if len(sales) > 0:
        rep = (
            sales.groupby("담당영업", as_index=False)
            .agg(수주금액=("수주금액", "sum"), 매출금액=("매출금액", "sum"))
            .sort_values("매출금액", ascending=False)
        )
        fig = go.Figure()
        fig.add_trace(
            go.Bar(name="수주금액", x=rep["담당영업"], y=rep["수주금액"], marker_color=COLORS["order"])
        )
        fig.add_trace(
            go.Bar(name="매출금액", x=rep["담당영업"], y=rep["매출금액"], marker_color=COLORS["revenue"])
        )
        fig.update_layout(barmode="group", yaxis_title="금액 (원)", xaxis_title="담당영업")
        st.plotly_chart(fig, use_container_width=True)


def render_customer_tab(customers: pd.DataFrame) -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("등급별 거래처 수")
        if len(customers) > 0:
            grade_count = customers.groupby("등급", as_index=False).size()
            fig = px.bar(
                grade_count,
                x="등급",
                y="size",
                color="등급",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(yaxis_title="거래처 수", xaxis_title="등급", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("거래처유형별 누적매출")
        if len(customers) > 0:
            type_sales = customers.groupby("거래처유형", as_index=False)["누적매출"].sum()
            fig = px.bar(
                type_sales,
                x="거래처유형",
                y="누적매출",
                color="거래처유형",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig.update_layout(yaxis_title="누적매출 (원)", xaxis_title="", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("등급별 누적매출")
        if len(customers) > 0:
            grade_sales = customers.groupby("등급", as_index=False)["누적매출"].sum()
            fig = px.pie(
                grade_sales,
                names="등급",
                values="누적매출",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("지역별 고객 분포")
        if len(customers) > 0:
            region = customers.groupby("지역", as_index=False).size().sort_values("size")
            fig = px.bar(
                region,
                x="size",
                y="지역",
                orientation="h",
                color_discrete_sequence=[COLORS["revenue"]],
            )
            fig.update_layout(xaxis_title="거래처 수", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("TOP 10 거래처 (누적매출)")
    if len(customers) > 0:
        top10 = customers.nlargest(10, "누적매출").sort_values("누적매출")
        fig = px.bar(
            top10,
            x="누적매출",
            y="거래처명",
            orientation="h",
            color="등급",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(xaxis_title="누적매출 (원)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)


def render_activity_tab(activities: pd.DataFrame) -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("활동유형별 건수")
        if len(activities) > 0:
            act_type = activities.groupby("활동유형", as_index=False).size()
            fig = px.bar(
                act_type,
                x="활동유형",
                y="size",
                color="활동유형",
                color_discrete_sequence=px.colors.qualitative.Set1,
            )
            fig.update_layout(yaxis_title="건수", xaxis_title="", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("담당영업별 활동 현황")
        if len(activities) > 0:
            heatmap_data = pd.crosstab(
                activities["담당영업"], activities["활동결과"]
            )
            fig = px.imshow(
                heatmap_data,
                text_auto=True,
                color_continuous_scale="Blues",
                aspect="auto",
            )
            fig.update_layout(xaxis_title="활동결과", yaxis_title="담당영업")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("활동결과 분포")
        if len(activities) > 0:
            result = activities.groupby("활동결과", as_index=False).size()
            fig = px.pie(
                result,
                names="활동결과",
                values="size",
                color="활동결과",
                color_discrete_map=RESULT_COLORS,
            )
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("최근 활동 목록")
    if len(activities) > 0:
        recent = activities.sort_values("활동일", ascending=False)[
            ["활동일", "거래처명", "담당영업", "활동유형", "활동결과", "다음액션"]
        ]
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.info("표시할 활동 데이터가 없습니다.")


def render_insights_tab(
    sales: pd.DataFrame,
    customers: pd.DataFrame,
    activities: pd.DataFrame,
    filters: FilterState,
) -> None:
    st.subheader("자동 인사이트")
    insights = generate_insights(sales, customers, activities, filters)

    severity_fn = {
        "success": st.success,
        "info": st.info,
        "warning": st.warning,
    }
    for severity, message in insights:
        severity_fn.get(severity, st.info)(message)


def render_data_expander(
    sales: pd.DataFrame,
    customers: pd.DataFrame,
    activities: pd.DataFrame,
) -> None:
    with st.expander("원본 데이터 보기"):
        tab_s, tab_c, tab_a = st.tabs(["매출", "고객", "활동"])
        with tab_s:
            st.dataframe(sales, use_container_width=True, hide_index=True)
            st.download_button(
                "매출 CSV 다운로드",
                sales.to_csv(index=False).encode("utf-8-sig"),
                "filtered_sales.csv",
                "text/csv",
            )
        with tab_c:
            st.dataframe(customers, use_container_width=True, hide_index=True)
            st.download_button(
                "고객 CSV 다운로드",
                customers.to_csv(index=False).encode("utf-8-sig"),
                "filtered_customers.csv",
                "text/csv",
            )
        with tab_a:
            st.dataframe(activities, use_container_width=True, hide_index=True)
            st.download_button(
                "활동 CSV 다운로드",
                activities.to_csv(index=False).encode("utf-8-sig"),
                "filtered_activities.csv",
                "text/csv",
            )


def main() -> None:
    st.title("📊 영업 대시보드")
    st.caption("샘플데이터 폴더의 매출·고객·영업활동 데이터를 분석합니다.")

    try:
        with st.spinner("데이터를 불러오는 중..."):
            sales_raw, customers_raw, activities_raw = load_all_data()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    min_date = sales_raw["수주일"].min().date()
    max_date = sales_raw["수주일"].max().date()
    activity_min = activities_raw["활동일"].min().date()
    activity_max = activities_raw["활동일"].max().date()
    global_min = min(min_date, activity_min)
    global_max = max(max_date, activity_max)

    with st.sidebar:
        st.header("필터")
        date_range = st.date_input(
            "기간",
            value=(global_min, global_max),
            min_value=global_min,
            max_value=global_max,
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            date_start, date_end = date_range
        else:
            date_start = date_end = date_range if not isinstance(date_range, tuple) else date_range[0]

        regions = st.multiselect(
            "지역",
            sorted(sales_raw["지역"].dropna().unique()),
        )
        customer_types = st.multiselect(
            "거래처유형",
            sorted(sales_raw["거래처유형"].dropna().unique()),
        )
        sales_reps = st.multiselect(
            "담당영업",
            sorted(sales_raw["담당영업"].dropna().unique()),
        )
        product_groups = st.multiselect(
            "제품군",
            sorted(sales_raw["제품군"].dropna().unique()),
        )

    filters = FilterState(
        date_start=date_start,
        date_end=date_end,
        regions=regions,
        customer_types=customer_types,
        sales_reps=sales_reps,
        product_groups=product_groups,
    )

    filtered_sales = apply_sales_filters(sales_raw, filters)
    filtered_customers = apply_customer_filters(customers_raw, filters)
    filtered_activities = apply_activity_filters_with_context(
        activities_raw, customers_raw, sales_raw, filters
    )

    kpis = compute_kpis(sales_raw, activities_raw, filters)
    render_kpi_row(kpis)

    st.divider()

    tab_sales, tab_customer, tab_activity, tab_insights = st.tabs(
        ["매출 분석", "고객 분석", "영업 활동", "인사이트"]
    )

    with tab_sales:
        render_sales_tab(filtered_sales)
    with tab_customer:
        render_customer_tab(filtered_customers)
    with tab_activity:
        render_activity_tab(filtered_activities)
    with tab_insights:
        render_insights_tab(sales_raw, customers_raw, activities_raw, filters)

    render_data_expander(filtered_sales, filtered_customers, filtered_activities)


if __name__ == "__main__":
    main()
