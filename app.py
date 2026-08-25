"""
Corporate Governance Analyzer
BA 435 - Corporate Finance

A general-purpose tool that walks any publicly traded ticker through the
Week 2 corporate governance framework:
    1. Corporate Governance (voting, ownership, shareholders, management,
       board, compensation)
    2. Bondholder Concerns (debt type, covenants, default risk)
    3. Financial Markets (trading/liquidity, analyst following)
    4. Society & Other Stakeholders (employees, reputation)

Quantitative fields are pulled live via yfinance where a free API can
reasonably supply them for an arbitrary ticker. Qualitative/governance
fields that require reading a proxy statement or 10-K (board composition,
CEO background, compensation mix, debt covenants, credit rating, employee
sentiment, ESG narrative) are NOT reliably available from a free API for
every ticker -- those are left as guided manual-entry fields, consistent
with this course's AI-assisted, human-verified research protocol: pull a
first-pass number, then verify it against a primary source before treating
it as final.
"""

import time
import random
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="Corporate Governance Analyzer", page_icon="🏛️", layout="wide")

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
DEFAULT_BOARD = pd.DataFrame(
    [{"Director": "", "Primary Occupation": "", "Independent?": "Yes"}]
)
DEFAULT_COMP = {
    "base_salary": 0.0,
    "bonus_incentive": 0.0,
    "stock_awards": 0.0,
    "option_awards": 0.0,
    "other_comp": 0.0,
    "pay_ratio": "",
    "say_on_pay_pct": "",
}
DEFAULT_BOND = {
    "debt_type": "Not yet researched",
    "covenants_notes": "",
    "credit_rating_sp": "Not rated / unknown",
    "credit_rating_moodys": "Not rated / unknown",
    "credit_rating_fitch": "Not rated / unknown",
}
DEFAULT_SOCIETY = {
    "glassdoor_rating": None,
    "ceo_approval_pct": None,
    "recommend_friend_pct": None,
    "turnover_notes": "",
    "esg_notes": "",
    "controversy_notes": "",
}

for key, default in [
    ("board_df", DEFAULT_BOARD.copy()),
    ("comp", DEFAULT_COMP.copy()),
    ("bond", DEFAULT_BOND.copy()),
    ("society", DEFAULT_SOCIETY.copy()),
    ("voting_notes", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# Data fetching (cached; yfinance fields vary by ticker and can go missing --
# every call is wrapped so one missing field never crashes the page)
#
# Classroom note: yfinance is an unofficial scraper against Yahoo Finance
# with no rate-limit guarantees, and a free Streamlit Community Cloud app
# shares a small pool of outbound IPs. If ~20 students each load a
# *different* ticker within the same minute (the common case, since this
# course has one company per student), Yahoo can occasionally throttle or
# briefly reject requests. A 4-hour cache means repeat loads of the same
# ticker (a student reloading the page, or two students on the same
# company) never re-hit Yahoo, and a small retry-with-backoff absorbs a
# single transient failure -- but this app cannot fully eliminate the risk
# of a rate-limited response during a burst of first-time requests. If a
# student hits it, "Retry" after a short wait usually clears it; the
# manual-entry fields work regardless.
# ---------------------------------------------------------------------------
def _retry(fn, attempts=3, base_delay=1.0):
    """Call fn() with a few retries and jittered backoff; re-raise the last error."""
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i) + random.uniform(0, 0.5))
    raise last_err


@st.cache_data(ttl=14400, show_spinner=False)
def fetch_ticker_data(ticker: str):
    t = yf.Ticker(ticker)
    data = {"ticker": ticker.upper(), "fetched_at": datetime.now().isoformat()}

    try:
        data["info"] = _retry(lambda: t.info or {})
    except Exception as e:
        data["info"] = {}
        data["info_error"] = str(e)
        data["rate_limited"] = "429" in str(e) or "rate" in str(e).lower() or "too many requests" in str(e).lower()

    try:
        df = t.institutional_holders
        data["institutional_holders"] = df if df is not None else pd.DataFrame()
    except Exception:
        data["institutional_holders"] = pd.DataFrame()

    try:
        df = t.major_holders
        data["major_holders"] = df if df is not None else pd.DataFrame()
    except Exception:
        data["major_holders"] = pd.DataFrame()

    try:
        recs = t.recommendations
        data["recommendations"] = recs if recs is not None else pd.DataFrame()
    except Exception:
        data["recommendations"] = pd.DataFrame()

    try:
        data["financials"] = t.financials if t.financials is not None else pd.DataFrame()
    except Exception:
        data["financials"] = pd.DataFrame()

    try:
        data["balance_sheet"] = t.balance_sheet if t.balance_sheet is not None else pd.DataFrame()
    except Exception:
        data["balance_sheet"] = pd.DataFrame()

    try:
        sustain = t.sustainability
        data["sustainability"] = sustain if sustain is not None else pd.DataFrame()
    except Exception:
        data["sustainability"] = pd.DataFrame()

    return data


