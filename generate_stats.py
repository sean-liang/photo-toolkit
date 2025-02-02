import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import plotly.graph_objects as go
from tqdm import tqdm
import webbrowser

def scan_directory(work_dir):
    stats = defaultdict(lambda: defaultdict(int))
    work_path = Path(work_dir)
    
    # Get all files recursively
    all_files = list(work_path.rglob("*"))
    
    # Process files with progress bar
    for file_path in tqdm(all_files, desc="Scanning files"):
        if file_path.is_file():
            try:
                # Extract year and month from path
                year = file_path.parent.parent.name
                month = file_path.parent.name
                
                # Validate year and month format
                if year.isdigit() and month.isdigit():
                    year = int(year)
                    month = int(month)
                    if 1 <= month <= 12:
                        stats[year][month] += 1
            except Exception as e:
                tqdm.write(f"Error processing {file_path}: {e}")
    
    return stats

def generate_html_table(stats, years, months):
    html = '''
    <style>
        table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: right;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
    </style>
    <table>
        <tr>
            <th>Year</th>
    '''
    
    # Add month headers
    for month in months:
        html += f'<th>Month {month}</th>'
    html += '</tr>'
    
    # Add data rows
    for year in sorted(years, reverse=True):
        html += f'<tr><td>{year}</td>'
        for month in months:
            count = stats[year].get(month, 0)
            html += f'<td>{count}</td>'
        html += '</tr>'
    
    html += '</table>'
    return html

def generate_year_plot(stats, years):
    # Calculate yearly totals
    yearly_totals = []
    for year in years:
        total = sum(stats[year].values())
        yearly_totals.append(total)
    
    # Create yearly statistics plot
    fig = go.Figure(data=[
        go.Bar(x=years, y=yearly_totals)
    ])
    
    fig.update_layout(
        title_text="Yearly File Count",
        xaxis_title="Year",
        yaxis_title="Number of Files",
        showlegend=False,
        height=500,
        width=None,  
        margin=dict(l=50, r=50, t=50, b=50)  
    )
    
    return fig.to_html(full_html=False, include_plotlyjs=True)

def generate_month_plot(stats, year):
    months = list(range(1, 13))
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    monthly_counts = [stats[year].get(month, 0) for month in months]
    
    fig = go.Figure(data=[
        go.Bar(x=month_labels, y=monthly_counts)
    ])
    
    fig.update_layout(
        title_text=f"Monthly File Count - {year}",
        xaxis_title="Month",
        yaxis_title="Number of Files",
        showlegend=False,
        height=500,
        width=None,  
        margin=dict(l=50, r=50, t=50, b=50)  
    )
    
    # Create table HTML
    table_html = '''
    <style>
        .month-stats-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-family: Arial, sans-serif;
        }
        .month-stats-table th, .month-stats-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }
        .month-stats-table th {
            background-color: #f2f2f2;
        }
    </style>
    <table class="month-stats-table">
        <tr>
    '''
    
    # Add month headers
    for month in month_labels:
        table_html += f'<th>{month}</th>'
    table_html += '</tr><tr>'
    
    # Add count data
    for count in monthly_counts:
        table_html += f'<td>{count}</td>'
    table_html += '</tr></table>'
    
    # Combine plot and table
    return fig.to_html(full_html=False, include_plotlyjs=True) + table_html

def generate_report(stats, output_file):
    years = sorted(stats.keys(), reverse=True)
    months = list(range(1, 13))
    
    # Generate navigation links
    nav_links = '<div style="margin: 20px 0;">'
    nav_links += '<a href="#yearly" style="margin-right: 15px;">Yearly Statistics</a>'
    for year in years:
        nav_links += f'<a href="#{year}" style="margin-right: 15px;">{year}</a>'
    nav_links += '</div>'
    
    # Generate yearly statistics plot
    yearly_plot = generate_year_plot(stats, years)
    
    # Generate monthly plots for each year
    monthly_plots = []
    for year in years:
        monthly_plots.append((year, generate_month_plot(stats, year)))
    
    # Generate table
    table_html = generate_html_table(stats, years, months)
    
    # Combine all content
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>File Statistics Report</title>
        <meta charset="utf-8">
        <style>
            body {{
                width: 98%;
                margin: 0 auto;
                padding: 1%;
                font-family: Arial, sans-serif;
            }}
            a {{
                text-decoration: none;
                color: #0066cc;
            }}
            a:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        <h1>File Statistics Report</h1>
        {nav_links}
        
        <div id="yearly">
            <h2>Yearly Statistics</h2>
            {yearly_plot}
        </div>
        
        {''.join(f"""
        <div id="{year}">
            <h2>Monthly Statistics - {year}</h2>
            {plot}
        </div>
        """ for year, plot in monthly_plots)}
        
        <h2>Monthly Statistics Table</h2>
        {table_html}
    </body>
    </html>
    '''
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Open in default browser
    abs_path = str(Path(output_file).resolve())
    webbrowser.open(f'file://{abs_path}')

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_stats.py <work_directory>")
        sys.exit(1)
        
    work_dir = sys.argv[1]
    if not os.path.isdir(work_dir):
        print(f"Error: {work_dir} is not a directory")
        sys.exit(1)
    
    print(f"Processing directory: {work_dir}")
    stats = scan_directory(work_dir)
    
    output_file = os.path.join(work_dir, "stats.html")
    print(f"Generating report to: {output_file}")
    generate_report(stats, output_file)
    print("Report generation completed!")

if __name__ == "__main__":
    main()