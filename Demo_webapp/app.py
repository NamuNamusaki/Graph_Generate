import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import os
import streamlit as st
import re

st.set_page_config(page_title="Result Dashboard", layout="wide")
st.title("Peptide Sequence Bioactivity Dashboard")
st.markdown("Upload an Excel file.")

uploaded_files = st.file_uploader("Upload Excel files", type=['xlsx'], accept_multiple_files=False)

def get_sheet_names(sheet_name):
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
    # 1 loop through every file in the folder
    for file in file_paths:
        file_name = file.name
        
        st.markdown(f"### 📁 File: {file_name}")
        
        # Load ALL sheets from the file into a dictionary
        all_sheets = pd.read_excel(file, sheet_name=None)
        
        # 2 loop through every sheet
        for i,(sheet_name, df) in enumerate(all_sheets.items()):            
            display_sheet_name = get_sheet_names(sheet_name)  # Use the regex function to extract the sheet name
            # Build the grid for each sheet
            if i % 2 == 0:
                cols = st.columns(2)
            col = cols[i % 2] #ใส่ข้อมูลแต่ละคอลัมน์ใน grid (ซ้าย/ขวา)

            # เพื่อskip หน้าว่าง
            if 'nPepSeq' not in df.columns or 'Bioactivity' not in df.columns:
                st.warning(f"Skipping '{sheet_name}' in {file_name}: Required columns not found.")
                continue  
            
            # 3  Data Processing
            # Sum Total peptide in each sheet
            total_peptides = df['nPepSeq'].sum()
            sorted_df = df.groupby('Bioactivity', as_index=False)['nPepSeq'].sum().sort_values(by='nPepSeq', ascending=False) # Group by 'Bioactivity' and sum 'nPepSeq', then sor

            top10_df = sorted_df.head(10).copy()
            top10_df['Hover_Details'] = ""
            rest_df = sorted_df.iloc[10:]

            # 4 handle the rest of the data for the "Others" category
            if not rest_df.empty:
                others_sum = rest_df['nPepSeq'].sum()
                others_names = rest_df['Bioactivity'].tolist() #extract the names of the remaining categories

                if len(others_names) > 5:
                    visible_name = '<br>'.join(others_names[:5])
                    details_str = f"<br><b>Includes:</b><br>{visible_name}<br><i> ...and {len(others_names)-5} more</i>"
                else:
                    visible_names = "<br>".join(others_names)
                    details_str = f"<br><b>Includes:</b><br>{visible_names}"

                others_row = pd.DataFrame({
                    'Bioactivity': ['Others'], 
                    'nPepSeq': [others_sum],
                    'Hover_Details': [details_str]
                })
                # Combine the Top 10 with the new Others row using pd.concat
                plot_df = pd.concat([top10_df, others_row], ignore_index=True)
            else: 
                plot_df = top10_df    

            plot_df['Hover_Percentage'] = ((plot_df['nPepSeq'] / total_peptides) * 100).round(2).astype(str) + '%'             
            plot_df['Hover_Combined'] = plot_df['Hover_Percentage'] + plot_df['Hover_Details']
            
            formatted_total = f"{total_peptides:,}"

            # -------------- Dashboard -----------------------
            with col:
                with st.container(border=True):
                    st.subheader(f" {display_sheet_name}")

                    if chart_type == "Bar Chart":
                        fig_bar = px.bar(plot_df, 
                                        x='nPepSeq', 
                                        y='Bioactivity', 
                                        log_x=True,      # The Y-axis now scales by percentage
                                        text='nPepSeq',
                                        custom_data=['Hover_Percentage', 'Hover_Details'],  # Include the hover data for percentage and details
                                        orientation='h',
                                        title=f'{display_sheet_name} | Total Peptide Sequences: {formatted_total}',
                                        height=400)

                        fig_bar.update_traces(textposition='inside',hovertemplate='<b>%{y}</b><br>Count: %{x}<br>Percentage: %{customdata[0]}%{customdata[1]}<extra></extra>')
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
        file_name = file.name
        all_sheets = pd.read_excel(file, sheet_name=None)

        for sheet_name, df in all_sheets.items():
            display_sheet_name = get_sheet_names(sheet_name)  # Use the regex function to extract the sheet name

            if 'nPepSeq' not in df.columns:
                st.warning(f"Skipping '{sheet_name}' in {file_name}: Required column 'nPepSeq' not found.")
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

if uploaded_files is not None:
    #for file in uploaded_files:
    st.success(f"File uploaded: {uploaded_files.name}")
    
    col_select, _ = st.columns([1, 3])
    with col_select:
        chart_type = st.selectbox(
            "Select Chart Type",
            options=["Bar Chart", "Pie Chart"],
            index=0,
        )
    get_sheet_names(uploaded_files.name)  # Call the function to extract and display the sheet name
    generate_dashboard_chart([uploaded_files], chart_type)
    create_sum_table([uploaded_files])