# 🏡 AskVinny — Agent Performance Dashboard (Unified Period Selector)
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
from datetime import timedelta

# --- Page setup ---
st.set_page_config(page_title="AskVinny — Agent Performance", page_icon="🏡", layout="wide")
st.title("🏡 AskVinny — Agent Performance Dashboard")
st.markdown("Explore weekly performance, long-term trends, and conversion outcomes for each agent.")

# --- Database connection ---
engine = create_engine(
    "postgresql://neondb_owner:npg_NVGydXqe3ar6@ep-aged-field-adcu8co8-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"
)

# --- Load weekly aggregated data ---
@st.cache_data(ttl=3600)
def load_weekly_data():
    query = """
    WITH cleaned_viewings AS (
      SELECT
        "personId",
        "Agent",
        TO_DATE("Date", 'DD/MM/YYYY') AS viewing_date
      FROM viewings
      WHERE "personId" IS NOT NULL
    ),
    weekly AS (
      SELECT
        v."Agent" AS agent,
        DATE_TRUNC('week', v.viewing_date)::date AS week_start,
        COUNT(DISTINCT v."personId") AS total_viewings,
        COUNT(DISTINCT CASE WHEN p."Applied" IS NOT NULL THEN v."personId" END) AS applications,
        COUNT(DISTINCT CASE WHEN p."Status" = 'Current' THEN v."personId" END) AS tenants
      FROM cleaned_viewings v
      LEFT JOIN prospects p ON v."personId" = p."personId"
      GROUP BY 1, 2
    )
    SELECT
      agent,
      week_start,
      week_start + INTERVAL '6 days' AS week_end,
      total_viewings,
      applications,
      tenants,
      ROUND(applications::NUMERIC / NULLIF(total_viewings,0) * 100, 1) AS view_to_app_rate,
      ROUND(tenants::NUMERIC / NULLIF(applications,0) * 100, 1) AS app_to_tenant_rate,
      ROUND(tenants::NUMERIC / NULLIF(total_viewings,0) * 100, 1) AS total_conversion_rate
    FROM weekly
    ORDER BY week_start, agent;
    """
    return pd.read_sql(query, engine)

df = load_weekly_data()

# ==============================================================
# 🏆 ① Weekly Agent Rankings — Unified Period Selector
# ==============================================================

st.markdown("## 🏆 Agent Rankings")

view_mode = st.radio(
    "View performance by:",
    ["Week", "Month", "Custom range"],
    horizontal=True
)

if view_mode == "Week":
    selected_date = st.date_input("Select a week", value=df["week_start"].max())
    start_date = selected_date
    end_date = selected_date + timedelta(days=6)
    title_label = f"Week of {start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')}"

elif view_mode == "Month":
    selected_month = st.date_input("Select month", value=df["week_start"].max())
    start_date = selected_month.replace(day=1)
    end_date = (start_date + pd.offsets.MonthEnd(1)).date()
    title_label = f"{start_date.strftime('%B %Y')}"

else:
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start date", value=df["week_start"].min())
    with col2:
        end_date = st.date_input("End date", value=df["week_start"].max())
    title_label = f"{start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}"

# Filter data within selected period
period_df = df.query("@start_date <= week_start <= @end_date")

# Aggregate across selected range
agg_df = (
    period_df.groupby("agent", as_index=False)
    .agg({"total_viewings": "sum", "tenants": "sum"})
)

# Ensure all agents appear even if zero
all_agents = pd.DataFrame({"agent": sorted(df["agent"].unique())})
agg_df = all_agents.merge(agg_df, on="agent", how="left").fillna(0)

# Melt for bar chart
melted = agg_df.melt(
    id_vars=["agent"],
    value_vars=["total_viewings", "tenants"],
    var_name="Metric",
    value_name="Count"
)
melted["Metric"] = melted["Metric"].map({
    "total_viewings": "Viewings",
    "tenants": "Tenants"
})

# Sort by viewings
agent_order = agg_df.sort_values("total_viewings", ascending=False)["agent"]

fig_rank = px.bar(
    melted,
    x="agent",
    y="Count",
    color="Metric",
    barmode="group",
    category_orders={"agent": agent_order.tolist()},
    color_discrete_map={
        "Viewings": "#90CAF9",
        "Tenants": "#1565C0"
    },
    title=f"Viewings vs Tenants — {title_label}",
    labels={"agent": "Agent", "Count": "Count"}
)

fig_rank.update_layout(
    plot_bgcolor="white",
    yaxis_title="Count",
    xaxis_title=None,
    height=450,
    margin=dict(t=60, b=40, l=40, r=40),
)
st.plotly_chart(fig_rank, use_container_width=True)

# Add divider
st.markdown("<hr style='border-top: 2px solid #ffff; margin-top: 40px; margin-bottom: 30px;'>", unsafe_allow_html=True)

# ==============================================================
# 📈 ② Agent Deep Dive (same as before)
# ==============================================================

st.markdown("## 📈 Agents Deep Dive")
agents = sorted(df["agent"].unique())
selected_agent = st.selectbox("Select an agent to view trend:", agents)

agent_trend = df[df["agent"] == selected_agent]
fig_trend = px.line(
    agent_trend,
    x="week_start",
    y="total_conversion_rate",
    markers=True,
    color_discrete_sequence=["#1565C0"],
    labels={"week_start": "Week", "total_conversion_rate": "Conversion Rate (%)"},
    title=f"Weekly Conversion Trend — {selected_agent}"
)
fig_trend.update_layout(plot_bgcolor="white", height=400)
st.plotly_chart(fig_trend, use_container_width=True)

# ==============================================================
# 🧾 ③ Performance Summary (clean narrative)
# ==============================================================

summary = df[df["agent"] == selected_agent]
total_viewings = int(summary["total_viewings"].sum())
total_apps = int(summary["applications"].sum())
total_tenants = int(summary["tenants"].sum())
overall_conv = round((total_tenants / total_viewings * 100) if total_viewings else 0, 1)
app_rate = round((total_apps / total_viewings * 100) if total_viewings else 0, 1)
tenant_rate = round((total_tenants / total_apps * 100) if total_apps else 0, 1)

st.markdown("## 🧾 Performance Summary")
st.markdown(
    f"""
    Between **{summary['week_start'].min().strftime('%d %b %Y')}** and **{summary['week_end'].max().strftime('%d %b %Y')}**,  
    **{selected_agent}** carried out **{total_viewings} property viewings**.  
    Around **{app_rate}%** of those viewings led to applications (**{total_apps} total**),  
    and **{tenant_rate}%** of applicants became tenants (**{total_tenants} total**).  
    That’s an overall conversion of **{overall_conv}%** from first viewing to signed lease.
    """
)
