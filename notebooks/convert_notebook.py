"""Convert old VS Code XML notebook format to Jupyter JSON format."""
import re
import json
from pathlib import Path

def convert_vscode_xml_to_ipynb(xml_file: str, output_file: str):
    """Convert old VS Code XML notebook to standard Jupyter notebook format."""
    
    with open(xml_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Initialize notebook structure
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }
    
    # Find all cells with regex
    cell_pattern = r'<VSCode\.Cell language="(.*?)">\n(.*?)</VSCode\.Cell>'
    cells = re.findall(cell_pattern, content, re.DOTALL)
    
    for language, cell_content in cells:
        # Clean up the content - remove leading/trailing whitespace but preserve internal structure
        cell_content = cell_content.rstrip('\n')
        
        if language == "markdown":
            cell = {
                "cell_type": "markdown",
                "metadata": {},
                "source": cell_content.split('\n')
            }
        else:  # python or other code
            cell = {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": cell_content.split('\n')
            }
        
        notebook["cells"].append(cell)
    
    # Write the notebook
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
    
    print(f"✓ Converted {len(notebook['cells'])} cells")
    print(f"✓ Saved to: {output_file}")

if __name__ == "__main__":
    xml_file = "health_index_improved_backup.xml"
    output_file = "health_index_improved.ipynb"
    
    convert_vscode_xml_to_ipynb(xml_file, output_file)
