from pathlib import Path 
text = Path('utility.py').read_text() 
start = text.index('def _build_driver') 
end = text.index('def _apply_window_bounds') 
print(text[start:end]) 
