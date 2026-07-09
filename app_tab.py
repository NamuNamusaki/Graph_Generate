import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import os
import streamlit as st
import re

st.set_page_config(page_title="Result Dashboard", layout="wide")

#Password Part
def check_password():
    """Returns `True` if the user had a correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input("Please enter the correct password:", 
                      type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Please enter the correct password:",
                      type="password", on_change=password_entered, key="password")
        st.error(f"Password incorrect")
        return False
    else:
        return True

#Result Part
st.title("Peptide Sequence Bioactivity Dashboard")
st.markdown("Upload your CSV files.")

# Helper Function
def get_display_names(sheet_name):
    """
    Extracts the sheet name from a given string using regex.
    """
    pattern = r'^RankBioactivity_G(\d+)([a-z]?)(?:_(\d+)Enz)?(?:_(.+))?$'
    match = re.match(pattern, sheet_name)
    
    # Error Handling
    if not match:
        return sheet_name # Return original sheet name if it doesn't match

    group_num, sub_letter, enz_count, suffix = match.groups()
    group_label = f"Group {group_num}{sub_letter}"
    #display_name = f"{group_label} ({enz_count} Enzyme{'s' if enz_count != '1' else ''})"
    return group_label

GROUP_DETAIL = {
    "Group 1": "Exact Match",
    "Group 2": "Shorter Match",
    "Group 3a": "Longer Match (Single Functional Domain)",
    "Group 3b": "Longer Match (Multiple Functional Domains)"
}

GROUP_ORDER = ["Group 1", "Group 2", "Group 3a", "Group 3b"]

def load_group_data(uploaded_files) -> dict[str, pd.DataFrame]:
    #reading uploaded csv and return grouped data
    group_data: dict[str, pd.DataFrame] = {}
    for file in uploaded_files:
        raw_name = file.name.replace('.csv', '')
        group_name = get_display_names(raw_name)
        file.seek(0)
        df = pd.read_csv(file)

        #Check if the file not exist
        if 'nPepSeq' not in df.columns or 'Bioactivity' not in df.columns:
            st.warning(f"Skipping '{raw_name}': Required columns 'nPepSeq' or 'Bioactivity' not found.")
            continue
            
        group_data[group_name] = (pd.concat([group_data[group_name],df],ignore_index=True)
                                  if group_name in group_data 
                                  else df
                                  )
    return group_data


def prep_plot_df(df) -> tuple[pd.DataFrame, int]:
    total_peptides = df['nPepSeq'].sum()
    # Group by 'Bioactivity' and sum 'nPepSeq', then sort
    plot_df = df.groupby('Bioactivity', as_index=False)['nPepSeq'].sum().sort_values(by='nPepSeq', ascending=False)
    plot_df['Hover_Percentage'] = ((plot_df['nPepSeq'] / total_peptides) * 100).round(2).astype(str) + '%'
    plot_df['Hover_Details'] = ""
    plot_df['Hover_Combined'] = plot_df['Hover_Percentage'] + plot_df['Hover_Details']    
    return plot_df, total_peptides

def build_topn_options(total_rows: int) -> list[str]:
    options = ["Top 10"]
    if total_rows > 20:
        options.append("Top 20")
    if total_rows > 50:
        options.append("Top 50")
    options.append(f"All ({total_rows})")
    return options

# Chart Building Finction
def plot_pie(plot_df: pd.DataFrame,title:str,top_n:int = 10, heigth: int=380):
    if len(plot_df) > top_n:
        top = plot_df.head(top_n - 1).copy()
        rest = plot_df.iloc[top_n - 1:]
        other_row = pd.DataFrame({
            "Bioactivity": ["Others"],
            "nPepSeq":     [rest["nPepSeq"].sum()],
            "Hover_Percentage": [""],
        })
        pie_df = pd.concat([top, other_row], ignore_index=True)
    else:
        pie_df = plot_df.copy()
 
    fig = px.pie(
        pie_df, values="nPepSeq", names="Bioactivity",
        hover_name="Bioactivity", custom_data=["Hover_Percentage"],
        title=title, height=heigth,
    )
    fig.update_traces(
        textposition="inside", textinfo="percent+label",
        direction="clockwise",
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{customdata[0]}<extra></extra>",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=10),
        uniformtext_minsize=10, uniformtext_mode="hide",
        legend=dict(orientation="v", yanchor="top", y=1,
                    xanchor="left", x=1.02, font=dict(size=10)),
    )
    return fig

def plot_bar(plot_df: pd.DataFrame, title: str, top_n_option: str = "Top 10", height: int = 500):
    if "All" in top_n_option:
        final_df = plot_df
    else:
        n = int(top_n_option.split()[1])
        final_df = plot_df.head(n)
    fig = px.bar(
        final_df, x="nPepSeq", y="Bioactivity", log_x=True,
        text="nPepSeq", color="nPepSeq",
        color_continuous_scale="Blues",
        custom_data=["Hover_Percentage", "Hover_Details"],
        )
    fig.update_traces(
        textposition="inside",
        hovertemplate="<b>%{y}</b><br>Count: %{x}<br>Percentage: %{customdata[0]}%{customdata[1]}<extra></extra>",
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed", title="Bioactivities"),
        xaxis=dict(title="Count of Peptide Sequences (Log Scale)"),
        margin=dict(l=0, r=0, t=30, b=10),
        coloraxis_showscale=False,
    )
    return fig

# Tab Creation
def summary_tab(present_groups: list, group_data: dict,group_total:dict):
    st.subheader("Summary")
    for row_start in range(0, len(present_groups), 2):
        row_groups = present_groups[row_start:row_start+2]
        cols = st.columns(2)
        for j, g in enumerate(row_groups):
            with cols[j]:
                with st.container(border=True):
                    st.markdown(f"**{g}** - {GROUP_DETAIL.get(g, '')}**")
                    pdf = group_data[g]
                    total = group_total[g]
                    shown = min(10,len(pdf))
                    fig = plot_pie(
                        pdf,
                        title = f"Top {shown} of {total:,} Bioactivity Groups",
                        top_n=10, heigth=340,
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                    key=f"summary_pie_{g}")
                    
    render_statistics_table(present_groups, group_total)

# Create Table Function
def render_statistics_table(present_groups: list, group_totals: dict):
    """
    Creates a summary table for all uploaded Excel files, 
    showing the total peptide sequences for each sheet.
    """
    st.markdown("## 📈 Statistical Summary")
    with st.expander("Sample / experiment metadata (optional)", expanded=False):
        c1, c2, c3 = st.columns(3)
        organism  = c1.text_input("Organism",        value="")
        enzyme    = c2.text_input("Enzyme",           value="")
        n_proteins = c3.text_input("nProteins (input)", value="")
 
    n_peptides_total = sum(group_totals.values())
    rows = [
        {"Parameter": "Organism",            "Value": organism  or "—"},
        {"Parameter": "Enzyme",              "Value": enzyme    or "—"},
        {"Parameter": "nProteins (input)",   "Value": n_proteins or "—"},
        {"Parameter": "nPeptides (output)",  "Value": f"{n_peptides_total:,}"},
    ]
    for g in present_groups:
        rows.append({
            "Parameter": f"{g} — {GROUP_DETAIL.get(g, g)}",
            "Value":     f"{group_totals[g]:,}",
        })
 
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        column_config={"Value": st.column_config.TextColumn(width="medium")},
    )

def render_group_tab(g: str, group_plotdf: dict, group_totals: dict, chart_type: str):
    """Renders a single per-group detail tab (filter → chart → raw data)."""
    plot_df_full = group_plotdf[g].copy()
    total = group_totals[g]
 
    st.subheader(f"{g} — {GROUP_DETAIL.get(g, '')}")
 
    # Multiselect filter
    select_bioac = st.multiselect(
        "Select Bioactivities:",
        options=plot_df_full["Bioactivity"].tolist(),
        default=[],
        key=f"select_bioac_{g}",
    )
    filtered_df = (
        plot_df_full[plot_df_full["Bioactivity"].isin(select_bioac)]
        if select_bioac
        else plot_df_full
    )
 
    # Chart
    if chart_type == "Bar Chart":
        top_n_option = st.selectbox(
            "Show Bioactivities:",
            options=build_topn_options(len(filtered_df)),
            index=0,
            key=f"top_n_{g}",
        )
        fig = plot_bar(filtered_df,
                       title=f"Total Peptide Sequences: {total:,}",
                       top_n_option=top_n_option, height=550)
    else:
        fig = plot_pie(filtered_df,
                       title=f"Total Peptide Sequences: {total:,}",
                       top_n=10, height=550)
 
    st.plotly_chart(fig, use_container_width=True, key=f"detail_chart_{g}")
 
    with st.expander(f"Raw data — {g}"):
        st.dataframe(plot_df_full[["Bioactivity", "nPepSeq"]],
                     use_container_width=True, hide_index=True)

def render_ml_tab():
    """Placeholder for the ML Predictions tab."""
    st.subheader("ML Predictions")
    st.info(
        "ML prediction results (AMP, NP, ATHP) are not part of the uploaded "
        "RankBioactivity CSV files. Once ML prediction output is available, "
        "hook it up here to display counts and charts the same way as the other tabs."
    )

#Main Function
def main():
    # --- Header ---
    header_left, header_right = st.columns([4, 1])
    with header_left:
        st.title("🧬 Analysis Results")
    with header_right:
        st.write("")
        st.button("⬇️ Export All Data", use_container_width=True)
    st.divider()
 

 
    st.markdown("Upload your CSV files.")
    uploaded_files = st.file_uploader(
        "Upload Your CSV files", type=["csv"], accept_multiple_files=True
    )
 
    if not uploaded_files:
        st.info(
            "Upload the RankBioactivity CSV files "
            "(G1, G2, G3a, G3b, and G4/Unknown) to see the dashboard."
        )
        return
 
    for file in uploaded_files:
        st.success(f"File uploaded: {file.name}")
    
    chart_type = st.selectbox(
        "Select Chart Type:",
        options=["Pie Chart", "Bar Chart"],
        index=0,
        key="global_chart_type",
    )
    
    # --- Load & pre-process ---
    group_data = load_group_data(uploaded_files)
 
    group_plotdf: dict[str, pd.DataFrame] = {}
    group_totals: dict[str, int] = {}
    for g, df in group_data.items():
        pdf, total = prep_plot_df(df)
        group_plotdf[g] = pdf
        group_totals[g] = total
 
    present_groups = [g for g in GROUP_ORDER if g in group_data]
    present_groups += [g for g in group_data if g not in GROUP_ORDER]  # any extras
 
    if not present_groups:
        st.warning("None of the uploaded files could be matched to a bioactivity group.")
        return
 
    # --- Build tabs ---
    tab_labels = (
        ["Summary"]
        + [f"{g} ({group_totals[g]:,})" for g in present_groups]
        + ["ML Predictions"]
    )
    tabs = st.tabs(tab_labels)
 
    with tabs[0]:
        summary_tab(present_groups, group_plotdf, group_totals)
 
    for idx, g in enumerate(present_groups, start=1):
        with tabs[idx]:
            render_group_tab(g, group_plotdf, group_totals, chart_type)
 
    with tabs[-1]:
        render_ml_tab()
 
 
if __name__ == "__main__":
    # if not check_password():
    #     st.stop()
    main()