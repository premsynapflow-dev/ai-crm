(function () {
  var currentScript = document.currentScript;
  if (!currentScript) {
    var scripts = document.getElementsByTagName("script");
    currentScript = scripts[scripts.length - 1];
  }

  var apiKey = currentScript ? currentScript.getAttribute("data-api-key") : "";
  var scriptSrc = currentScript ? currentScript.src : "";
  var endpoint = scriptSrc ? new URL("/webhook/complaint", scriptSrc).href : "/webhook/complaint";

  var style = document.createElement("style");
  style.textContent = "\
#complaint-widget-btn{position:fixed;bottom:20px;right:20px;background:#111827;color:#fff;border:none;border-radius:999px;padding:12px 16px;cursor:pointer;z-index:2147483647;font-family:Arial,sans-serif;font-size:14px;}\
#complaint-widget-popup{position:fixed;bottom:72px;right:20px;width:320px;background:#fff;border:1px solid #d1d5db;border-radius:8px;padding:12px;box-shadow:0 8px 24px rgba(0,0,0,.18);z-index:2147483647;font-family:Arial,sans-serif;display:none;}\
#complaint-widget-popup h3{margin:0 0 10px;font-size:16px;}\
#complaint-widget-popup label{display:block;margin:8px 0 4px;font-size:12px;color:#374151;}\
#complaint-widget-popup input,#complaint-widget-popup textarea{width:100%;box-sizing:border-box;border:1px solid #d1d5db;border-radius:6px;padding:8px;font-size:13px;}\
#complaint-widget-popup textarea{min-height:84px;resize:vertical;}\
#complaint-widget-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:10px;}\
#complaint-widget-actions button{border:1px solid #111827;background:#111827;color:#fff;border-radius:6px;padding:8px 10px;cursor:pointer;font-size:12px;}\
#complaint-widget-actions button.secondary{background:#fff;color:#111827;}\
#complaint-widget-status{margin-top:8px;font-size:12px;color:#059669;}\
#complaint-widget-status.error{color:#b91c1c;}\
";
  document.head.appendChild(style);

  var button = document.createElement("button");
  button.id = "complaint-widget-btn";
  button.type = "button";
  button.textContent = "Report Issue";

  var popup = document.createElement("div");
  popup.id = "complaint-widget-popup";
  popup.innerHTML = "\
    <h3>Report Issue</h3>\
    <label for='cw-email'>Email</label>\
    <input id='cw-email' type='email' placeholder='you@example.com' />\
    <label for='cw-phone'>Phone</label>\
    <input id='cw-phone' type='text' placeholder='+91...' />\
    <label for='cw-message'>Message</label>\
    <textarea id='cw-message' placeholder='Describe your issue' required></textarea>\
    <div id='complaint-widget-actions'>\
      <button type='button' class='secondary' id='cw-close'>Close</button>\
      <button type='button' id='cw-submit'>Submit</button>\
    </div>\
    <div id='complaint-widget-status'></div>\
  ";

  document.body.appendChild(button);
  document.body.appendChild(popup);

  var closeBtn = popup.querySelector("#cw-close");
  var submitBtn = popup.querySelector("#cw-submit");
  var emailEl = popup.querySelector("#cw-email");
  var phoneEl = popup.querySelector("#cw-phone");
  var messageEl = popup.querySelector("#cw-message");
  var statusEl = popup.querySelector("#complaint-widget-status");

  function setStatus(message, isError) {
    statusEl.textContent = message || "";
    statusEl.className = isError ? "error" : "";
  }

  button.addEventListener("click", function () {
    popup.style.display = popup.style.display === "none" || popup.style.display === "" ? "block" : "none";
    setStatus("");
  });

  closeBtn.addEventListener("click", function () {
    popup.style.display = "none";
    setStatus("");
  });

  submitBtn.addEventListener("click", async function () {
    var message = (messageEl.value || "").trim();
    if (!message) {
      setStatus("Message is required.", true);
      return;
    }
    if (!apiKey) {
      setStatus("Widget is missing data-api-key.", true);
      return;
    }

    submitBtn.disabled = true;
    setStatus("Submitting...");

    try {
      var response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-api-key": apiKey
        },
        body: JSON.stringify({
          message: message,
          source: "widget",
          customer_email: (emailEl.value || "").trim() || null,
          customer_phone: (phoneEl.value || "").trim() || null
        })
      });

      if (!response.ok) {
        throw new Error("Request failed with status " + response.status);
      }

      setStatus("Issue submitted successfully.", false);
      messageEl.value = "";
      emailEl.value = "";
      phoneEl.value = "";
    } catch (err) {
      setStatus("Failed to submit issue.", true);
    } finally {
      submitBtn.disabled = false;
    }
  });
})();
