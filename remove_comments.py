#!/usr/bin/env python3
"""
Script to remove all comments from Python files and Jupyter notebooks in the project.
"""

import os
import json
import re
import glob
from pathlib import Path

def remove_python_comments(content):
    """Remove comments from Python code."""
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove inline comments but preserve strings
        in_string = False
        quote_char = None
        cleaned_line = ""
        i = 0
        
        while i < len(line):
            char = line[i]
            
            if not in_string:
                if char in ['"', "'"]:
                    in_string = True
                    quote_char = char
                    cleaned_line += char
                elif char == '#' and i > 0 and line[i-1] != '\\':
                    # Found a comment, stop here
                    break
                else:
                    cleaned_line += char
            else:
                if char == quote_char and (i == 0 or line[i-1] != '\\'):
                    in_string = False
                    quote_char = None
                cleaned_line += char
            
            i += 1
        
        # Remove trailing whitespace
        cleaned_line = cleaned_line.rstrip()
        cleaned_lines.append(cleaned_line)
    
    return '\n'.join(cleaned_lines)

def remove_notebook_comments(notebook_path):
    """Remove comments from Jupyter notebook code cells."""
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
    
    modified = False
    
    for cell in notebook.get('cells', []):
        if cell.get('cell_type') == 'code':
            source = cell.get('source', [])
            if isinstance(source, list):
                # Process each line in the source
                cleaned_source = []
                for line in source:
                    if isinstance(line, str):
                        # Remove comments from this line
                        cleaned_line = remove_python_comments(line)
                        cleaned_source.append(cleaned_line)
                    else:
                        cleaned_source.append(line)
                
                if cleaned_source != source:
                    cell['source'] = cleaned_source
                    modified = True
    
    if modified:
        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=1, ensure_ascii=False)
        print(f"Removed comments from: {notebook_path}")
        return True
    
    return False

def main():
    """Main function to process all files."""
    # Get all Python files
    python_files = glob.glob("**/*.py", recursive=True)
    
    # Get all Jupyter notebook files
    notebook_files = glob.glob("**/*.ipynb", recursive=True)
    
    print(f"Found {len(python_files)} Python files")
    print(f"Found {len(notebook_files)} Jupyter notebook files")
    
    # Process Python files
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            cleaned_content = remove_python_comments(content)
            
            if cleaned_content != content:
                with open(py_file, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
                print(f"Removed comments from: {py_file}")
        except Exception as e:
            print(f"Error processing {py_file}: {e}")
    
    # Process Jupyter notebook files
    for nb_file in notebook_files:
        try:
            remove_notebook_comments(nb_file)
        except Exception as e:
            print(f"Error processing {nb_file}: {e}")
    
    print("Comment removal completed!")

if __name__ == "__main__":
    main()
