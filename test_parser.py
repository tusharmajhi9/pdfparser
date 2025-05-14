# test_parser.py
from smart_pdf_parser import PDFParser, JSONFormatter, MarkdownFormatter, ASCIIFormatter
import os

# Path to a PDF file - replace with your own PDF
pdf_path = "test_files/Jefferson_Biomedical_Services_RFP.pdf"  # Update this path to a real PDF file

# Make sure the PDF file exists
if not os.path.exists(pdf_path):
    print(f"Error: PDF file not found at {pdf_path}")
    print("Please add a PDF file to the test_files directory")
    exit(1)

print(f"Parsing PDF: {pdf_path}")

# Initialize parser
parser = PDFParser(
    detect_tables=True,
    use_toc=True,
    detect_headings=True
)

# Parse document
document = parser.parse(pdf_path)

print(f"Parsed document: {document.title} ({document.pages} pages)")
print(f"Found {len(document.sections)} top-level sections")

# Format and save outputs
output_dir = "test_outputs"
os.makedirs(output_dir, exist_ok=True)

# JSON output
json_formatter = JSONFormatter()
json_output = json_formatter.format(document)
with open(f"{output_dir}/output.json", "w", encoding="utf-8") as f:
    f.write(json_output)
print(f"JSON output saved to {output_dir}/output.json")

# Markdown output
md_formatter = MarkdownFormatter()
md_output = md_formatter.format(document)
with open(f"{output_dir}/output.md", "w", encoding="utf-8") as f:
    f.write(md_output)
print(f"Markdown output saved to {output_dir}/output.md")

# ASCII tree output
ascii_formatter = ASCIIFormatter()
ascii_output = ascii_formatter.format(document)
with open(f"{output_dir}/output.txt", "w", encoding="utf-8") as f:
    f.write(ascii_output)
print(f"ASCII tree output saved to {output_dir}/output.txt")

print("Parsing complete!")