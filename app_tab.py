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
        st.error(f"Password incorrect",color="red")
        return False
    else:
        return True

#Result Part
st.title("Peptide Sequence Bioactivity Dashboard")
st.markdown("Upload your CSV files.")

uploaded_files = st.file_uploader("Upload Your CSV files", type=['csv'], accept_multiple_files=True)

# Helper Function
def get_display_names(file):
    #Extracts the sheet name using regex.
    raw_name = file.name.replace('.csv', '')  # Remove the .csv extension
    pattern = r'^RankBioactivity_G(\d+)([a-z]?)(?:_(\d+)Enz)?(?:_(.+))?$'
    match = re.match(pattern, raw_name)
    # Error Handling
    if not match:
        return raw_name # Return original sheet name if it doesn't match
    group_num, sub_letter, enz_count, suffix = match.groups()
    group_label = f"Group {group_num}{sub_letter}"
    #display_name = f"{group_label} ({enz_count} Enzyme{'s' if enz_count != '1' else ''})"
    return group_label

def map_group_detail(file):
    detail_mapping = {
        "Group 1": "Exact Match",
        "Group 2": "Shorter Match",
        "Group 3a": "Longer Match (Single Functional Domain)",
        "Group 3b": "Longer Match (Multiple Functional Domains)"
    }
    return detail_mapping.get(file, "")

@st.cache_data(show_spinner=False) # Cache for speed
def load_prep_data(file):
    file.seek(0)
    df = pd.read_csv(file)
    if 'nPepSeq' not in df.columns or 'Bioactivity' not in df.columns:
        return None,0,"0"
    
    total_peptides = df['nPepSeq'].sum()
    plot_df = df.sort_values(by='nPepSeq', ascending=False).copy() 
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
                        color_continuous_scale='Blues',
                        custom_data=['Hover_Percentage', 'Hover_Details'],
                        orientation='h',
                        title=f'Total Peptide Sequences: {formatted_total}',
                        height=450)

    fig_bar.update_traces(textposition='inside',
                          hovertemplate='<b>%{y}</b><br>Count: %{x}<br>Percentage: %{customdata[0]}%{customdata[1]}<extra></extra>')
    fig_bar.update_layout(yaxis=dict(autorange="reversed", title='Bioactivities'),
                          xaxis=dict(title='Count of Peptide Sequences (Log Scale)'),
                          margin = dict(l=0, r=0, t=30, b=10),
                          coloraxis_showscale=False)
    return fig_bar


def plot_pie(filtered_df,formatted_total):
    if len(filtered_df) > 10:
        pie_top = filtered_df.head(9).copy()
        pie_rest = filtered_df.iloc[9:]
        other_sum = pie_rest['nPepSeq'].sum()
        other_row = pd.DataFrame({
            'Bioactivity': ['Other'], 
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
                        #hole=0.4,  # Creates a donut
                        custom_data=['Hover_Combined'],
                        title=f'Top 10 Bioactivity Groups | Total Peptide Sequences: {formatted_total}',
                        height=450)
    fig_pie.update_traces(textposition='inside', 
                        textinfo='percent+label',
                        direction = 'clockwise',
                        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{customdata[0]}<extra></extra>')
    fig_pie.update_layout(margin = dict(l=0, r=0, t=30, b=10),
                        uniformtext_minsize=12, 
                        uniformtext_mode='hide',
                        legend=dict(
                            orientation="h",
                            yanchor="top",
                            y=-0.1,
                            xanchor="center",
                            x=0.5
                        ))
    return fig_pie

# Summary tab content
def summary_dashboard(file_paths):
    """
    Iterates through a list of CSV files, opens EVERY file, 
    and generates Bar and Pie charts for sheets.
    """
    #Build Grid Column
    st.header("Summary Dashboard")
    col_select, _ = st.columns([1, 3])
    with col_select:
        chart_type = st.selectbox("Global Chart Type", options=["Pie Chart", "Bar Chart"],key='summary_chart_type')
    for i, file in enumerate(file_paths):         
        # Create new row every 2 items
        if i % 2 == 0:
            cols = st.columns(2)
        col = cols[i % 2]
        
        # 1. Get Details from File
        group_name = get_display_names(file)
        group_detail = map_group_detail(group_name)

        # 2. Load and Process Data
        plot_df, total_peptides, formatted_total= load_prep_data(file)
        if plot_df is None:
            st.warning(f"Skipping '{file.name}': Required columns 'nPepSeq' or 'Bioactivity' not found.")
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
                    filtered_df = plot_df[plot_df['Bioactivity'].isin(select_bioac)]
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
                    fig = plot_pie(filtered_df, formatted_total)
                    st.plotly_chart(fig, use_container_width=True)
    create_sum_table(file_paths)


def create_sum_table(file_paths):
    """
    Creates a summary table for all uploaded Excel files, 
    showing the total peptide sequences for each sheet.
    """
    st.markdown("## 📈 Statistical Summary")
    summary_data = []

    for file in file_paths:
        #raw_name = file.name.replace('.csv', '')
        display_sheet_name = get_display_names(file)  # Use the regex function to extract the sheet name
        file.seek(0)

        df = pd.read_csv(file)  # Read the CSV file into a DataFrame

        if 'nPepSeq' not in df.columns:
            st.warning(f"Skipping '{display_sheet_name}' in {file.name}: Required column 'nPepSeq' not found.")
            continue
        
        total_peptides = df['nPepSeq'].sum()
        summary_data.append({
            "Sheet Name": display_sheet_name,
            "Total Peptide Sequences": total_peptides
        })
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, width="stretch", hide_index=True,
                 column_config={"Total Peptide Sequences": st.column_config.NumberColumn(
                     alignment="left")})
             

def render_group_tab(group_name,file):
    # For render each group detail
    st.header(f'Detail Analysis: {group_name}')
    st.info(f'Custom Data table')

def reder_ml_tab():
    st.header("ML Prediction")
    st.info("the Ml prediction result")

if uploaded_files:
    # Define Tabs
    tab_titles = ["Summary", "Group 1", "Group 2", "Group 3a", "Group 3b", "ML Prediction"]
    tabs = st.tabs(tab_titles)
    
    # Route to appropriate render function based on selected tab
    with tabs[0]:
        summary_dashboard(uploaded_files)
        
    with tabs[1]:
        render_group_tab("Group 1", uploaded_files)
        
    with tabs[2]:
        render_group_tab("Group 2", uploaded_files)
        
    with tabs[3]:
        render_group_tab("Group 3a", uploaded_files)
        
    with tabs[4]:
        render_group_tab("Group 3b", uploaded_files)
        
    with tabs[5]:
        reder_ml_tab()