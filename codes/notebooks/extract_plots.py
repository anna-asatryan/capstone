import json

with open('/Users/annaasatryan/Desktop/capstone/codes/notebooks/analysis.ipynb', 'r') as f:
    nb = json.load(f)

found_poster_plots = False
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'markdown':
        content = "".join(cell.get('source', []))
        if 'POSTER PLOTS' in content:
            found_poster_plots = True
            continue
    
    if found_poster_plots and cell['cell_type'] == 'code':
        print(f"--- CELL {i} ---")
        print("".join(cell.get('source', [])))
        print("\n")
