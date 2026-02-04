import json
import tempfile
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional dependency
    fitz = None

DATA_PATH = Path(__file__).resolve().parents[1] / "tracing_positional.json"
PDF_PATH = Path(__file__).resolve().parents[1] / "documents" / "tracing_positional_bias_in_finance_decision_making.pdf"


@st.cache_data
def load_tracing_data_from_path(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_tracing_data_from_bytes(raw: bytes):
    return json.loads(raw.decode("utf-8"))


def ensure_index_bounds(index: int, max_index: int) -> int:
    if index < 0:
        return 0
    if index > max_index:
        return max_index
    return index


def generate_json_from_pdf(pdf_bytes: bytes, api_key: str, output_dir: Path) -> Path:
    raise NotImplementedError("PDF-to-JSON generation is not implemented yet.")


def build_placeholder_image(width: int = 900, height: int = 600) -> Image.Image:
    img = Image.new("RGB", (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    text = "Image Placeholder"
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_width = right - left
    text_height = bottom - top
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    draw.text((x, y), text, fill=(80, 80, 80), font=font)
    return img


@st.cache_data
def render_pdf_page_from_path(path: Path, page_index: int, zoom: float = 2.0) -> Image.Image:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not available. Install with: pip install pymupdf")
    with fitz.open(path) as doc:
        page_index = max(0, min(page_index, doc.page_count - 1))
        page = doc.load_page(page_index)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        mode = "RGB"
        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        return img


@st.cache_data
def render_pdf_page_from_bytes(raw: bytes, page_index: int, zoom: float = 2.0) -> Image.Image:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not available. Install with: pip install pymupdf")
    with fitz.open(stream=raw, filetype="pdf") as doc:
        page_index = max(0, min(page_index, doc.page_count - 1))
        page = doc.load_page(page_index)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        mode = "RGB"
        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        return img


def main():
    st.set_page_config(page_title="Tracing Positional Viewer", layout="wide")

    st.sidebar.header("Data Sources")
    api_key = st.sidebar.text_input("API Key", type="password")
    json_mode = st.sidebar.radio("JSON Source", ["Upload JSON", "Generate from PDF"])
    pdf_upload = st.sidebar.file_uploader("Upload PDF", type=["pdf"])
    json_upload = None
    if json_mode == "Upload JSON":
        json_upload = st.sidebar.file_uploader("Upload JSON", type=["json"])

    data = None
    if "json_hash" not in st.session_state:
        st.session_state.json_hash = None
    if "pdf_hash" not in st.session_state:
        st.session_state.pdf_hash = None
    if json_mode == "Generate from PDF" and pdf_upload is not None:
        if not api_key:
            st.sidebar.warning("API key required to generate JSON from PDF.")
        else:
            try:
                temp_dir = Path(tempfile.mkdtemp(prefix="tracing_json_"))
                json_path = generate_json_from_pdf(pdf_upload.getvalue(), api_key, temp_dir)
                data = load_tracing_data_from_path(json_path)
                st.session_state.pos_index = 0
            except NotImplementedError as exc:
                st.sidebar.warning(str(exc))

    if data is None:
        if json_upload is not None:
            json_bytes = json_upload.getvalue()
            json_hash = hash(json_bytes)
            if st.session_state.json_hash != json_hash:
                st.session_state.json_hash = json_hash
                st.session_state.pos_index = 0
            data = load_tracing_data_from_bytes(json_bytes)
        else:
            st.info("Upload a JSON file (or choose Generate from PDF and upload a PDF) to begin.")
            return
    if not isinstance(data, list) or len(data) == 0:
        st.error("No tracing data found or unexpected format.")
        return

    if "pos_index" not in st.session_state:
        st.session_state.pos_index = 0

    max_index = len(data) - 1
    current_index = ensure_index_bounds(st.session_state.pos_index, max_index)
    st.session_state.pos_index = current_index

    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        btn_prev, btn_next = st.columns([1, 1])
        with btn_prev:
            prev_clicked = st.button("Prev", use_container_width=True, disabled=current_index == 0)
        with btn_next:
            next_clicked = st.button("Next", use_container_width=True, disabled=current_index == max_index)

        if prev_clicked:
            st.session_state.pos_index = ensure_index_bounds(current_index - 1, max_index)
        if next_clicked:
            st.session_state.pos_index = ensure_index_bounds(current_index + 1, max_index)

        current_item = data[st.session_state.pos_index]
        if isinstance(current_item, dict):
            markdown_text = current_item.get("text", "")
        else:
            markdown_text = str(current_item)

        st.markdown(markdown_text, unsafe_allow_html=True)

    with right_col:
        page_no = 0
        if isinstance(current_item, dict):
            if current_item.get("page_no") is not None:
                page_no = int(current_item.get("page_no"))
            elif current_item.get("page") is not None:
                page_no = int(current_item.get("page"))

        if fitz is None:
            st.warning("PyMuPDF is required to render PDF pages. Install with: pip install pymupdf")
            st.image(build_placeholder_image(), use_container_width=True)
        else:
            try:
                if pdf_upload is not None:
                    img = render_pdf_page_from_bytes(pdf_upload.getvalue(), page_no)
                else:
                    if not PDF_PATH.exists():
                        st.warning(f"PDF not found at {PDF_PATH}")
                        st.image(build_placeholder_image(), use_container_width=True)
                        return
                    img = render_pdf_page_from_path(PDF_PATH, page_no)
                if isinstance(current_item, dict) and current_item.get("bbox") is not None:
                    bbox = current_item.get("bbox")
                    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                        width, height = img.size
                        x0, y0, x1, y1 = bbox
                        x0 = int(x0 * width)
                        x1 = int(x1 * width)
                        y0 = int(y0 * height)
                        y1 = int(y1 * height)
                        draw = ImageDraw.Draw(img)
                        draw.rectangle([x0, y0, x1, y1], outline=(220, 20, 60), width=4)
                st.image(img, use_container_width=True)
            except Exception as exc:
                st.warning(f"Failed to render PDF page {page_no}: {exc}")
                st.image(build_placeholder_image(), use_container_width=True)


if __name__ == "__main__":
    main()
