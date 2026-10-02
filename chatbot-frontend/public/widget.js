(function() {
  // Configuration
  var WIDGET_BASE_URL = window.RAGCHAT_BASE_URL || "http://localhost:3000";
  var API_KEY = window.RAGCHAT_API_KEY || "";

  // Don't initialize twice
  if (document.getElementById("ragchat-widget-container")) return;

  // Create floating button
  var btn = document.createElement("div");
  btn.id = "ragchat-widget-btn";
  btn.innerHTML = "💬";
  btn.style.cssText = "position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#a855f7);color:#fff;display:flex;align-items:center;justify-content:center;font-size:24px;cursor:pointer;box-shadow:0 4px 20px rgba(99,102,241,0.4);z-index:99999;transition:transform 0.2s;";
  btn.onmouseenter = function() { btn.style.transform = "scale(1.1)"; };
  btn.onmouseleave = function() { btn.style.transform = "scale(1)"; };

  // Create widget container
  var container = document.createElement("div");
  container.id = "ragchat-widget-container";
  container.style.cssText = "position:fixed;bottom:92px;right:24px;width:380px;height:520px;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.3);z-index:99999;display:none;border:1px solid rgba(99,102,241,0.3);";

  // Create iframe
  var iframe = document.createElement("iframe");
  iframe.src = WIDGET_BASE_URL + "/widget?api_key=" + encodeURIComponent(API_KEY);
  iframe.style.cssText = "width:100%;height:100%;border:none;";
  iframe.allow = "clipboard-write";

  container.appendChild(iframe);
  document.body.appendChild(container);
  document.body.appendChild(btn);

  // Toggle
  var isOpen = false;
  btn.addEventListener("click", function() {
    isOpen = !isOpen;
    container.style.display = isOpen ? "block" : "none";
    btn.innerHTML = isOpen ? "✕" : "💬";
    btn.style.fontSize = isOpen ? "18px" : "24px";
  });
})();
