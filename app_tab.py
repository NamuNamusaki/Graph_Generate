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

def map_group_detail(sheet_name):
    detail_mapping = {
        "Group 1": "Exact Match",
        "Group 2": "Shorter Match",
        "Group 3a": "Longer Match (Single Functional Domain)",
        "Group 3b": "Longer Match (Multiple Functional Domains)"
    }
    return detail_mapping.get(sheet_name, "")

def load_group_data(uploaded_files):

    return

def prep_plot_df(df):
    return

def plot_pie():
    return

def plot_bar():
    return



#Main Function
def generate_dashboard_chart (file_paths,chart_type):
    """
    Iterates through a list of Excel files, opens EVERY sheet inside them, 
    and generates Bar and Pie charts for sheets.
    """
    # 1 แปลงชื่อกลุ่มให้อยู่ใน Dict
    tab_title = ['Group 1', 'Group 2', 'Group 3a', 'Group 3b']
    tabs = st.tabs(tab_title)
    tab_dict = dict(zip(tab_title, tabs))

    # 2 Route to tab
    for file in file_paths:
        raw_name = file.name.replace('.csv', '')
        group_name = get_display_names(raw_name)
        group_detail = map_group_detail(group_name)

    # 1 loop through every csv file
    for i,file in enumerate(file_paths):         

        # build grid column
        if i % 2 == 0:
            cols = st.columns(2)
        col = cols[i %2]
        # 3 read csv file
        df = pd.read_csv(file)  # Read the CSV file into a DataFrame
                     
        # 2 Extract the display name from the file name
        raw_name = file.name.replace('.csv', '')  # Remove the .csv extension
        group_name = get_display_names(raw_name)  # Use the regex function to extract the display name
        group_detail = map_group_detail(group_name)

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
        
        # -------------- Dashboard -----------------------
        with col:
            with st.container(border=True):
                st.subheader(f" {group_name} : {group_detail}")

                # Multiselect Filter
                all_bioactivities = plot_df['Bioactivity'].tolist()
                select_bioac = st.multiselect(
                    "Select Bioactivities:",
                    options=all_bioactivities,
                    default=[],
                    key=f"select_bioac_{group_name}"
                )
                # Apply Multiselect
                if select_bioac:
                    filtered_df = plot_df[plot_df['Bioactivity'].isin(select_bioac)]
                else:
                    filtered_df = plot_df.copy()

                total_rows = len(plot_df) # Count the exact number of the group of Bioactivity


                # Bar Chart and Pie Chart Generation
                if chart_type == "Bar Chart":
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
                        width=200,
                        index=0,
                        key=f"top_n_{group_name}"
                    )

                    if "All" in top_n_option:
                        final_df = filtered_df
                    else:
                        n = int(top_n_option.split()[1])
                        final_df = filtered_df.head(n)
                        #chart_height = 400
                    #dynamic_height = max(400, len(plot_df) * 30)
                    fig_bar = px.bar(final_df, 
                                    x='nPepSeq', 
                                    y='Bioactivity', 
                                    log_x=True,      # The Y-axis now scales by percentage
                                    text='nPepSeq',
                                    color='nPepSeq',
                                    color_continuous_scale='Blues',
                                    custom_data=['Hover_Percentage', 'Hover_Details'],  # Include the hover data for percentage and details
                                    orientation='h',
                                    title=f'Total Peptide Sequences: {formatted_total}',
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
                                    #hole=0.4,  # Creates a donut chart
                                    custom_data=['Hover_Combined'],  # Include the combined hover data
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
            options=["Pie Chart","Bar Chart"],
            index=0,
        )
    generate_dashboard_chart(uploaded_files, chart_type)
    create_sum_table(uploaded_files)