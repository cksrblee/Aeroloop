import os
import glob
import base64
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm
from pdf2image import convert_from_path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# Load env variables
load_dotenv()

def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def process_pdf(pdf_path, output_path, model):
    print(f"Processing {pdf_path}...")
    pages = convert_from_path(pdf_path, dpi=200)
    
    extracted_text = []
    
    for i, page in enumerate(tqdm(pages, desc=f"Pages in {Path(pdf_path).name}")):
        base64_image = image_to_base64(page)
        
        system_msg = SystemMessage(
            content="You are an expert regulatory parser. Your task is to extract all text, tables, and structures from the provided page image of an FAA regulation. Maintain the hierarchical structure (parts, subparts, sections), lists, and formatting precisely in Markdown format. Do not add any conversational filler. Only return the extracted Markdown."
        )
        
        human_msg = HumanMessage(
            content=[
                {"type": "text", "text": "Extract the contents of this page into Markdown:"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        )
        
        try:
            response = model.invoke([system_msg, human_msg])
            extracted_text.append(f"<!-- PAGE {i+1} -->\n{response.content}\n")
        except Exception as e:
            print(f"Error processing page {i+1}: {e}")
            extracted_text.append(f"<!-- ERROR ON PAGE {i+1}: {e} -->\n")
            
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(extracted_text))
        
    print(f"Saved extracted text to {output_path}")

def main():
    raw_dir = Path("data/regulations/raw")
    processed_dir = Path("data/regulations/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_files = list(raw_dir.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in data/regulations/raw/")
        return
        
    model = ChatOpenAI(model="gpt-5.4-mini", temperature=0.0)
    
    for pdf_file in pdf_files:
        output_file = processed_dir / f"{pdf_file.stem}.md"
        process_pdf(pdf_file, output_file, model)

if __name__ == "__main__":
    main()