def fnum(x, fmt="{:,.2f}", prefix="", suffix=""):
    """Format a number safely; return 'Not available' for missing/None."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "Not available"
    try:
        return f"{prefix}{fmt.format(x)}{suffix}"
    except (ValueError, TypeError):
        return str(x)


def pct(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "Not available"
    return f"{x * 100:.2f}%"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("🏛️ Governance Analyzer")
st.sidebar.caption("BA 435 -- Corporate Finance | Week 2 framework")
ticker_input = st.sidebar.text_input("Ticker symbol", value="MOD", help="e.g. MOD, AAPL, VRT").strip().upper()
load = st.sidebar.button("Load / Refresh Live Data", width="stretch")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**What's live vs. manual**\n\n"
    "Live (via Yahoo Finance): price, market cap, shares outstanding, float, "
    "beta, insider/institutional ownership %, top institutional holders, "
    "analyst ratings & price targets, revenue/net income, total debt & cash.\n\n"
    "Manual (needs a primary source -- DEF 14A, 10-K, Glassdoor, a ratings "
    "agency): board composition, CEO background, pay mix, debt covenants, "
    "credit rating, employee sentiment, ESG narrative. Free APIs don't "
    "reliably expose these for an arbitrary ticker -- fill them in after "
    "checking SEC EDGAR / the company's investor relations site, the same "
    "way the course's AI-verification protocol expects."
)

if "data" not in st.session_state or load:
    if ticker_input:
        with st.spinner(f"Fetching live data for {ticker_input}..."):
            st.session_state["data"] = fetch_ticker_data(ticker_input)
            st.session_state["loaded_ticker"] = ticker_input

data = st.session_state.get("data")
info = data.get("info", {}) if data else {}
company_name = info.get("longName") or info.get("shortName") or ticker_input

st.title(f"Corporate Governance Analysis -- {company_name}")
if data:
    st.caption(
        f"Ticker: {data['ticker']}  |  Data pulled: {data['fetched_at'][:19].replace('T', ' ')}  |  "
        "Live figures via Yahoo Finance (yfinance) -- verify anything you cite in graded work against a primary source."
    )

if not data:
    st.info("Enter a ticker in the sidebar and click **Load / Refresh Live Data** to begin.")
    st.stop()

if data.get("info_error") and not info:
    if data.get("rate_limited"):
        st.warning(
            "Yahoo Finance didn't respond for this ticker -- this usually means it's "
            "briefly rate-limiting the app (common when a lot of people are using it at "
            "once, e.g. during class). Wait 30-60 seconds and click **Load / Refresh Live "
            "Data** again. In the meantime, the manual-entry fields in each tab still work fine."
        )
    else:
        st.warning(
            f"Couldn't fetch live data for '{data['ticker']}' -- double-check the ticker "
            "symbol, or try again in a moment. Manual-entry fields still work regardless."
        )

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["1. Corporate Governance", "2. Bondholder Concerns", "3. Financial Markets", "4. Society & Stakeholders", "📄 Report"]
)

# ---------------------------------------------------------------------------
# TAB 1 -- Corporate Governance
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("a. Voting structure")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Shares Outstanding", fnum(info.get("sharesOutstanding"), "{:,.0f}"))
        st.metric("Float Shares", fnum(info.get("floatShares"), "{:,.0f}"))
    with col2:
        st.write(
            "Free APIs don't reliably flag dual-class structures or golden shares for an "
            "arbitrary ticker. Check the company's 10-K cover page or DEF 14A for share-class "
            "language, then note your finding below."
        )
        st.session_state["voting_notes"] = st.text_area(
            "Voting structure notes (manual)",
            value=st.session_state["voting_notes"],
            placeholder="e.g. Single class of common stock, one share/one vote, no government golden share found in the DEF 14A.",
            height=80,
        )

    st.subheader("b. Ownership structure")
    c1, c2, c3 = st.columns(3)
    c1.metric("Insider Ownership", pct(info.get("heldPercentInsiders")))
    c2.metric("Institutional Ownership", pct(info.get("heldPercentInstitutions")))
    c3.metric("Market Cap", fnum(info.get("marketCap"), "{:,.0f}", prefix="$"))

    major_holders = data.get("major_holders")
    if isinstance(major_holders, pd.DataFrame) and not major_holders.empty:
        with st.expander("Raw 'major holders' breakdown (Yahoo Finance)"):
            st.dataframe(major_holders, width="stretch")

    st.subheader("c. Top shareholders")
    inst_holders = data.get("institutional_holders")
    if isinstance(inst_holders, pd.DataFrame) and not inst_holders.empty:
        st.dataframe(inst_holders, width="stretch")
        st.caption(
            "Live institutional-holder table from Yahoo Finance's 13F aggregation. "
            "Cross-check the largest positions against the company's own DEF 14A "
            "beneficial-ownership table -- 13F aggregators sometimes double-count share "
            "classes or lag the filing date."
        )
    else:
        st.warning("No institutional-holder table returned for this ticker -- try a fresh load, or pull it manually from the DEF 14A / stockanalysis.com.")

    st.subheader("d. CEO and top management")
    officers = info.get("companyOfficers")
    if officers:
        off_df = pd.DataFrame(officers)
        keep_cols = [c for c in ["name", "title", "age", "yearBorn", "totalPay"] if c in off_df.columns]
        st.dataframe(off_df[keep_cols] if keep_cols else off_df, width="stretch")
        st.caption("Live officer list from Yahoo Finance. Tenure, prior employers, and education are not exposed by this API -- verify those against the company's proxy bio or press release.")
    else:
        st.info("No officer list returned for this ticker. Look up the CEO's tenure and background in the most recent DEF 14A or the company's leadership page.")

    st.subheader("e. Board of directors")
    st.write("Board composition isn't available via a free API for arbitrary tickers -- enter it from the DEF 14A proxy statement (SEC EDGAR).")
    st.session_state["board_df"] = st.data_editor(
        st.session_state["board_df"],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Independent?": st.column_config.SelectboxColumn(options=["Yes", "No"]),
        },
        key="board_editor",
    )
    board_df = st.session_state["board_df"]
    valid_rows = board_df[board_df["Director"].str.strip() != ""] if not board_df.empty else board_df
    if not valid_rows.empty:
        n_total = len(valid_rows)
        n_indep = (valid_rows["Independent?"] == "Yes").sum()
        pct_indep = n_indep / n_total * 100
        c1, c2, c3 = st.columns(3)
        c1.metric("Board size", n_total)
        c2.metric("Independent directors", n_indep)
        c3.metric("% Independent", f"{pct_indep:.0f}%")
        st.markdown("**CalPERS-style check:** " + ("✅ Majority independent" if pct_indep > 50 else "⚠️ Not majority independent"))

    st.subheader("f. Compensation structure")
    st.write("CEO pay mix comes from the DEF 14A Summary Compensation Table -- enter the components below.")
    comp = st.session_state["comp"]
    cc1, cc2, cc3 = st.columns(3)
    comp["base_salary"] = cc1.number_input("Base salary ($)", value=float(comp["base_salary"]), step=10000.0, format="%.0f")
    comp["bonus_incentive"] = cc2.number_input("Bonus / non-equity incentive ($)", value=float(comp["bonus_incentive"]), step=10000.0, format="%.0f")
    comp["stock_awards"] = cc3.number_input("Stock awards ($)", value=float(comp["stock_awards"]), step=10000.0, format="%.0f")
    cc4, cc5, cc6 = st.columns(3)
    comp["option_awards"] = cc4.number_input("Option awards ($)", value=float(comp["option_awards"]), step=10000.0, format="%.0f")
    comp["other_comp"] = cc5.number_input("Other compensation ($)", value=float(comp["other_comp"]), step=1000.0, format="%.0f")
    comp["pay_ratio"] = cc6.text_input("CEO pay ratio (e.g. 256:1)", value=comp["pay_ratio"])
    comp["say_on_pay_pct"] = st.text_input("Say-on-pay support (%)", value=comp["say_on_pay_pct"])
    total_comp = sum([comp["base_salary"], comp["bonus_incentive"], comp["stock_awards"], comp["option_awards"], comp["other_comp"]])
    if total_comp > 0:
        st.metric("Total CEO compensation", f"${total_comp:,.0f}")
        breakdown = pd.DataFrame(
            {
                "Component": ["Base salary", "Bonus/incentive", "Stock awards", "Option awards", "Other"],
                "Amount ($)": [comp["base_salary"], comp["bonus_incentive"], comp["stock_awards"], comp["option_awards"], comp["other_comp"]],
            }
        )
        breakdown["% of Total"] = (breakdown["Amount ($)"] / total_comp * 100).round(1)
        st.dataframe(breakdown, width="stretch", hide_index=True)
    st.session_state["comp"] = comp

# ---------------------------------------------------------------------------
# TAB 2 -- Bondholder Concerns
# ---------------------------------------------------------------------------
with tab2:
    bond = st.session_state["bond"]
    st.subheader("a. Debt type")
    bond["debt_type"] = st.selectbox(
        "How is this company financed?",
        ["Not yet researched", "Bank credit facility only", "Public bonds/notes only", "Both bank and public bonds", "No debt"],
        index=["Not yet researched", "Bank credit facility only", "Public bonds/notes only", "Both bank and public bonds", "No debt"].index(bond["debt_type"]) if bond["debt_type"] in ["Not yet researched", "Bank credit facility only", "Public bonds/notes only", "Both bank and public bonds", "No debt"] else 0,
    )
    st.caption("Check the 10-K debt footnote and 8-K filings on SEC EDGAR for credit agreements, indentures, or notes outstanding.")

    st.subheader("b. Debt covenants")
    bond["covenants_notes"] = st.text_area(
        "Covenant notes (manual -- from the credit agreement exhibit or 10-K debt footnote)",
        value=bond["covenants_notes"],
        height=100,
        placeholder="e.g. Maximum net leverage ratio of 3.5x; minimum interest coverage of 3.0x; restrictions on additional secured debt.",
    )

    st.subheader("c. Default risk measures")
    st.markdown("**Live balance-sheet leverage (from the most recent reported balance sheet):**")
    bs = data.get("balance_sheet")
    total_debt_live = info.get("totalDebt")
    cash_live = info.get("totalCash")
    ebitda_live = info.get("ebitda")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Debt", fnum(total_debt_live, "{:,.0f}", prefix="$"))
    c2.metric("Total Cash", fnum(cash_live, "{:,.0f}", prefix="$"))
    c3.metric("EBITDA", fnum(ebitda_live, "{:,.0f}", prefix="$"))
    if total_debt_live is not None and cash_live is not None and ebitda_live:
        net_debt = total_debt_live - cash_live
        leverage = net_debt / ebitda_live if ebitda_live else None
        c1, c2 = st.columns(2)
        c1.metric("Net Debt", f"${net_debt:,.0f}")
        c2.metric("Net Leverage (Net Debt / EBITDA)", f"{leverage:.2f}x" if leverage is not None else "Not available")
    else:
        st.info("Not all fields needed for a live leverage calculation were returned for this ticker -- pull total debt, cash, and EBITDA from the most recent 10-K or earnings release instead.")

    st.markdown("**Credit ratings (manual -- not exposed by free APIs):**")
    r1, r2, r3 = st.columns(3)
    bond["credit_rating_sp"] = r1.text_input("S&P rating", value=bond["credit_rating_sp"])
    bond["credit_rating_moodys"] = r2.text_input("Moody's rating", value=bond["credit_rating_moodys"])
    bond["credit_rating_fitch"] = r3.text_input("Fitch rating", value=bond["credit_rating_fitch"])
    st.session_state["bond"] = bond

# ---------------------------------------------------------------------------
# TAB 3 -- Financial Markets
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("a. Trading and liquidity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Price", fnum(info.get("currentPrice") or info.get("regularMarketPrice"), "{:,.2f}", prefix="$"))
    c2.metric("Market Cap", fnum(info.get("marketCap"), "{:,.0f}", prefix="$"))
    c3.metric("Shares Outstanding", fnum(info.get("sharesOutstanding"), "{:,.0f}"))
    c4.metric("Float", fnum(info.get("floatShares"), "{:,.0f}"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg. Daily Volume", fnum(info.get("averageVolume"), "{:,.0f}"))
    c2.metric("Beta", fnum(info.get("beta"), "{:,.2f}"))
    c3.metric("52-Week Range", f"{fnum(info.get('fiftyTwoWeekLow'), '{:,.2f}', prefix='$')} - {fnum(info.get('fiftyTwoWeekHigh'), '{:,.2f}', prefix='$')}")
    st.caption("Precise bid-ask spread / transaction-cost data isn't exposed by this API -- check a live Level 2 quote if you need exact liquidity-cost figures.")

    st.subheader("b. Analyst following")
    c1, c2, c3 = st.columns(3)
    c1.metric("Mean Target Price", fnum(info.get("targetMeanPrice"), "{:,.2f}", prefix="$"))
    c2.metric("# of Analysts", fnum(info.get("numberOfAnalystOpinions"), "{:,.0f}"))
    c3.metric("Recommendation", str(info.get("recommendationKey", "Not available")).replace("_", " ").title())

    recs = data.get("recommendations")
    if isinstance(recs, pd.DataFrame) and not recs.empty:
        st.markdown("**Recent recommendation trend (Yahoo Finance):**")
        st.dataframe(recs, width="stretch")
        rating_cols = [c for c in ["strongBuy", "buy", "hold", "sell", "strongSell"] if c in recs.columns]
        if rating_cols:
            latest = recs.iloc[0][rating_cols]
            st.bar_chart(latest)
    else:
        st.info("No analyst recommendation history returned for this ticker.")

# ---------------------------------------------------------------------------
# TAB 4 -- Society & Other Stakeholders
# ---------------------------------------------------------------------------
with tab4:
    society = st.session_state["society"]
    st.subheader("a. Employee satisfaction")
    st.caption("Not available via free financial-data APIs -- pull from Glassdoor, Indeed, or Comparably and enter below.")
    c1, c2, c3 = st.columns(3)
    society["glassdoor_rating"] = c1.number_input("Glassdoor rating (out of 5)", min_value=0.0, max_value=5.0, step=0.1, value=float(society["glassdoor_rating"] or 0.0))
    society["ceo_approval_pct"] = c2.number_input("CEO approval (%)", min_value=0.0, max_value=100.0, step=1.0, value=float(society["ceo_approval_pct"] or 0.0))
    society["recommend_friend_pct"] = c3.number_input("Would recommend to a friend (%)", min_value=0.0, max_value=100.0, step=1.0, value=float(society["recommend_friend_pct"] or 0.0))
    society["turnover_notes"] = st.text_area("Employee turnover / workforce notes (manual)", value=society["turnover_notes"], height=70)

    st.subheader("b. Society")
    sustain = data.get("sustainability")
    if isinstance(sustain, pd.DataFrame) and not sustain.empty:
        with st.expander("Raw ESG data returned by Yahoo Finance (if any)"):
            st.dataframe(sustain, width="stretch")
    else:
        st.info("No structured ESG data returned for this ticker via the API -- check CDP, EcoVadis, CSRHub, or the company's own sustainability report.")
    society["esg_notes"] = st.text_area("Sustainability / ESG notes (manual)", value=society["esg_notes"], height=70)
    society["controversy_notes"] = st.text_area("Reputation / controversy notes (manual)", value=society["controversy_notes"], height=70)
    st.session_state["society"] = society

# ---------------------------------------------------------------------------
# TAB 5 -- Report
# ---------------------------------------------------------------------------
with tab5:
    st.subheader("Auto-generated governance report")
    st.caption("Combines the live figures above with whatever you've entered manually. Review it, fix anything wrong, then export.")

    board_df = st.session_state["board_df"]
    valid_rows = board_df[board_df["Director"].str.strip() != ""] if not board_df.empty else board_df
    comp = st.session_state["comp"]
    bond = st.session_state["bond"]
    society = st.session_state["society"]
    total_comp = sum([comp["base_salary"], comp["bonus_incentive"], comp["stock_awards"], comp["option_awards"], comp["other_comp"]])

    lines = []
    lines.append(f"# Corporate Governance Analysis -- {company_name} ({data['ticker']})")
    lines.append(f"\n*Generated {datetime.now().strftime('%B %d, %Y')} -- live figures via Yahoo Finance; manual fields as entered in the app.*\n")

    lines.append("## 1. Corporate Governance\n")
    lines.append(f"**a. Voting structure:** {st.session_state['voting_notes'] or '_Not yet entered._'}\n")
    lines.append(f"**b. Ownership structure:** Insider ownership {pct(info.get('heldPercentInsiders'))}; institutional ownership {pct(info.get('heldPercentInstitutions'))}.\n")
    lines.append("**c. Top shareholders:** see live institutional-holder table in the app (Yahoo Finance 13F aggregation).\n")
    if officers:
        names = ", ".join(o.get("name", "") for o in officers[:3] if o.get("name"))
        lines.append(f"**d. CEO and top management:** {names or 'Not available'}.\n")
    else:
        lines.append("**d. CEO and top management:** Not available via API -- verify from the proxy statement.\n")
    if not valid_rows.empty:
        n_total = len(valid_rows)
        n_indep = (valid_rows["Independent?"] == "Yes").sum()
        lines.append(f"**e. Board of directors:** {n_total} members, {n_indep} independent ({n_indep/n_total*100:.0f}%).\n")
        lines.append(valid_rows.to_markdown(index=False))
        lines.append("")
    else:
        lines.append("**e. Board of directors:** _Not yet entered._\n")
    if total_comp > 0:
        lines.append(f"**f. Compensation structure:** Total CEO compensation ${total_comp:,.0f} (base ${comp['base_salary']:,.0f}, bonus ${comp['bonus_incentive']:,.0f}, stock ${comp['stock_awards']:,.0f}, options ${comp['option_awards']:,.0f}, other ${comp['other_comp']:,.0f}). Pay ratio: {comp['pay_ratio'] or 'not entered'}. Say-on-pay support: {comp['say_on_pay_pct'] or 'not entered'}.\n")
    else:
        lines.append("**f. Compensation structure:** _Not yet entered._\n")

    lines.append("## 2. Bondholder Concerns\n")
    lines.append(f"**a. Debt type:** {bond['debt_type']}\n")
    lines.append(f"**b. Debt covenants:** {bond['covenants_notes'] or '_Not yet entered._'}\n")
    if total_debt_live is not None and cash_live is not None and ebitda_live:
        net_debt = total_debt_live - cash_live
        leverage = net_debt / ebitda_live if ebitda_live else None
        lines.append(f"**c. Default risk measures:** Total debt ${total_debt_live:,.0f}; cash ${cash_live:,.0f}; net debt ${net_debt:,.0f}; EBITDA ${ebitda_live:,.0f}; net leverage {leverage:.2f}x. Ratings -- S&P: {bond['credit_rating_sp']}; Moody's: {bond['credit_rating_moodys']}; Fitch: {bond['credit_rating_fitch']}.\n")
    else:
        lines.append(f"**c. Default risk measures:** Ratings -- S&P: {bond['credit_rating_sp']}; Moody's: {bond['credit_rating_moodys']}; Fitch: {bond['credit_rating_fitch']}. Live leverage figures were not available for this ticker.\n")

    lines.append("## 3. Financial Markets\n")
    lines.append(f"**a. Trading and liquidity:** Price {fnum(info.get('currentPrice') or info.get('regularMarketPrice'), '{:,.2f}', prefix='$')}; market cap {fnum(info.get('marketCap'), '{:,.0f}', prefix='$')}; shares outstanding {fnum(info.get('sharesOutstanding'), '{:,.0f}')}; float {fnum(info.get('floatShares'), '{:,.0f}')}; average volume {fnum(info.get('averageVolume'), '{:,.0f}')}; beta {fnum(info.get('beta'), '{:,.2f}')}.\n")
    lines.append(f"**b. Analyst following:** Mean target price {fnum(info.get('targetMeanPrice'), '{:,.2f}', prefix='$')} from {fnum(info.get('numberOfAnalystOpinions'), '{:,.0f}')} analysts; consensus: {str(info.get('recommendationKey', 'not available')).replace('_', ' ').title()}.\n")

    lines.append("## 4. Society and Other Stakeholders\n")
    lines.append(f"**a. Employee satisfaction:** Glassdoor rating {society['glassdoor_rating'] or 'not entered'}/5; CEO approval {society['ceo_approval_pct'] or 'not entered'}%; would recommend to a friend {society['recommend_friend_pct'] or 'not entered'}%. {society['turnover_notes']}\n")
    lines.append(f"**b. Society:** {society['esg_notes'] or '_Not yet entered._'} {society['controversy_notes']}\n")

    lines.append("---\n*Live figures are pulled from Yahoo Finance via yfinance and can lag or occasionally be wrong -- cross-check anything you cite in graded work against the company's own 10-K, DEF 14A, or investor relations page, per this course's AI-verification protocol.*")

    report_md = "\n".join(lines)
    st.markdown(report_md)
    st.download_button(
        "⬇️ Download report as Markdown",
        data=report_md,
        file_name=f"governance_analysis_{data['ticker']}.md",
        mime="text/markdown",
        width="stretch",
    )
