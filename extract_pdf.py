import pdfplumber

def extract_pdf_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

if __name__ == "__main__":
    pdf_path = r"c:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\report_dataset_IRCTC.pdf"
    text = extract_pdf_text(pdf_path)
    with open("pdf_content.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("Text extracted to pdf_content.txt")