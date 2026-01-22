from pathlib import Path 
lines=Path('utility.py').read_text(errors='ignore').splitlines() 
start=730 
end=880 
for i in range(start-1,end): 
    print('%04d: '%(i+1) + lines[i]) 
