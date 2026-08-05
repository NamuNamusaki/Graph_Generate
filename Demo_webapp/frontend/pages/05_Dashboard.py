import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import os
import glob
import streamlit as st
import re
import io
import requests
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak
from config import API_URL

st.set_page_config(page_title="Result Dashboard", layout="centered")

# Global CSS to make all Streamlit UI text bold
st.markdown("""
    <style>
        .main p, .main h1, .main h2, .main h3, .main label, 
        div[data-testid="stTable"], div[data-testid="stMetricValue"] {
            font-weight: bold !important;
        }
    </style>
""", unsafe_allow_html=True)

# Security Check + Data Check
if not st.session_state.get("logged_in", False):
    st.warning("⚠️ You must be logged in to view results.")
    st.stop()
if 'job_id' not in st.session_state:
    st.warning("⚠️ No data found. Please go back to the Upload page and submit a sequence.")
    st.stop()

job_uuid = st.session_state['job_id']
AUTH_HEADERS = {"Authorization": f"Bearer {st.session_state.get('access_token', '')}"}

#API FETCHING FUNCTIONS
@st.cache_data(show_spinner="Fetching data from server...")
def fetch_summary_data(job_id):
    try:
        response = requests.get(f"{API_URL}/results/{job_id}/summary", headers=AUTH_HEADERS)
        response.raise_for_status()
        df = pd.DataFrame(response.json())

        # Convert CSV text into Pandas DataFrame for the frontend
        group_dfs = {}
        if 'Group' in df.columns:
            for group_name, group_data in df.groupby('Group'):
                group_dfs[group_name] = group_data.drop(columns=["Group"]).reset_index(drop=True)
        return group_dfs
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Could not fetch summary data from the server. Details: {e}")
        return {}

    
def fetch_sequence_csv(job_id, group_name, bioactivity):
    """
    Handoff Note:
    Endpoint: GET /api/results/{job_id}/download?group={group_name}&bioactivity={bioactivity}
    Expected Response: Plain text CSV string.
    """
    try:
        # Safe URL formatting
        url = f"{API_URL}/results/{job_id}/download"
        params = {"group": group_name, "bioactivity": bioactivity}
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            return response.content # Returns raw bytes perfect for the download button
        return None
    except:
        return None

# Helper Function
# Function to transform the bioactivity name
def format_bioac_name(name):
    if pd.isna(name):
        return name
    parts = str(name).replace('_', ' ').split(' ')
    formatted_parts = [p[0].upper() +p[1:] if len(p) >0 else p for p in parts]
    return ' '.join(formatted_parts)

def get_group_names(file_name):
    # Extracts the sheet name using regex.
    raw_name = file_name.replace('.csv', '')  # Remove the .csv extension (if using the file fromapi or upload usinf.name instead)
    pattern = r'^RankBioactivity_G(\d+)([a-z]?)(?:_(\d+)Enz)?(?:_(.+))?$'
    match = re.match(pattern, raw_name)
    # Error Handling
    if not match:
        return raw_name # Return original sheet name if it doesn't match
    group_num, sub_letter, enz_count, suffix = match.groups()
    group_label = f"Group {group_num}{sub_letter if sub_letter else ''}"
    #display_name = f"{group_label} ({enz_count} Enzyme{'s' if enz_count != '1' else ''})"
    return group_label

def map_group_detail(group_name):
    detail_mapping = {
        "Group 1": "Exact Match",
        "Group 2": "Shorter Match",
        "Group 3a": "Longer Match (Single Functional Domain)",
        "Group 3b": "Longer Match (Multiple Functional Domains)"
    }
    return detail_mapping.get(group_name, "")

def load_prep_data(df):
    if df is None or df.empty or 'nPepSeq' not in df.columns or 'Bioactivity' not in df.columns:
            return None, 0, "0"
    df = df.copy()
    if 'nPepSeq' not in df.columns or 'Bioactivity' not in df.columns:
        return None, 0, "0"
    
    df['Raw_bioactiity'] = df['Bioactivity']
    df['Bioactivity'] = df['Bioactivity'].apply(format_bioac_name)
    
    total_peptides = df['nPepSeq'].sum()
    plot_df = df.sort_values(by='nPepSeq', ascending=False)
    plot_df['Hover_Percentage'] = ((plot_df['nPepSeq'] / total_peptides) * 100).round(2).astype(str) + '%'
    plot_df['Hover_Details'] = ""
    plot_df['Hover_Combined'] = plot_df['Hover_Percentage'] + plot_df['Hover_Details']
    formatted_total = f"{total_peptides:,}"
    
    return plot_df, total_peptides, formatted_total 

