const header = document.querySelector(".site-header");

function updateHeader() {
  if (!header) {
    return;
  }

  header.classList.toggle("scrolled", window.scrollY > 24);
}

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (!target) {
      return;
    }

    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

window.addEventListener("scroll", updateHeader, { passive: true });
updateHeader();

// Stagger the signal-chain card reveal animation.
document.querySelectorAll(".chain-card").forEach((card, index) => {
  card.style.setProperty("--i", index);
});

// Reveal sections as they scroll into view.
const revealTargets = document.querySelectorAll("[data-reveal]");
if ("IntersectionObserver" in window && revealTargets.length) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -8% 0px" }
  );

  revealTargets.forEach((target) => observer.observe(target));
} else {
  revealTargets.forEach((target) => target.classList.add("in-view"));
}

// Let visitors turn on the demo reel's commentary audio.
const videoFrame = document.getElementById("hero-video");
const audioToggle = document.getElementById("audio-toggle");

if (videoFrame && audioToggle && window.Vimeo) {
  const player = new window.Vimeo.Player(videoFrame);
  let unmuted = false;

  const setLabel = () => {
    audioToggle.querySelector(".audio-toggle__label").textContent = unmuted
      ? "Commentary audio on"
      : "Turn on commentary audio";
    audioToggle.setAttribute("aria-pressed", String(unmuted));
  };

  audioToggle.addEventListener("click", async () => {
    unmuted = !unmuted;
    try {
      await player.setMuted(!unmuted);
      if (unmuted) {
        await player.setVolume(1);
      }
    } catch (error) {
      unmuted = false;
    }
    setLabel();
  });

  setLabel();
} else if (audioToggle) {
  audioToggle.hidden = true;
}
