
def extract_text_from_pdf_with(pdf_path):
    funcs = [extract_text_from_pdf_with_fitz, 
             extract_text_from_pdf_with_pdfminer,
             extract_text_from_pdf_with_pypdf2,
             extract_text_from_image_pdf_with_ocr,
             extract_text_from_scanned_pdf
             ]
    text = None
    # for fun in funcs:
    try:
        if not is_scanned_pdf(pdf_path):
            fun = extract_text_from_pdf_with_pdfminer
            text = fun(pdf_path)
            return text
        else:
            # fun = extract_text_from_scanned_pdf
            # text = fun(pdf_path)
            # return text
            from core.mcp_gateway import get_mcp_gateway
            import asyncio
            
            async def _req_mcp():
                gateway = get_mcp_gateway()
                params = {"messages": [{"role": "user", "content": f"Please extract all readable text content from the following file path: {pdf_path}"}]}
                try:
                    resp = await gateway.call("ai_mcp", "chat_analyze", params)
                    if isinstance(resp, dict) and 'response' in resp:
                        return resp['response']
                    return str(resp)
                except Exception as e:
                    return f"OCR Extraction failed via AI: {e}"
                    
            text = asyncio.run(_req_mcp())
            return text
    except Exception as e:
        pass
    return text

def is_scanned_pdf(pdf_path):
    from pdfminer.high_level import extract_text
    text = extract_text(pdf_path)
    if len(text.strip()) < 100:  # 如果提取的文本少于100个字符，可能是扫描版
        return True
    return False

def extract_text_from_pdf_with_fitz(pdf_path):
    import fitz  # PyMuPDF
    document = fitz.open(pdf_path)  # 打开PDF文件
    text = ""
    for page_num in range(len(document)):
        page = document.load_page(page_num)  # 加载每一页
        text += page.get_text()  # 提取该页的文本内容
    return text

def extract_text_from_pdf_with_pdfminer(pdf_path):
    from pdfminer.high_level import extract_text
    text = extract_text(pdf_path)  # 提取文本
    return text

def extract_text_from_pdf_with_pypdf2(pdf_path):
    import PyPDF2
    pdf_file = open(pdf_path, 'rb')
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page_num in range(len(pdf_reader.pages)):
        text += pdf_reader.pages[page_num].extract_text()
    pdf_file.close()
    return text

def extract_text_from_scanned_pdf(pdf_path):
    import pytesseract
    from PIL import Image
    import fitz  # PyMuPDF
    document = fitz.open(pdf_path)
    text = ""
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        pix = page.get_pixmap()  # 获取页面图像
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)  # 将图像数据转换为PIL图像
        page_text = pytesseract.image_to_string(img, lang='chi_sim+eng')  # 使用OCR识别文本，支持中文和英文
        text += page_text
    return text

def extract_text_from_image_pdf_with_ocr(pdf_path):
    import pytesseract
    from PIL import Image
    import fitz  # PyMuPDF
    document = fitz.open(pdf_path)
    text = ""
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        pix = page.get_pixmap()  # 获取页面图像
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)  # 将图像数据转换为PIL图像
        page_text = pytesseract.image_to_string(img, lang='chi_sim+eng')  # 使用OCR识别文本，支持中文和英文
        text += page_text
    return text