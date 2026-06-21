/* BhuKhadan Website – frontend interactions v4 */
document.addEventListener('DOMContentLoaded', function () {

    /* ── Smooth scroll for anchor links ── */
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            var target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    /* ── Stat counter animation (triggered by IntersectionObserver) ── */
    function animateCounter(el) {
        var target = parseInt(el.getAttribute('data-count'), 10);
        var duration = 1600;
        var step = target / (duration / 16);
        var current = 0;
        var timer = setInterval(function () {
            current += step;
            if (current >= target) { current = target; clearInterval(timer); }
            el.textContent = Math.floor(current).toLocaleString('en-IN') + (el.getAttribute('data-suffix') || '');
        }, 16);
    }
    var counters = document.querySelectorAll('[data-count]');
    if (counters.length) {
        var cntObs = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) { animateCounter(entry.target); cntObs.unobserve(entry.target); }
            });
        }, { threshold: 0.5 });
        counters.forEach(function (c) { cntObs.observe(c); });
    }

    /* ── Navbar scroll state + mobile drawer ── */
    var navbar = document.querySelector('.bhu-navbar');
    var navToggle = document.querySelector('.bhu-nav-toggle');
    var navBackdrop = document.querySelector('.bhu-nav-mobile-backdrop');
    var navClose = document.querySelector('.bhu-nav-mobile-close');
    var mobileMq = window.matchMedia('(max-width: 640px)');

    function isMobileNav() {
        return mobileMq.matches;
    }

    function setMobileMenuOpen(open) {
        if (!navbar) return;
        navbar.classList.toggle('is-open', open);
        if (navToggle) {
            navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            navToggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
        }
        document.body.classList.toggle('bhu-nav-open', open);
    }

    function closeMobileMenu() {
        setMobileMenuOpen(false);
        var dd = document.querySelector('.bhu-nav-dropdown');
        if (dd) {
            dd.classList.remove('open');
            var ddBtn = dd.querySelector('.bhu-nav-drop-toggle');
            if (ddBtn) ddBtn.setAttribute('aria-expanded', 'false');
        }
    }

    if (navbar) {
        var setScrolled = function () {
            navbar.classList.toggle('scrolled', window.scrollY > 8);
        };
        setScrolled();
        window.addEventListener('scroll', setScrolled, { passive: true });
    }

    if (navToggle) {
        navToggle.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            setMobileMenuOpen(!navbar.classList.contains('is-open'));
        });
    }
    if (navBackdrop) {
        navBackdrop.addEventListener('click', closeMobileMenu);
    }
    if (navClose) {
        navClose.addEventListener('click', function (e) {
            e.preventDefault();
            closeMobileMenu();
        });
    }

    mobileMq.addEventListener('change', function () {
        closeMobileMenu();
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && navbar && navbar.classList.contains('is-open')) {
            closeMobileMenu();
        }
    });

    if (navbar) {
        navbar.querySelectorAll('.bhu-nav-links a').forEach(function (link) {
            link.addEventListener('click', function () {
                if (isMobileNav()) {
                    closeMobileMenu();
                }
            });
        });
    }

    /* ════════════════════════════════════════════════════════
       NAVBAR — Features dropdown (CBA guide)
       ════════════════════════════════════════════════════════ */
    var dropParent = document.querySelector('.bhu-nav-dropdown');
    if (dropParent) {
        /* Never leave dropdown open on load (legacy templates used server-side .open) */
        dropParent.classList.remove('open');
        var dropBtn = dropParent.querySelector('.bhu-nav-drop-toggle');
        dropBtn.setAttribute('aria-expanded', 'false');
        dropBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            var open = dropParent.classList.toggle('open');
            dropBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        document.addEventListener('click', function (e) {
            if (isMobileNav()) {
                return;
            }
            if (!dropParent.contains(e.target)) {
                dropParent.classList.remove('open');
                dropBtn.setAttribute('aria-expanded', 'false');
            }
        });
        dropParent.querySelector('.bhu-nav-dropdown-panel').addEventListener('click', function (e) {
            e.stopPropagation();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !isMobileNav()) {
                dropParent.classList.remove('open');
                dropBtn.setAttribute('aria-expanded', 'false');
            }
        });
    }

    /* ── Remove Odoo "Skip to Content" ── */
    var skip = document.querySelector('.o_skip_to_content, a[href="#wrap"]');
    if (skip && skip.parentNode) skip.parentNode.removeChild(skip);

    /* ════════════════════════════════════════════════════════
       SCROLL-REVEAL SYSTEM
       Automatically attach .bhu-reveal / .bhu-reveal-left /
       .bhu-reveal-right to elements that should animate in,
       then observe them and add .bhu-visible when in-view.
       ════════════════════════════════════════════════════════ */

    var revealMap = [
        /* Whole-section headings */
        { sel: '.bhu-sec-head',              cls: 'bhu-reveal' },
        /* Hero sides */
        { sel: '.bhu-hero-left',             cls: 'bhu-reveal-left' },
        { sel: '.bhu-hero-visual',           cls: 'bhu-reveal-right' },
        { sel: '.bhu-hero-trust',            cls: 'bhu-reveal' },
        /* Trusted bar */
        { sel: '.bhu-trusted-inner',         cls: 'bhu-reveal' },
        /* Value props */
        { sel: '.bhu-values-img-wrap',       cls: 'bhu-reveal-left' },
        { sel: '.bhu-values-content',        cls: 'bhu-reveal-right' },
        /* Features cards */
        { sel: '.bhu-feature',               cls: 'bhu-reveal' },
        /* Why cards */
        { sel: '.bhu-why-card',              cls: 'bhu-reveal' },
        /* Insights */
        { sel: '.bhu-insights-content',      cls: 'bhu-reveal-left' },
        { sel: '.bhu-insights-visual',       cls: 'bhu-reveal-right' },
        /* Roadmap steps */
        { sel: '.bhu-roadmap-step',          cls: 'bhu-reveal' },
        /* VP items */
        { sel: '.bhu-vp-item',               cls: 'bhu-reveal' },
        /* Contact sections */
        { sel: '.bhu-contact-info',          cls: 'bhu-reveal-left' },
        { sel: '.bhu-contact-form',          cls: 'bhu-reveal-right' },
        /* Acts / PDF cards */
        { sel: '.bhu-act-card',              cls: 'bhu-reveal' },
        { sel: '.bhu-pdf-card',              cls: 'bhu-reveal' },
        { sel: '.bhu-act-stage',             cls: 'bhu-reveal' },
    ];

    revealMap.forEach(function (entry) {
        document.querySelectorAll(entry.sel).forEach(function (el) {
            /* Don't double-tag */
            if (!el.classList.contains('bhu-reveal') &&
                !el.classList.contains('bhu-reveal-left') &&
                !el.classList.contains('bhu-reveal-right')) {
                el.classList.add(entry.cls);
            }
        });
    });

    /* Add staggered transition-delay to children inside grid containers */
    var staggerGrids = [
        '.bhu-features-grid',
        '.bhu-why-grid',
        '.bhu-vp-grid',
        '.bhu-roadmap-track',
        '.bhu-act-stage-line',
        '.bhu-pdf-grid',
    ];
    staggerGrids.forEach(function (gridSel) {
        document.querySelectorAll(gridSel).forEach(function (grid) {
            Array.from(grid.children).forEach(function (child, i) {
                /* Only add delay if not already set */
                if (!child.style.transitionDelay) {
                    child.style.transitionDelay = (i * 0.08) + 's';
                }
            });
        });
    });

    /* Single observer for all reveal elements */
    var revealObs = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('bhu-visible');
                revealObs.unobserve(entry.target);
            }
        });
    }, { threshold: 0.08, rootMargin: '0px 0px -48px 0px' });

    document.querySelectorAll('.bhu-reveal, .bhu-reveal-left, .bhu-reveal-right')
        .forEach(function (el) { revealObs.observe(el); });

    /* ════════════════════════════════════════════════════════
       NAVBAR MOBILE MENU (hamburger toggle)
       ════════════════════════════════════════════════════════ */
    var hamburger = document.querySelector('.bhu-hamburger');
    var mobileMenu = document.querySelector('.bhu-nav-links');
    if (hamburger && mobileMenu) {
        hamburger.addEventListener('click', function () {
            var open = mobileMenu.classList.toggle('bhu-nav-open');
            hamburger.setAttribute('aria-expanded', open);
        });
    }

    /* ════════════════════════════════════════════════════════
       BUTTON RIPPLE on click
       ════════════════════════════════════════════════════════ */
    document.querySelectorAll('.bhu-btn, .bhu-btn-nav').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            var rect = btn.getBoundingClientRect();
            var ripple = document.createElement('span');
            ripple.className = 'bhu-ripple';
            var size = Math.max(rect.width, rect.height);
            ripple.style.cssText =
                'position:absolute;border-radius:50%;pointer-events:none;' +
                'transform:scale(0);animation:rippleOut 0.55s ease-out forwards;' +
                'background:rgba(255,255,255,0.28);' +
                'width:' + size + 'px;height:' + size + 'px;' +
                'left:' + (e.clientX - rect.left - size/2) + 'px;' +
                'top:'  + (e.clientY - rect.top  - size/2) + 'px;';
            btn.style.position = 'relative';
            btn.style.overflow = 'hidden';
            btn.appendChild(ripple);
            setTimeout(function () { if (ripple.parentNode) ripple.parentNode.removeChild(ripple); }, 600);
        });
    });

});

/* Ripple keyframe injected once */
(function () {
    if (document.getElementById('bhu-ripple-style')) return;
    var s = document.createElement('style');
    s.id = 'bhu-ripple-style';
    s.textContent = '@keyframes rippleOut{to{transform:scale(2.5);opacity:0}}';
    document.head.appendChild(s);
})();
