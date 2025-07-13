import os
import json
import fitz  # PyMuPDF
import subprocess
import unicodedata

from django.shortcuts import render
from django.conf import settings
from .forms import PDFUploadForm

# Clean Unicode text
def clean_text(text):
    return unicodedata.normalize("NFKD", text)

# Extract text from PDF
def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text() for page in doc)

# Send text to local LLM (Ollama) and extract JSON safely
def query_llm(text):
    safe_text = clean_text(text)

    prompt = f"""
You are an intelligent parser. Extract the following fields from the resume:
- Full Name
- Email
- Phone
- Skills
- Education
- Work Experience

Respond ONLY with valid JSON in the format:
{{
  "Full Name": "...",
  "Email": "...",
  "Phone": "...",
  "Skills": ["...", "..."],
  "Education": ["...", "..."],
  "Work Experience": ["...", "..."]
}}

Text:
{safe_text}
"""

    process = subprocess.Popen(
        ['ollama', 'run', 'mistral'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    stdout_data, _ = process.communicate(input=prompt.encode("utf-8"))
    result = stdout_data.decode("utf-8", errors="ignore").strip()

    print("\n=== LLM Raw Output ===\n", result)

    # Try direct JSON load
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        pass

    # Try extracting the first JSON object manually
    brace_start = result.find('{')
    if brace_start != -1:
        count = 0
        for i in range(brace_start, len(result)):
            if result[i] == '{':
                count += 1
            elif result[i] == '}':
                count -= 1
                if count == 0:
                    try:
                        return json.loads(result[brace_start:i+1])
                    except json.JSONDecodeError:
                        break

    return {
        "error": "Could not parse JSON",
        "raw_output": result[:500]
    }

# Handle file upload view
def upload_pdf(request):
    if request.method == "POST":
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data['file']

            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

            path = os.path.join(settings.MEDIA_ROOT, file.name)
            with open(path, 'wb+') as dest:
                for chunk in file.chunks():
                    dest.write(chunk)

            text = extract_text(path)
            response = query_llm(text)

            return render(request, "pdfapp/result.html", {
                "response": json.dumps(response, indent=2).replace("\n", "<br>").replace(" ", "&nbsp;")
            })
    else:
        form = PDFUploadForm()

    return render(request, "pdfapp/upload.html", {"form": form})