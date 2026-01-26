from pathlib import Path 
lines=Path('utility.py').read_text().splitlines() 
start=510 
end=545 
for idx,line in enumerate(lines[start:end],start+1): 
    print(f\"{idx:04d}: {line}\") 
