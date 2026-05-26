export const copyToClipboard = async (text, showNotification) => {
    if (!text) return;
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        if (showNotification) showNotification("Code copied!", "success");
        return;
      } catch (err) {
        console.error("Clipboard API failed, trying fallback...", err);
      }
    }
    try {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-9999px";
      textArea.style.top = "0";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);
      if (successful) {
        if (showNotification) showNotification("Code copied!", "success");
      } else {
        throw new Error("execCommand copy was unsuccessful");
      }
    } catch (err) {
      console.error("Fallback copy failed: ", err);
      if (showNotification) showNotification("Failed to copy code", "error");
    }
  };