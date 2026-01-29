import pathlib 
lines = pathlib.Path('utility.py').read_text().splitlines() 
for i in range(1060, 1140): 
    print(f'{i+1:04d}: {lines[i]}') 
