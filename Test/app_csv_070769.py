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
        display_name = "Group 1"
    elif group_label == "Group 2":
        display_name = "Group 2"
    elif group_label == "Group 3a":
        display_name = "Group 3a"
    elif group_label == "Group 3b":
        display_name = "Group 3b"

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
        grouped_df = df.groupby('Bioactivity', as_index=False)['nPepSeq'].sum()  # Group by 'Bioactivity' and sum 'nPepSeq'
        total_peptides = df['nPepSeq'].sum()
        plot_df = df.sort_values(by='nPepSeq', ascending=False).copy() # Group by 'Bioactivity' and sum 'nPepSeq', then sort

        plot_df['Hover_Percentage'] = ((plot_df['nPepSeq'] / total_peptides) * 100).round(2).astype(str) + '%'
        plot_df['Hover_Details'] = ""
        plot_df['Hover_Combined'] = plot_df['Hover_Percentage'] + plot_df['Hover_Details']

        formatted_total = f"{total_peptides:,}"
        total_rows = len(plot_df) # Count the exact number of the group of Bioactivity
        
        # -------------- Dashboard -----------------------
        with col:
            with st.container(border=True):
                st.subheader(f" {display_sheet_name}")

                # Dropdown to filter each chart by Bioactivity Rank
                dropdown_option = ["Top 10"]
                if total_rows > 20:
                    dropdown_option.append("Top 20")
                if total_rows > 50:
                    dropdown_option.append("Top 50")

                dropdown_option.append(f"All ({total_rows})")

                top_n_option = st.selectbox(
                    "Show Bioactivities:",
                    options=dropdown_option,
                    index=0,
                    key=f"top_n_{display_sheet_name}"
                )

                if "All" in top_n_option:
                    filtered_df = plot_df
                    #chart_height = max(400, total_rows * 25)
                else:
                    n = int(top_n_option.split()[1])
                    filtered_df = plot_df.head(n)
                    #chart_height = 400


                # Bar Chart and Pie Chart Generation
                if chart_type == "Bar Chart":
                    #dynamic_height = max(400, len(plot_df) * 30)
                    fig_bar = px.bar(filtered_df, 
                                    x='nPepSeq', 
                                    y='Bioactivity', 
                                    log_x=True,      # The Y-axis now scales by percentage
                                    text='nPepSeq',
                                    color='nPepSeq',
                                    color_continuous_scale='Blues',
                                    custom_data=['Hover_Percentage', 'Hover_Details'],  # Include the hover data for percentage and details
                                    orientation='h',
                                    title=f'{display_sheet_name} | Total Peptide Sequences: {formatted_total}',
                                    height=450)

                    fig_bar.update_traces(textposition='inside',
                                          hovertemplate='<b>%{y}</b><br>Count: %{x}<br>Percentage: %{customdata[0]}%{customdata[1]}<extra></extra>')
                    fig_bar.update_layout(
                                        yaxis=dict(autorange="reversed", title='Bioactivities'),
                                        xaxis=dict(title='Count of Peptide Sequences (Log Scale)'),
                                        margin = dict(l=0, r=0, t=30, b=10),
                                        coloraxis_showscale=False
                                        )
                    
                    st.plotly_chart(fig_bar, use_container_width=True)

                else:
                    # 6 Generate the Pie Chart
                    if len(filtered_df) > 10:
                        pie_top = filtered_df.head(10).copy()
                        pie_rest = filtered_df.iloc[10:]
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
                                    hole=0.4,  # Creates a donut chart
                                    custom_data=['Hover_Combined'],  # Include the combined hover data
                                    title=f'{display_sheet_name} | Total Peptide Sequences: {formatted_total}',
                                    height=450)
                
                    fig_pie.update_traces(textposition='inside', 
                                    textinfo='percent+label',
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