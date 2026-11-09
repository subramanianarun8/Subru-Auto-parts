import re
import time

import frappe
from deep_translator import GoogleTranslator


PHRASES = {
    "SPARK PLUG": "شمعة احتراق",
    "OIL FILTER": "فلتر زيت",
    "AIR FILTER": "فلتر هواء",
    "FUEL FILTER": "فلتر وقود",
    "BRAKE PAD": "فحمات فرامل",
    "BRAKE PADS": "فحمات فرامل",
    "WATER PUMP": "طرمبة ماء",
    "FUEL PUMP": "طرمبة وقود",
    "OIL PUMP": "طرمبة زيت",
    "TIMING BELT": "سير توقيت",
    "FAN BELT": "سير مروحة",
    "SHOCK ABSORBER": "مساعد",
    "CONTROL ARM": "ذراع تحكم",
    "BALL JOINT": "مفصل كروي",
    "WHEEL BEARING": "رمان بلي",
    "CLUTCH KIT": "طقم كلتش",
    "RADIATOR CAP": "غطاء رديتر",
    "ENGINE MOUNT": "قاعدة مكينة",
    "GEAR MOUNT": "قاعدة قير",
}

BRANDS = {
    "BOSCH": "بوش",
    "TOYOTA": "تويوتا",
    "NISSAN": "نيسان",
    "HONDA": "هوندا",
    "HYUNDAI": "هيونداي",
    "KIA": "كيا",
    "MAZDA": "مازدا",
    "MITSUBISHI": "ميتسوبيشي",
    "ISUZU": "ايسوزو",
    "SUZUKI": "سوزوكي",
    "FORD": "فورد",
    "CHEVROLET": "شفروليه",
    "BMW": "بي ام دبليو",
    "MERCEDES": "مرسيدس",
    "AUDI": "أودي",
    "VOLKSWAGEN": "فولكس واجن",
    "LEXUS": "لكزس",
    "DENSO": "دينسو",
    "NGK": "إن جي كي",
}

KEEP_WORDS = {
    "AFM", "OEM", "RH", "LH", "ABS", "AC", "A/C", "AT", "MT", "4WD", "2WD", "CVT"
}

GOOGLE_ERROR_MARKERS = (
    "error 500",
    "server error",
    "that's an error",
    "that’s an error",
    "there was an error",
    "please try again later",
    "that's all we know",
    "that’s all we know",
)


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def is_part_number(token):
    token = token.strip()
    if not token:
        return False

    if re.fullmatch(r"[A-Z0-9]+(?:[-/][A-Z0-9]+)+", token, flags=re.IGNORECASE):
        return True

    if re.fullmatch(r"[0-9][0-9A-Z./-]*", token, flags=re.IGNORECASE):
        return True

    return False


def should_keep_token(token):
    if not token:
        return True

    if is_part_number(token):
        return True

    if token in KEEP_WORDS:
        return True

    # Keep already-Arabic tokens as-is.
    if re.search(r"[\u0600-\u06FF]", token):
        return True

    # Leave common upper-case short codes as-is (CTR, FR, RR, etc.).
    if re.fullmatch(r"[A-Z]{2,5}", token):
        return True

    return False


def is_bad_translation(value):
    value = normalize_text(value)
    if not value:
        return True

    lowered = value.lower()
    return any(marker in lowered for marker in GOOGLE_ERROR_MARKERS)


def translate_text_safely(text, retries=2):
    """Translate one English text segment to Arabic without leaking provider errors."""
    text = normalize_text(text)
    if not text:
        return "", True

    for attempt in range(retries + 1):
        try:
            translated = GoogleTranslator(source="en", target="ar").translate(text)
            translated = normalize_text(translated)

            if is_bad_translation(translated):
                raise ValueError("Google Translate returned an error page instead of translated text")

            return translated, True
        except Exception:
            if attempt < retries:
                time.sleep(0.35 * (attempt + 1))

    frappe.log_error(
        title="Item Translation Error",
        message=f"Arabic translation failed after retries for text: {text}",
    )
    return text, False


def translate_unknown_segments(working):
    """Translate contiguous unknown words together to reduce Google requests."""
    parts = working.split(" ")
    final_parts = []
    pending = []
    all_successful = True

    def flush_pending():
        nonlocal all_successful
        if not pending:
            return

        translated, successful = translate_text_safely(" ".join(pending))
        final_parts.append(translated)
        all_successful = all_successful and successful
        pending.clear()

    for token in parts:
        if not token:
            continue

        if should_keep_token(token):
            flush_pending()
            final_parts.append(token)
        else:
            pending.append(token)

    flush_pending()
    return " ".join(final_parts), all_successful


@frappe.whitelist()
def translate_en_to_ar(text):
    """Translate an Item name to Arabic while keeping codes/part numbers intact.

    External translation failure must never raise into the Item save request.
    Returning an empty string on provider failure lets the Item save continue and
    allows the next save to retry instead of storing Google's error page.
    """
    try:
        text = normalize_text(text)
        if not text:
            return ""

        working = text.upper()

        # Force known automotive phrases first.
        for en, ar in PHRASES.items():
            working = working.replace(en, ar)

        # Force known brands.
        for en, ar in BRANDS.items():
            working = working.replace(en, ar)

        translated, successful = translate_unknown_segments(working)

        if not successful or is_bad_translation(translated):
            return ""

        return translated

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Item Translation Error")
        return ""
