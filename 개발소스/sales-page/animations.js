(() => {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function revealGroup(gsap, selector, trigger, options = {}) {
    const targets = gsap.utils.toArray(selector);
    if (!targets.length) {
      return;
    }

    const compact = window.matchMedia("(max-width: 760px)").matches;
    gsap.from(targets, {
      autoAlpha: 0,
      y: options.y ?? (compact ? 18 : 26),
      duration: options.duration ?? 0.68,
      ease: "power2.out",
      stagger: compact ? Math.min(options.stagger ?? 0.08, 0.08) : options.stagger ?? 0.1,
      scrollTrigger: {
        trigger,
        start: options.start ?? "top 84%",
        once: true,
        invalidateOnRefresh: true,
      },
    });
  }

  function initialiseMotion() {
    if (reducedMotion.matches || !window.gsap || !window.ScrollTrigger) {
      return;
    }

    const { gsap, ScrollTrigger } = window;
    gsap.registerPlugin(ScrollTrigger);

    const intro = gsap.timeline({
      defaults: { ease: "power2.out" },
    });

    intro
      .from(".site-header", { autoAlpha: 0, y: -14, duration: 0.52 })
      .from(".hero-copy h1 span", { autoAlpha: 0, y: 28, duration: 0.64, stagger: 0.09 }, "-=0.2")
      .from(".hero-copy p", { autoAlpha: 0, y: 18, duration: 0.52 }, "-=0.34")
      .from(".hero-actions .btn", { autoAlpha: 0, y: 14, duration: 0.44, stagger: 0.08 }, "-=0.26")
      .from(".hero-proof > div", { autoAlpha: 0, y: 16, duration: 0.46, stagger: 0.07 }, "-=0.18")
      .from(".hero-media", { autoAlpha: 0, y: 22, duration: 0.7 }, "-=0.7")
      .from(".hero-card", { autoAlpha: 0, y: 12, duration: 0.42, stagger: 0.1 }, "-=0.34");

    revealGroup(gsap, ".quick-categories a", ".quick-categories", { y: 20, stagger: 0.07 });
    revealGroup(gsap, ".package-section .section-heading", ".package-section", { y: 22 });
    revealGroup(gsap, ".package-card", ".package-grid", { y: 26, stagger: 0.1 });
    revealGroup(gsap, ".catalog-section .section-heading", ".catalog-section", { y: 22 });
    revealGroup(gsap, ".brand-group", ".brand-board", { y: 24, stagger: 0.1 });
    revealGroup(gsap, ".scanner-section .section-heading", ".scanner-section", { y: 22 });
    revealGroup(gsap, ".scanner-card", ".scanner-grid", { y: 24, stagger: 0.1 });
    revealGroup(gsap, ".supplies-section .section-heading", ".supplies-section", { y: 22 });
    revealGroup(gsap, ".supply-card", ".supplies-grid", { y: 24, stagger: 0.12 });
    revealGroup(gsap, ".software-copy", ".software-section", { y: 22 });
    revealGroup(gsap, ".software-panel", ".software-section", { y: 24, start: "top 78%" });
    revealGroup(gsap, ".trust-strip > div", ".trust-strip", { y: 18, stagger: 0.08 });
    revealGroup(gsap, ".contact-section > div, .contact-form", ".contact-section", { y: 24, stagger: 0.12 });

    ScrollTrigger.refresh();
  }

  if (document.readyState === "complete") {
    initialiseMotion();
  } else {
    window.addEventListener("load", initialiseMotion, { once: true });
  }
})();
