from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass
class FilterState:
    date_start: date
    date_end: date
    regions: list[str]
    customer_types: list[str]
    sales_reps: list[str]
    product_groups: list[str]


@dataclass
class KPIResult:
    total_revenue: float
    total_orders: float
    total_receivable: float
    transaction_count: int
    completion_rate: float
    positive_activity_rate: float
    revenue_delta: float | None
    orders_delta: float | None
    receivable_delta: float | None
    transaction_delta: float | None


def apply_sales_filters(sales: pd.DataFrame, filters: FilterState) -> pd.DataFrame:
    df = sales.copy()
    if "수주일" in df.columns:
        mask = (df["수주일"].dt.date >= filters.date_start) & (
            df["수주일"].dt.date <= filters.date_end
        )
        df = df[mask]
    if filters.regions:
        df = df[df["지역"].isin(filters.regions)]
    if filters.customer_types:
        df = df[df["거래처유형"].isin(filters.customer_types)]
    if filters.sales_reps:
        df = df[df["담당영업"].isin(filters.sales_reps)]
    if filters.product_groups:
        df = df[df["제품군"].isin(filters.product_groups)]
    return df


def apply_customer_filters(customers: pd.DataFrame, filters: FilterState) -> pd.DataFrame:
    df = customers.copy()
    if filters.regions:
        df = df[df["지역"].isin(filters.regions)]
    if filters.customer_types:
        df = df[df["거래처유형"].isin(filters.customer_types)]
    return df


def apply_activity_filters(
    activities: pd.DataFrame,
    customers: pd.DataFrame | None = None,
    sales: pd.DataFrame | None = None,
    filters: FilterState | None = None,
) -> pd.DataFrame:
    if filters is None:
        return activities
    if customers is not None and sales is not None:
        return apply_activity_filters_with_context(
            activities, customers, sales, filters
        )
    df = activities.copy()
    if "활동일" in df.columns:
        mask = (df["활동일"].dt.date >= filters.date_start) & (
            df["활동일"].dt.date <= filters.date_end
        )
        df = df[mask]
    if filters.sales_reps:
        df = df[df["담당영업"].isin(filters.sales_reps)]
    return df


def apply_activity_filters_with_context(
    activities: pd.DataFrame,
    customers: pd.DataFrame,
    sales: pd.DataFrame,
    filters: FilterState,
) -> pd.DataFrame:
    df = activities.copy()
    if "활동일" in df.columns:
        mask = (df["활동일"].dt.date >= filters.date_start) & (
            df["활동일"].dt.date <= filters.date_end
        )
        df = df[mask]
    if filters.sales_reps:
        df = df[df["담당영업"].isin(filters.sales_reps)]

    if filters.regions or filters.customer_types:
        cust_filtered = apply_customer_filters(customers, filters)
        valid_names = set(cust_filtered["거래처명"])
        sales_filtered = apply_sales_filters(sales, filters)
        valid_names.update(sales_filtered["거래처명"].unique())
        df = df[df["거래처명"].isin(valid_names)]

    return df


def _period_delta(
    sales: pd.DataFrame,
    filters: FilterState,
    metric_fn,
) -> float | None:
    if "수주일" not in sales.columns or sales["수주일"].isna().all():
        return None

    period_days = (filters.date_end - filters.date_start).days + 1
    prev_end = pd.Timestamp(filters.date_start) - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=period_days - 1)

    current = apply_sales_filters(
        sales,
        FilterState(
            date_start=filters.date_start,
            date_end=filters.date_end,
            regions=filters.regions,
            customer_types=filters.customer_types,
            sales_reps=filters.sales_reps,
            product_groups=filters.product_groups,
        ),
    )
    previous = apply_sales_filters(
        sales,
        FilterState(
            date_start=prev_start.date(),
            date_end=prev_end.date(),
            regions=filters.regions,
            customer_types=filters.customer_types,
            sales_reps=filters.sales_reps,
            product_groups=filters.product_groups,
        ),
    )

    curr_val = metric_fn(current)
    prev_val = metric_fn(previous)
    if prev_val == 0:
        return None
    return (curr_val - prev_val) / prev_val * 100


def compute_kpis(
    sales: pd.DataFrame,
    activities: pd.DataFrame,
    filters: FilterState,
) -> KPIResult:
    filtered_sales = apply_sales_filters(sales, filters)
    filtered_activities = apply_activity_filters(
        activities, customers=None, sales=None, filters=filters
    )

    total_revenue = filtered_sales["매출금액"].sum()
    total_orders = filtered_sales["수주금액"].sum()
    total_receivable = filtered_sales["미수금"].sum()
    transaction_count = len(filtered_sales)

    if transaction_count > 0:
        completion_rate = (
            (filtered_sales["수주상태"] == "완료").sum() / transaction_count * 100
        )
    else:
        completion_rate = 0.0

    if len(filtered_activities) > 0:
        positive_activity_rate = (
            (filtered_activities["활동결과"] == "긍정").sum()
            / len(filtered_activities)
            * 100
        )
    else:
        positive_activity_rate = 0.0

    return KPIResult(
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_receivable=total_receivable,
        transaction_count=transaction_count,
        completion_rate=completion_rate,
        positive_activity_rate=positive_activity_rate,
        revenue_delta=_period_delta(
            sales, filters, lambda df: df["매출금액"].sum()
        ),
        orders_delta=_period_delta(
            sales, filters, lambda df: df["수주금액"].sum()
        ),
        receivable_delta=_period_delta(
            sales, filters, lambda df: df["미수금"].sum()
        ),
        transaction_delta=_period_delta(sales, filters, lambda df: len(df)),
    )


