import pdfplumber
import fitz
import json
import os

def extract_text(pdf_path):
    text_content = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text:
                text_content.append({
                    'page': page_num,
                    'text': text
                })
    return text_content

def extract_tables(pdf_path):
    tables_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    tables_data.append({
                        'page': page_num,
                        'table': table
                    })
    return tables_data

def extract_images(pdf_path, output_dir='images'):
    os.makedirs(output_dir, exist_ok=True)
    images = []
    doc = fitz.open(pdf_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images()
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            filename = f"page_{page_num+1}_img_{img_index+1}.{image_ext}"
            image_path = os.path.join(output_dir, filename)
            
            with open(image_path, "wb") as img_file:
                img_file.write(image_bytes)
            
            images.append({
                'page': page_num + 1,
                'path': image_path
            })
    
    doc.close()
    return images