def plot_bar(filter_df,formatted_total,top_n_option):
    if "All" in top_n_option:
        final_df = filter_df
    else:
        n = int(top_n_option.split()[1])
        final_df = filter_df.head(n)
    fig_bar = px.bar(final_df, 
                        x='nPepSeq', 
                        y='Bioactivity', 
                        log_x=True,      # The Y-axis now scales by
                        text='nPepSeq',
                        color='nPepSeq',
                        color_continuous_scale='tempo',
                        custom_data=['Hover_Percentage', 'Hover_Details'],
                        orientation='h',
                        title=f'Total Peptide Sequences: {formatted_total}',
                        height=450)

    fig_bar.update_traces(textposition='inside',
                          textfont=dict(weight='bold'),
                          hovertemplate='<b>%{y}</b><br>Count: %{x}<br>Percentage: %{customdata[0]}%{customdata[1]}<extra></extra>')
    fig_bar.update_layout(yaxis=dict(autorange="reversed", title='Bioactivities'),
                          xaxis=dict(title='Count of Peptide Sequences (Log Scale)'),
                          font=dict(weight='bold'),
                          margin = dict(l=0, r=0, t=30, b=10),
                          coloraxis_showscale=False)
    return fig_bar


def plot_pie(filtered_df,formatted_total):
    pie_rest = pd.DataFrame()
    if len(filtered_df) > 10:
        pie_top = filtered_df.head(9).copy()
        pie_rest = filtered_df.iloc[9:]  #Keep all other item
        other_sum = pie_rest['nPepSeq'].sum()
        other_row = pd.DataFrame({
            'Bioactivity': ['Others'], 
            'nPepSeq': [other_sum], 
            'Hover_Percentage': ['']
        })
        pie_df = pd.concat([pie_top, other_row], ignore_index=True)
    else:
        pie_df = filtered_df.copy()
    
    fig_pie = px.pie(pie_df, 
                        values='nPepSeq', 
                        names='Bioactivity', 
                        hover_name='Bioactivity',
                        custom_data=['Hover_Combined'],
                        title=f'Top 10 Bioactivity Groups | Total Peptide Sequences: {formatted_total}',
                        color_discrete_sequence=px.colors.qualitative.Pastel2,
                        height=450)
    fig_pie.update_traces(textposition='inside', 
                        textinfo='percent+label',
                        textfont=dict(weight='bold'),
                        direction = 'clockwise',
                        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{customdata[0]}<extra></extra>')
    fig_pie.update_layout(margin = dict(l=0, r=0, t=30, b=10),
                        font=dict(weight='bold'),
                        uniformtext_minsize=12, 
                        uniformtext_mode='hide',
                        legend=dict(
                            orientation="h",
                            yanchor="top",
                            y=-0.1,
                            xanchor="center",
                            x=0.5
                        ))
    return fig_pie,pie_rest

#=============== Summary tab content=============================
def summary_dashboard(group_dfs):
    """
    Iterates through a list of CSV files, opens EVERY file, 
    and generates Bar and Pie charts for sheets.
    """
    #Build Grid Column
    st.header("Summary Dashboard")
    col_select, col_html, col_pdf = st.columns([2, 1, 1])
    with col_select:
        chart_type = st.selectbox("Chart Type", options=["Pie Chart", "Bar Chart"],key='summary_chart_type')
    with col_html:
        st.download_button(
            "📄 Download HTML Report",
            data=generate_html_report(group_dfs),
            file_name="bioactivity_dashboard_report.html",
            mime="text/html",
            use_container_width=True,
        )
    with col_pdf:
        st.download_button(
            "📑 Download PDF Report",
            data=generate_pdf_report(group_dfs),
            file_name="bioactivity_dashboard_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    for i, (group_name, df) in enumerate(group_dfs.items()):         
        # Create new row every 2 items
        if i % 2 == 0:
            cols = st.columns(2)
        col = cols[i % 2]
        
        # 1. Get Details from File
        # file_name = os.path.basename(file)
        # group_name = get_group_names(file_name)
        group_detail = map_group_detail(group_name)

        # 2. Load and Process Data
        plot_df, total_peptides, formatted_total= load_prep_data(df)
        if plot_df is None:
            continue
        # 4. Render Dashboard Components
        with col:
            with st.container(border=True):
                st.subheader(f"{group_name} : {group_detail}")

                # Multiselect Filter
                all_bioactivities = plot_df['Bioactivity'].tolist()
                select_bioac = st.multiselect(
                    "Select Bioactivities:",
                    options=all_bioactivities,
                    default=[],
                    key=f"select_bioac_{group_name}"
                )
                # Apply Filter
                if select_bioac:
                    filtered_df = plot_df[plot_df['Bioactivity'].isin(select_bioac)] if select_bioac else plot_df.copy()
                else:
                    filtered_df = plot_df.copy()
                total_rows = len(plot_df)
                # Chart Logic Route
                if chart_type == "Bar Chart":
                    dropdown_option = ["Top 10"]
                    if total_rows > 20: dropdown_option.append("Top 20")
                    if total_rows > 50: dropdown_option.append("Top 50")
                    dropdown_option.append(f"All ({total_rows})")

                    top_n_option = st.selectbox(
                        "Show Bioactivities:",
                        options=dropdown_option,
                        width=200,
                        index=0,
                        key=f"top_n_{group_name}"
                    )

                    fig = plot_bar(filtered_df, formatted_total, top_n_option)
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    fig,pie_rest = plot_pie(filtered_df, formatted_total)
                    st.plotly_chart(fig, use_container_width=True)
                    if not pie_rest.empty:
                        with st.expander(f'View All of Others ({len(pie_rest)} Bioactivities)'):
                            display_df = pie_rest[['Bioactivity', 'nPepSeq', 'Hover_Percentage']].rename(
                                columns={'nPepSeq': 'Count', 'Hover_Percentage': 'Percentage'}
                            )
                            st.dataframe(display_df, hide_index=True,use_container_width=True)
    create_sum_table(group_dfs)

def build_summary_rows(group_dfs):
    """
    Shared builder for the Project Detail & Statistical Summary table,
    reused by the on-screen table and the HTML/PDF report exports.
    """
    summary_data = {
        'Organism': st.session_state.get('api_payload',{}).get('organism','N/A'),
        'Clevage Enzyme': st.session_state.get('api_payload',{}).get('clevage_enz','-'),
        'Missed Cleavages': st.session_state.get('api_payload',{}).get('miss_clevages','-'),
    }

    for group_name, df in group_dfs.items():
        if 'nPepSeq' not in df.columns:
            continue
        group_detail = map_group_detail(group_name)
        total_peptides = df['nPepSeq'].sum()
        group_bioac = df['Bioactivity'].nunique()
        
        summary_data[f"{group_name} {group_detail} - Total Peptides"] = f"{total_peptides:,}"
        summary_data[f"{group_name} - Unique Bioactivities"] = f"{group_bioac:,}"

    return pd.DataFrame(list(summary_data.items()), columns=["Parameter", "Detail"])


def create_sum_table(group_dfs):
    """
    Creates a summary table for all uploaded Excel files,
    showing the total peptide sequences for each sheet.
    """
    st.markdown("## Project Detail & Statistical Summary")
    details_df = build_summary_rows(group_dfs)
    st.table(details_df)
    st.markdown("<hr style='margin-bottom: 20px; margin-top: 10px;'>", unsafe_allow_html=True)

# --- Export: HTML report (interactive Plotly charts + summary table) -------
@st.cache_data(show_spinner="Preparing HTML report...")
def generate_html_report(csv_paths):
    details_df = build_summary_rows(csv_paths)
    table_html = details_df.to_html(index=False, border=0, classes="summary-table")

    chart_sections = []
    for i, (group_name, df) in enumerate(csv_paths.items()):
        # file_name = os.path.basename(file)
        # group_name = get_group_names(file_name)
        group_detail = map_group_detail(group_name)
        plot_df, total_peptides, formatted_total = load_prep_data(df)
        if plot_df is None:
            continue

        bar_fig = plot_bar(plot_df, formatted_total, f"All ({len(plot_df)})")
        pie_fig, _ = plot_pie(plot_df, formatted_total)
        # Embed the Plotly library once (first chart) so the file works offline.
        bar_html = bar_fig.to_html(full_html=False, include_plotlyjs=(i == 0))
        pie_html = pie_fig.to_html(full_html=False, include_plotlyjs=False)

        chart_sections.append(f"""
        <section class="group-section">
            <h2>{group_name} : {group_detail}</h2>
            <div class="chart-row">
                <div class="chart-box">{bar_html}</div>
                <div class="chart-box">{pie_html}</div>
            </div>
        </section>
        """)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Bioactivity Dashboard Report</title>
<style>
    body {{ font-family: Arial, sans-serif; margin: 30px; color:#212529; }}
    h1 {{ margin-bottom:4px; }}
    .meta {{ color:#6c757d; margin-bottom:30px; }}
    table.summary-table {{ border-collapse: collapse; width:100%; margin-top:10px; }}
    table.summary-table th, table.summary-table td {{ border:1px solid #dee2e6; padding:8px 12px; text-align:left; }}
    table.summary-table th {{ background:#f1f3f5; }}
    .group-section {{ margin-top:40px; }}
    .chart-row {{ display:flex; gap:20px; flex-wrap:wrap; }}
    .chart-box {{ flex:1; min-width:420px; }}
</style>
</head>
<body>
    <h1>Peptide Sequence Bioactivity Dashboard - Summary Report</h1>
    <div class="meta">Generated: {generated_at}</div>
    <h2>Project Detail &amp; Statistical Summary</h2>
    {table_html}
    {''.join(chart_sections)}
</body>
</html>"""

# --- Export: PDF report (static Matplotlib charts + summary table) ---------
def render_static_bar(plot_df, formatted_total, top_n=15):
    data = plot_df.head(top_n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, max(3, 0.4 * len(data))))
    ax.barh(data['Bioactivity'], data['nPepSeq'], color="#3E7CB1")
    ax.set_xlabel("Count of Peptide Sequences")
    ax.set_title(f"Total Peptide Sequences: {formatted_total}", fontsize=11)
    for i, v in enumerate(data['nPepSeq']):
        ax.text(v, i, f" {v:,}", va='center', fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

def render_static_pie(plot_df, formatted_total, top_n=9):
    if len(plot_df) > top_n + 1:
        top = plot_df.head(top_n)
        rest_sum = plot_df.iloc[top_n:]['nPepSeq'].sum()
        labels = list(top['Bioactivity']) + ['Others']
        values = list(top['nPepSeq']) + [rest_sum]
    else:
        labels = list(plot_df['Bioactivity'])
        values = list(plot_df['nPepSeq'])
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(values, labels=labels, autopct='%1.1f%%', textprops={'fontsize': 8})
    ax.set_title(f"Top {top_n} Bioactivity Groups | Total: {formatted_total}", fontsize=11)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

def _pdf_scaled_image(png_buf, target_width):
    png_buf.seek(0)
    with PILImage.open(png_buf) as img:
        px_w, px_h = img.size
    png_buf.seek(0)
    return RLImage(png_buf, width=target_width, height=target_width * px_h / px_w)

@st.cache_data(show_spinner="Preparing PDF report...")
def generate_pdf_report(csv_paths):
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Peptide Sequence Bioactivity Dashboard - Summary Report", styles["Title"]),
        Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Project Detail & Statistical Summary", styles["Heading2"]),
    ]

    details_df = build_summary_rows(csv_paths)
    table_rows = [details_df.columns.tolist()] + details_df.values.tolist()
    summary_table = Table(table_rows, colWidths=[8 * cm, 9 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(summary_table)
    story.append(PageBreak())

    for group_name, df in csv_paths.items():
        # file_name = os.path.basename(file)
        # group_name = get_group_names(file_name)
        group_detail = map_group_detail(group_name)
        plot_df, total_peptides, formatted_total = load_prep_data(df)
        if plot_df is None:
            continue

        story.append(Paragraph(f"{group_name} : {group_detail}", styles["Heading2"]))
        for png_buf in (render_static_bar(plot_df, formatted_total), render_static_pie(plot_df, formatted_total)):
            story.append(_pdf_scaled_image(png_buf, 15 * cm))
            story.append(Spacer(1, 14))
        story.append(PageBreak())

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
             
def render_group_tab(group_name,group_dfs):
    # For render each group detail
    group_detail = map_group_detail(group_name)
    st.header(f'Detail Analysis: {group_name} {group_detail}')
    # Limit the Display
    limit_key = f'limit_{group_name}'
    if limit_key not in st.session_state:
        st.session_state[limit_key] = 10  

    df_raw = group_dfs.get(group_name)
    if df_raw is None:
        st.info(f"No data in {group_name}.")
        return
    df, _, _ = load_prep_data(df_raw)
    if df is None:
        st.error("Error reading data.")
        return
    # Create Table header
    h1, h2, h3, h4, h5 = st.columns([0.5, 3, 1.5, 1.5, 1.5])
    with h1: st.markdown("#",unsafe_allow_html=True)
    with h2: st.markdown("Bioactivity",unsafe_allow_html=True)
    with h3: st.markdown("Count",unsafe_allow_html=True)
    with h4: st.markdown("CSV Download",unsafe_allow_html=True)
    with h5: st.markdown("PARQUET Download",unsafe_allow_html=True)

    st.markdown("<hr style='margin-bottom: 10px; margin-top: 5px;'>", unsafe_allow_html=True)

    # Sort Datail of the table in group 1 to 3b
    interesed_list =st.session_state.get('Interested_Bioactivity',[])
    df['is_prior'] = df['Bioactivity'].str.lower().isin(interesed_list)
    df = df.sort_values(by=['is_prior', 'nPepSeq'], ascending=[False, False])
    df = df.reset_index(drop=True)
    
    total_rows = len(df)
    current_limit = st.session_state[limit_key]
    df_to_display = df.head(current_limit)

    for index, row in df_to_display.iterrows():
        bioactivity = row['Bioactivity']
        count = row['nPepSeq']
        
        c1,c2,c3,c4,c5 = st.columns([0.5, 3, 1.5, 1.5, 1.5])
        with c1: st.markdown(f'{index+1}.',unsafe_allow_html=True)
        with c2: st.markdown(bioactivity,unsafe_allow_html=True)
        with c3: st.markdown(count,unsafe_allow_html=True)
        with c4:
            if bioactivity.lower() in interesed_list:
                csv_bytes = fetch_sequence_csv(job_uuid, group_name, bioactivity)
                if csv_bytes:
                    st.download_button(
                        label="Download CSV",
                        data=csv_bytes,
                        file_name=f"{bioactivity}.csv",
                        mime="text/csv",
                        key=f"dl_csv_{group_name}_{index}"
                    )
                else:
                    st.markdown('No File',unsafe_allow_html=True)
            else:
                st.markdown('-')
        with c5:
            st.markdown('-')
        st.markdown("<hr style='margin-bottom: 10px; margin-top: 5px;'>", unsafe_allow_html=True)

    if total_rows > current_limit:
        col_space1, col_space2,col_btn = st.columns([2, 2, 1])
        with col_btn:
            if current_limit == 10:
                if st.button('See more', key=f'btn_more_{group_name}'):
                    st.session_state[limit_key] = 20
                    st.rerun()
            elif current_limit == 20:
                if st.button('See more', key=f'btn_more_{group_name}'):
                    st.session_state[limit_key] = 50
                    st.rerun()

    

# --- MOCKUP ONLY -------------------------------------------------------
# Once the FastAPI backend + prediction worker are wired up, replace
# MODEL_INFO / generate_mock_ml_predictions with the real model metadata
# and CSV result files produced by the worker/API job.
# -------------------------------------------------------------------------
MODEL_INFO = [
    {
        "key": "athp",
        "name": "ATHP",
        "description": "Antihypertensive model.",
        "n_predictions": 1240,
    },
    {
        "key": "amp",
        "name": "AMP",
        "description": "Antimicrobial model.",
        "n_predictions": 1240,
    },
    {
        "key": "np",
        "name": "NP",
        "description": "Neuropeptide model.",
        "n_predictions": 1240,
    },
]

@st.cache_data(show_spinner=False)
def generate_mock_ml_predictions(model_key, n_rows):
    """Placeholder result generator; replace with the worker/API CSV output."""
    prefix = model_key.upper().replace("_", "")[:6]
    bioactivities = ["AMP", "ACE inhibitor", "Antioxidant", "Anticancer"] * (n_rows // 4 + 1)
    return pd.DataFrame({
        "PeptideSequence": [f"{prefix}{i:04d}" for i in range(1, n_rows + 1)],
        "PredictedBioactivity": bioactivities[:n_rows],
        "ConfidenceScore": [round(0.5 + (i % 50) / 100, 2) for i in range(n_rows)],
    })

def render_ml_tab():
    st.header("ML Prediction")
    st.info("Mockup preview — these results will be populated from the worker/API once the prediction job completes.")

    h1, h2, h3, h4, h5 = st.columns([0.5, 2, 3.5, 1.5, 1.5])
    with h1: st.markdown("#", unsafe_allow_html=True)
    with h2: st.markdown("Model Name", unsafe_allow_html=True)
    with h3: st.markdown("Description", unsafe_allow_html=True)
    with h4: st.markdown("No. of Predictions", unsafe_allow_html=True)
    with h5: st.markdown("CSV Download", unsafe_allow_html=True)
    st.markdown("<hr style='margin-bottom: 10px; margin-top: 5px;'>", unsafe_allow_html=True)

    for index, model in enumerate(MODEL_INFO):
        c1, c2, c3, c4, c5 = st.columns([0.5, 2, 3.5, 1.5, 1.5])
        with c1: st.markdown(f"{index + 1}.", unsafe_allow_html=True)
        with c2: st.markdown(f"**{model['name']}**", unsafe_allow_html=True)
        with c3: st.markdown(model['description'], unsafe_allow_html=True)
        with c4: st.markdown(f"{model['n_predictions']:,}", unsafe_allow_html=True)
        with c5:
            mock_df = generate_mock_ml_predictions(model['key'], model['n_predictions'])
            st.download_button(
                label="Download CSV",
                data=mock_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{model['key']}_predictions.csv",
                mime="text/csv",
                key=f"dl_ml_{model['key']}"
            )
        st.markdown("<hr style='margin-bottom: 10px; margin-top: 5px;'>", unsafe_allow_html=True)



# Get Sequence File function
def get_sequence_path(group_name,bioactivity_name):
    BASE_DIR = 'Result_Sequence'
    target_folder = group_name.replace("Group ", "ResultG")
    file_path = os.path.join(BASE_DIR, target_folder, f"{bioactivity_name}.csv")
    return file_path

def get_stat_file():
    BASE_DIR = 'Result_Sequence'
    if not os.path.exists(BASE_DIR):
        return []
    #find file inside the folder
    return glob.glob(os.path.join(BASE_DIR, '**', 'RankBioactivity_*.csv'), recursive=True)


# Tab Name Define
st.title("Peptide Sequence Bioactivity Dashboard")
st.markdown(f"**Job ID:** `{job_uuid}`")
grouped_data = fetch_summary_data(job_uuid)

tab_titles = ["Summary", "Group 1", "Group 2", "Group 3a", "Group 3b", "ML Prediction"]
tabs = st.tabs(tab_titles)

# Route to appropriate render function based on selected tab
with tabs[0]:
    summary_dashboard(grouped_data)
with tabs[1]:
    render_group_tab("Group 1", grouped_data)
with tabs[2]:
    render_group_tab("Group 2", grouped_data)
with tabs[3]:
    render_group_tab("Group 3a", grouped_data)
with tabs[4]:
    render_group_tab("Group 3b", grouped_data)
with tabs[5]:
    render_ml_tab()