def generate_insights(
    sales: pd.DataFrame,
    customers: pd.DataFrame,
    activities: pd.DataFrame,
    filters: FilterState,
) -> list[tuple[str, str]]:
    """Returns list of (severity, message) where severity is success/info/warning."""
    insights: list[tuple[str, str]] = []
    filtered_sales = apply_sales_filters(sales, filters)
    filtered_customers = apply_customer_filters(customers, filters)
    filtered_activities = apply_activity_filters_with_context(
        activities, customers, sales, filters
    )

    if len(filtered_sales) == 0:
        insights.append(("info", "선택한 필터 조건에 해당하는 매출 데이터가 없습니다."))
        return insights

    if "분기" in filtered_sales.columns:
        quarters = sorted(filtered_sales["분기"].dropna().unique())
        if len(quarters) >= 2:
            curr_q, prev_q = quarters[-1], quarters[-2]
            curr = filtered_sales[filtered_sales["분기"] == curr_q]
            prev = filtered_sales[filtered_sales["분기"] == prev_q]

            for col_name, group_col in [("지역", "지역"), ("제품군", "제품군")]:
                curr_grp = curr.groupby(group_col)["매출금액"].sum()
                prev_grp = prev.groupby(group_col)["매출금액"].sum()
                for key in curr_grp.index:
                    c_val = curr_grp.get(key, 0)
                    p_val = prev_grp.get(key, 0)
                    if p_val > 0:
                        change = (c_val - p_val) / p_val * 100
                        if change >= 20:
                            insights.append(
                                (
                                    "success",
                                    f"{col_name} '{key}' 매출이 전분기({prev_q}→{curr_q}) 대비 {change:.1f}% 증가했습니다.",
                                )
                            )
                        elif change <= -20:
                            insights.append(
                                (
                                    "warning",
                                    f"{col_name} '{key}' 매출이 전분기({prev_q}→{curr_q}) 대비 {abs(change):.1f}% 감소했습니다.",
                                )
                            )

    receivable_by_customer = (
        filtered_sales.groupby("거래처명")["미수금"].sum().sort_values(ascending=False)
    )
    top_receivable = receivable_by_customer[receivable_by_customer > 0].head(3)
    for name, amount in top_receivable.items():
        insights.append(
            (
                "warning",
                f"미수금 상위 거래처: '{name}' — {amount:,.0f}원",
            )
        )

    if len(filtered_sales) > 0:
        cancel_rate = (
            filtered_sales.groupby("제품군")
            .apply(
                lambda g: (g["수주상태"] == "취소").sum() / len(g) * 100,
                include_groups=False,
            )
            .sort_values(ascending=False)
        )
        high_cancel = cancel_rate[cancel_rate >= 15]
        for product, rate in high_cancel.head(3).items():
            insights.append(
                (
                    "warning",
                    f"제품군 '{product}' 취소율이 {rate:.1f}%로 높습니다.",
                )
            )

        region_cancel = (
            filtered_sales.groupby("지역")
            .apply(
                lambda g: (g["수주상태"] == "취소").sum() / len(g) * 100,
                include_groups=False,
            )
            .sort_values(ascending=False)
        )
        high_region_cancel = region_cancel[region_cancel >= 15]
        for region, rate in high_region_cancel.head(2).items():
            insights.append(
                (
                    "warning",
                    f"지역 '{region}' 취소율이 {rate:.1f}%로 높습니다.",
                )
            )

    if len(filtered_activities) > 0:
        rep_negative = (
            filtered_activities.groupby("담당영업")
            .apply(
                lambda g: (g["활동결과"].isin(["부정", "보류"])).sum() / len(g) * 100,
                include_groups=False,
            )
            .sort_values(ascending=False)
        )
        for rep, rate in rep_negative[rep_negative >= 50].head(3).items():
            insights.append(
                (
                    "warning",
                    f"담당영업 '{rep}'의 부정·보류 활동 비율이 {rate:.1f}%입니다.",
                )
            )

    vip_customers = filtered_customers[filtered_customers["등급"] == "VIP"]
    if len(vip_customers) > 0 and len(filtered_activities) > 0:
        active_names = set(filtered_activities["거래처명"])
        for _, row in vip_customers.iterrows():
            name = row["거래처명"]
            base_name = name.split()[0] if name else ""
            has_activity = name in active_names or any(
                base_name in a for a in active_names
            )
            if not has_activity:
                insights.append(
                    (
                        "info",
                        f"VIP 거래처 '{name}'에 대한 선택 기간 내 영업 활동이 없습니다.",
                    )
                )

    if not insights:
        insights.append(
            ("success", "현재 필터 조건에서 특별한 이상 징후가 발견되지 않았습니다.")
        )

    return insights
