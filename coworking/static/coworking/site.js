document.addEventListener("DOMContentLoaded", () => {
  const countdown = document.querySelector("#hold-countdown");
  if (!countdown) return;

  let seconds = Number(countdown.dataset.seconds || 0);
  const render = () => {
    if (seconds <= 0) {
      countdown.textContent = "The hold has expired. Staff may still approve if the space remains available.";
      return false;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    countdown.textContent = `Time remaining: ${minutes}:${String(remainingSeconds).padStart(2, "0")}.`;
    seconds -= 1;
    return true;
  };
  if (render()) window.setInterval(render, 1000);
});
