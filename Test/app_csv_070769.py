import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import os
import streamlit as st
import re

st.set_page_config(page_title="Result Dashboard", layout="wide")
st.title("Peptide Sequence Bioactivity Dashboard")
st.markdown("Upload your CSV files.")

uploaded_files = st.file_uploader("Upload Your CSV files", type=['csv'], accept_multiple_files=True)

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

    if group_label == "Group 1":
        display_name = "Group 1 - Exact Match"
    elif group_label == "Group 2":
        display_name = "Group 2 - Shorter Match"
    elif group_label == "Group 3a":
        display_name = "Group 3a - Longer Match (Single Functional Domain)"
    elif group_label == "Group 3b":
        display_name = "Group 3b - Longer Match (Multiple Functional Domains)"

    return display_name

def generate_dashboard_chart (file_paths,chart_type):
    """
    Iterates through a list of Excel files, opens EVERY sheet inside them, 
    and generates Bar and Pie charts for sheets.
    """
    # 1 loop through every csv file
    for i,file in enumerate(file_paths):            
        # Build the grid for each sheet
        if i % 2 == 0:
            cols = st.columns(2)
        col = cols[i % 2] #ใส่ข้อมูลแต่ละคอลัมน์ใน grid (ซ้าย/ขวา)
        
        # 2 Extract the display name from the file name
        raw_name = file.name.replace('.csv', '')  # Remove the .csv extension
        display_sheet_name = get_display_names(raw_name)  # Use the regex function to extract the display name
        
        # 3 read csv file
        df = pd.read_csv(file)  # Read the CSV file into a DataFrame

        # Check if required columns exist
        if 'nPepSeq' not in df.columns or 'Bioactivity' not in df.columns:
            st.warning(f"Skipping '{raw_name}': Required columns 'nPepSeq' or 'Bioactivity' not found.")
            continue
        
        # 4 Data Processing
        total_peptides = df['nPepSeq'].sum()
        plot_df = df.sort_values(by='nPepSeq', ascending=False).copy() # Group by 'Bioactivity' and sum 'nPepSeq', then sort

        plot_df['Hover_Percentage'] = ((plot_df['nPepSeq'] / total_peptides) * 100).round(2).astype(str) + '%'
        plot_df['Hover_Details'] = ""
        plot_df['Hover_Combined'] = plot_df['Hover_Percentage'] + plot_df['Hover_Details']

        formatted_total = f"{total_peptides:,}"

        # -------------- Dashboard -----------------------
        with col:
            with st.container(border=True):
                st.subheader(f" {display_sheet_name}")

                if chart_type == "Bar Chart":
                   # dynamic_height = max(400, len(plot_df) * 30)
                    fig_bar = px.bar(plot_df, 
                                    x='nPepSeq', 
                                    y='Bioactivity', 
                                    log_x=True,      # The Y-axis now scales by percentage
                                    text='nPepSeq',
                                    custom_data=['Hover_Percentage', 'Hover_Details'],  # Include the hover data for percentage and details
                                    orientation='h',
                                    title=f'{display_sheet_name} | Total Peptide Sequences: {formatted_total}',
                                    height=400)

                    fig_bar.update_traces(textposition='inside',
                                          hovertemplate='<b>%{y}</b><br>Count: %{x}<br>Percentage: %{customdata[0]}%{customdata[1]}<extra></extra>')
                    fig_bar.update_layout(
                                        yaxis=dict(autorange="reversed", title='Bioactivity'),
                                        xaxis=dict(title='Count of Peptide Sequences (Log Scale)'),
                                        margin = dict(l=0, r=0, t=30, b=10)
                                        )
                    
                    st.plotly_chart(fig_bar, use_container_width=True)

                # 6 Generate the Pie Chart
                else:
                    fig_pie = px.pie(plot_df, 
                                    values='nPepSeq', 
                                    names='Bioactivity', 
                                    hover_name='Bioactivity',
                                    custom_data=['Hover_Combined'],  # Include the combined hover data
                                    title=f'{display_sheet_name} | Total Peptide Sequences: {formatted_total}',
                                    height=400)
                
                    fig_pie.update_traces(textposition='inside', 
                                    textinfo='percent+label',
                                    hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{customdata[0]}<extra></extra>')
                    fig_pie.update_layout(margin = dict(l=0, r=0, t=30, b=10))
                
                    st.plotly_chart(fig_pie, use_container_width=True)

def create_sum_table(file_paths):
    """
    Creates a summary table for all uploaded Excel files, 
    showing the total peptide sequences for each sheet.
    """
    st.markdown("## 📈 Statistical Summary")
    summary_data = []

    for file in file_paths:
        raw_name = file.name.replace('.csv', '')
        display_sheet_name = get_display_names(raw_name)  # Use the regex function to extract the sheet name

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

if uploaded_files:
    for file in uploaded_files:
        st.success(f"File uploaded: {file.name}")
    
    col_select, _ = st.columns([1, 3])
    with col_select:
        chart_type = st.selectbox(
            "Select Chart Type",
            options=["Bar Chart", "Pie Chart"],
            index=0,
        )
    #get_display_names(uploaded_files.name)  # Call the function to extract and display the sheet name
    generate_dashboard_chart(uploaded_files, chart_type)
    create_sum_table(uploaded_files)