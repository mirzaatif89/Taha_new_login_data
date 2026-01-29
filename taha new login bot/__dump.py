import pathlib 
lines=pathlib.Path('utility.py').read_text().splitlines() 
start=next(i for i,l in enumerate(lines) if l.startswith('def _build_driver')) 
end=next(i for i,l in enumerate(lines[start+1:], start+1) if l.startswith('def _apply_window_bounds')) 
print('|'.join(f\"{i+1:04d}: {lines[i]}\" for i in range(start,end)))
