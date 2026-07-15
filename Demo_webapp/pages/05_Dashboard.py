import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import os
import glob
import streamlit as st
import re

st.set_page_config(page_title="Result Dashboard", layout="wide")

# Security Check: Ensure user is logged in
if not st.session_state.get("logged_in", False):
    st.warning("⚠️ You must be logged in to view results.")
    st.stop()
# Check Sequence Uploading
if not st.session_state.get('uploaded_files') and not st.session_state.get('raw_sequence'):
    st.warning("⚠️ No data found. Please go back to the Upload page and submit your CSV files.")
    st.stop() # This halts the script so the app doesn't crash trying to process empty data

#uploaded_files = st.session_state.get('uploaded_files', [])

# Helper Function
def get_display_names(file_name):
    #Extracts the sheet name using regex.
    raw_name = file_name.replace('.csv', '')  # Remove the .csv extension (if using the file fromapi or upload usinf.name instead)
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
    #file.seek(0)
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
def summary_dashboard(csv_path):
    """
    Iterates through a list of CSV files, opens EVERY file, 
    and generates Bar and Pie charts for sheets.
    """
    #Build Grid Column
    st.header("Summary Dashboard")
    col_select, _ = st.columns([1, 3])
    with col_select:
        chart_type = st.selectbox("Chart Type", options=["Pie Chart", "Bar Chart"],key='summary_chart_type')
    for i, file in enumerate(csv_path):         
        # Create new row every 2 items
        if i % 2 == 0:
            cols = st.columns(2)
        col = cols[i % 2]
        
        # 1. Get Details from File
        file_name = os.path.basename(file)
        group_name = get_display_names(file_name)
        group_detail = map_group_detail(group_name)

        # 2. Load and Process Data
        plot_df, total_peptides, formatted_total= load_prep_data(file)
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
                    fig = plot_pie(filtered_df, formatted_total)
                    st.plotly_chart(fig, use_container_width=True)
    create_sum_table(csv_path)

def create_sum_table(csv_paths):
    """
    Creates a summary table for all uploaded Excel files, 
    showing the total peptide sequences for each sheet.
    """
    st.markdown("## Project Detail & Statistical Summary")
    summary_data = {
        'Organism': st.session_state.get('organism','N/A'),
        'Clevage Enzyme': st.session_state.get('clevage_enz','-'),
        'Missed Cleavages': st.session_state.get('miss_cle','-'),
    }

    for file in csv_paths:
        #raw_name = file.name.replace('.csv', '')
        file_name = os.path.basename(file)
        display_sheet_name = get_display_names(file_name)  # Use the regex function to extract the sheet name
        group_detail = map_group_detail(display_sheet_name)
        df = pd.read_csv(file)  # Read the CSV file into a DataFrame

        if 'nPepSeq' not in df.columns:
            st.warning(f"Skipping '{display_sheet_name}' in {file.name}: Required column 'nPepSeq' not found.")
            continue
        
        total_peptides = df['nPepSeq'].sum()
        summary_data[f"{display_sheet_name} {group_detail}"] = f"{total_peptides:,}"
    details_df = pd.DataFrame(list(summary_data.items()), columns=["Parameter", "Detail"])
    st.table(details_df)
    st.markdown("<hr style='margin-bottom: 20px; margin-top: 10px;'>", unsafe_allow_html=True)
             

def render_group_tab(group_name,csv_file):
    # For render each group detail
    group_detail = map_group_detail(group_name)
    st.header(f'Detail Analysis: {group_name} {group_detail}')
    # Limit the Display
    limit_key = f'limit_{group_name}'
    if limit_key not in st.session_state:
        st.session_state[limit_key] = 10
    # Identify Correct File
    target_file = None
    for f in csv_file:
        file_name_only = os.path.basename(f)
        if get_display_names(file_name_only) == group_name:
            target_file = f
            break
    if target_file is None:
        st.info(f"No data in {group_name}.")
        return
    #Load Data
    df, _, _ = load_prep_data(target_file)
    if df is None:
        st.error("Error reading uploaded data.")
        return

    # Get a list of unique bioactivities found in the uploaded CSV
    #group_detail = map_group_detail(group_name)
    #short_id = group_name.replace('Group','G')    
    #st.markdown(f"#### 🟢 **{short_id}** {group_detail} — Bioactivity Summary")

    # Create Table header
    h1, h2, h3, h4, h5 = st.columns([0.5, 3, 1.5, 1.5, 1.5])
    with h1: st.markdown("#",unsafe_allow_html=True)
    with h2: st.markdown("Bioactivity",unsafe_allow_html=True)
    with h3: st.markdown("Count",unsafe_allow_html=True)
    with h4: st.markdown("CSV Download",unsafe_allow_html=True)
    with h5: st.markdown("PARQUET Download",unsafe_allow_html=True)

    st.markdown("<hr style='margin-bottom: 10px; margin-top: 5px;'>", unsafe_allow_html=True)

    # Sort Datainthetable
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
            interesed_list =st.session_state.get('Interested_Bioactivity',[])
            lower_bioac = bioactivity.lower()
            if lower_bioac in interesed_list:
                file_path = get_sequence_path(group_name,bioactivity)
                if file_path and os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        csv_data = f.read()
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"{bioactivity}.csv",
                        mime="text/csv",
                        key=f"dl_csv_{group_name}_{index}"
                    )
                else:
                    st.markdown('No File',unsafe_allow_html=True)
            else: 
                st.markdown('-',unsafe_allow_html=True) #ถ้าไม่ได้อยู่ในที่ user เลือกจะไม่แสดงปุ่มโหลด
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

    
def reder_ml_tab():
    st.header("ML Prediction")
    st.info("the Ml prediction result")

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
tab_titles = ["Summary", "Group 1", "Group 2", "Group 3a", "Group 3b", "ML Prediction"]
tabs = st.tabs(tab_titles)

csv_files = get_stat_file()
# Route to appropriate render function based on selected tab
with tabs[0]:
    summary_dashboard(csv_files)
with tabs[1]:
    render_group_tab("Group 1", csv_files)
with tabs[2]:
    render_group_tab("Group 2", csv_files)
with tabs[3]:
    render_group_tab("Group 3a", csv_files)
with tabs[4]:
    render_group_tab("Group 3b", csv_files)
with tabs[5]:
    reder_ml_tab()