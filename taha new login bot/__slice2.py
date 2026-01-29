import pathlib 
lines = pathlib.Path('utility.py').read_text().splitlines() 
for i in range(430, 620): 
    print(f'{i+1:04d}: {lines[i]}') 
