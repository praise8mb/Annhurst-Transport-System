import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io
import os
import re
from datetime import datetime
from pdf2image import convert_from_bytes
import cv2
import numpy as np

# 🔧 Manually set tesseract path if not added to system PATH
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Set up directories
UPLOAD_FOLDER = "uploads"
LOG_FILE = "dataset.csv"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize dataset file if not present
if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=[
        "Driver ID", "Driver Name", "Amount", "Date", "Receipt Type", "Timestamp"
    ]).to_csv(LOG_FILE, index=False)

st.title("Receipt Upload and Logging System")

# Form
with st.form("receipt_form"):
    driver_id = st.text_input("Enter Driver ID (e.g., A12)")
    receipt_type = st.selectbox("Select Receipt Type", ["DR receipt", "AA conf"])
    date_input = st.date_input("Enter Date of Transaction")
    uploaded_file = st.file_uploader("Upload Receipt (Image or PDF)", type=["png", "jpg", "jpeg", "pdf"])
    submitted = st.form_submit_button("Upload and Process")

if submitted and uploaded_file:
    original_filename = uploaded_file.name

    # Convert to image if PDF
    if uploaded_file.type == "application/pdf":
        images = convert_from_bytes(uploaded_file.read())
        image = images[0]  # Take the first page
    else:
        image = Image.open(uploaded_file)

    # Preprocess image using OpenCV
    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    preprocessed_image = Image.fromarray(thresh)

    # OCR extraction
    text = pytesseract.image_to_string(preprocessed_image)

    # Display OCR text output for debug
    st.text_area("OCR Text", text, height=200)

    # Extract amount with more general pattern
    amount_match = re.search(r"(?:[₦N]\s?)?(\d{1,3}(?:[\s,]?\d{3})*(?:\.\d{1,2})?)", text)
    amount = amount_match.group(1).replace(" ", "") if amount_match else "Unknown"
    if amount != "Unknown":
        amount_numeric = float(amount.replace(",", ""))
        if amount_numeric >= 1000:
            if amount_numeric >= 100000:
                short_value = int(amount_numeric / 1000)
                amount_short = f"N{short_value}k"
            elif amount_numeric >= 10000:
                amount_short = f"N{int(amount_numeric / 1000)}k"
            elif amount_numeric >= 1000:
                amount_short = f"N{round(amount_numeric / 1000, 1)}k"
        elif amount_numeric >= 100:
            amount_short = f"N{int(amount_numeric / 100)}h"
        else:
            amount_short = f"N{int(amount_numeric)}"
        amount = f"N{amount}"  # Full amount for dataset
    else:
        amount_short = "Unknown"

    # Format the user-entered date
    parsed_date = datetime.strptime(str(date_input), "%Y-%m-%d")
    date_for_dataset = parsed_date.strftime("%d/%m/%Y")
    date_for_filename = parsed_date.strftime("%d.%m.%y")

    # Extract driver name more reliably by handling both same-line and next-line
    if receipt_type == "DR receipt":
        lines = text.splitlines()
        driver_name = "Unknown"
        for i, line in enumerate(lines):
            if "Sender Details" in line:
                same_line_match = re.search(r"Sender Details\s*(.+)", line)
                if same_line_match:
                    name_candidate = same_line_match.group(1).strip()
                    if len(name_candidate.split()) >= 2:
                        driver_name = name_candidate.title()
                        break
                if i + 1 < len(lines):
                    next_line_candidate = lines[i + 1].strip()
                    if len(next_line_candidate.split()) >= 2:
                        driver_name = next_line_candidate.title()
                        break
    else:
        driver_name = "-"

    # Set folder for file saving
    save_folder = os.path.join(UPLOAD_FOLDER, "DR_receipts" if receipt_type == "DR receipt" else "AA_conf")
    os.makedirs(save_folder, exist_ok=True)

    new_filename = f"{driver_id},{amount_short},{date_for_filename},{receipt_type}".replace(" ", "_") + os.path.splitext(original_filename)[1]
    save_path = os.path.join(save_folder, new_filename)

    if uploaded_file.type == "application/pdf":
        images[0].save(save_path)
    else:
        image.save(save_path)

    new_record = {
        "Driver ID": driver_id,
        "Driver Name": driver_name,
        "Amount": amount,
        "Date": date_for_dataset,
        "Receipt Type": receipt_type,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    df = pd.read_csv(LOG_FILE)
    df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    df.to_csv(LOG_FILE, index=False)

    st.success("Receipt uploaded and logged successfully!")
    st.code(new_filename, language="text")
    st.write("Extracted Info:")
    st.json(new_record)

st.markdown("---")
st.subheader("Upload History")
log_df = pd.read_csv(LOG_FILE)
st.dataframe(log_df.tail(10))
