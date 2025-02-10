document.addEventListener("DOMContentLoaded", function () {
    // Find all comment spans within code blocks
    let allCommentSpans = Array.from(document.querySelectorAll("pre code span.c1"));
  
    // (Optional) Filter out empty comment spans
    allCommentSpans = allCommentSpans.filter(span => span.textContent.trim() !== "");
  
    // Group comment spans based on their vertical positions.
    // We assume that spans that appear on consecutive lines have a small vertical gap.
    let groups = [];
    let currentGroup = [];
  
    allCommentSpans.forEach((span, index) => {
      // Hide the span (CSS should do this, but this is extra insurance)
      span.style.display = "none";
  
      if (currentGroup.length === 0) {
        currentGroup.push(span);
      } else {
        let lastSpan = currentGroup[currentGroup.length - 1];
        // Get the bounding rectangles
        let lastRect = lastSpan.getBoundingClientRect();
        let curRect = span.getBoundingClientRect();
        
        // Calculate the gap between the bottom of the last span and the top of the current span.
        // Adjust the threshold (here 10 pixels) as needed.
        let gap = curRect.top - (lastRect.top + lastRect.height);
        
        if (gap < 10) {
          // They are close enough to be considered on consecutive lines.
          currentGroup.push(span);
        } else {
          groups.push(currentGroup);
          currentGroup = [span];
        }
      }
    });
  
    if (currentGroup.length > 0) {
      groups.push(currentGroup);
    }
  
    // For each group, create one toggle button and a popup with the combined comment text.
    groups.forEach(group => {
      // Combine the text from all spans in the group (each on its own line)
      let groupText = group.map(span => span.textContent.trim()).join("\n");
  
      // Create a toggle button
      let btn = document.createElement("button");
      btn.className = "comment-toggle-btn";
      btn.textContent = "[?]";
  
      // Insert the button before the first span in the group
      group[0].parentNode.insertBefore(btn, group[0]);
  
      // Create a popup to display the combined comment text
      let popup = document.createElement("div");
      popup.className = "comment-popup";
      popup.textContent = groupText;
      // Insert the popup immediately after the button
      btn.parentNode.insertBefore(popup, btn.nextSibling);
  
      // Toggle the popup on button click
      btn.addEventListener("click", function (e) {
        // Prevent click propagation so that a document click doesn't close the popup immediately.
        e.stopPropagation();
        if (popup.style.display === "block") {
          popup.style.display = "none";
        } else {
          // Position the popup just below the button.
          const rect = btn.getBoundingClientRect();
          popup.style.top = (rect.bottom + window.scrollY + 5) + "px"; // 5px gap
          popup.style.left = (rect.left + window.scrollX) + "px";
          popup.style.display = "block";
        }
      });
  
      // Hide the popup when clicking elsewhere on the document.
      document.addEventListener("click", function (event) {
        if (!btn.contains(event.target) && !popup.contains(event.target)) {
          popup.style.display = "none";
        }
      });
    });
  });
  