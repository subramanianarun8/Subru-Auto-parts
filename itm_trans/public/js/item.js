frappe.ui.form.on("Item", {
  before_save(frm) {
    const text = (frm.doc.item_name || "").trim();

    if (!text) {
      return frm.set_value("custom_translated_name", "");
    }

    // Avoid another translation call when this exact Item Name was already
    // translated successfully during the current form session.
    if (frm.__last_translated_text === text && frm.doc.custom_translated_name) {
      return;
    }

    // Return the Promise so Frappe waits for a successful translation before
    // completing the save, without using a synchronous/blocking XHR request.
    // Translation-provider failures are swallowed intentionally: an external
    // service outage must never prevent the Item itself from being saved.
    return frappe
      .call({
        method: "itm_trans.api.translate_en_to_ar",
        args: { text },
      })
      .then((r) => {
        const translated = (r && typeof r.message === "string")
          ? r.message.trim()
          : "";

        // Empty response means the provider failed after retries. Keep the
        // existing value and allow Item save to continue. Do not cache this
        // attempt, so the next save can retry automatically.
        if (!translated) {
          console.warn("itm_trans: translation unavailable; Item will save without updating Arabic name");
          return;
        }

        frm.__last_translated_text = text;

        if (frm.doc.custom_translated_name !== translated) {
          return frm.set_value("custom_translated_name", translated);
        }
      })
      .catch((error) => {
        console.warn("itm_trans: translation request failed; Item save will continue", error);
      });
  },
});
