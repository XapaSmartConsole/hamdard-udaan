from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from openai import OpenAI
from PIL import Image
from pdf2image import convert_from_bytes
import io, base64, os

router = APIRouter(prefix="/api/kyc", tags=["KYC OCR"])


def image_to_base64_from_pil(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()


@router.post("/extract-number")
async def extract_document_number(
    document_type: str = Form(...),
    file: UploadFile = File(...)
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    client = OpenAI(api_key=api_key)

    if file.content_type == "application/pdf":
        pdf_bytes = await file.read()
        images = convert_from_bytes(pdf_bytes)
        image = images[0].convert("RGB")
    elif file.content_type in ["image/jpeg", "image/png"]:
        image = Image.open(file.file).convert("RGB")
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload JPG, PNG, or PDF only."
        )

    image_base64 = image_to_base64_from_pil(image)

    prompt = f"""
    You are a KYC assistant.
    Extract ONLY the document number.

    Document type: {document_type}

    Rules:
    - PAN: 10 characters (ABCDE1234F)
    - GST: 15 characters
    - Address Proof: Aadhaar or official ID number
    - Respond ONLY with the number
    """

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_base64}"
                    }
                ]
            }]
        )

        return {
            "document_number": response.output_text.strip()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
