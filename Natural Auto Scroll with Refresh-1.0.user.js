// ==UserScript==
// @name         Natural Auto Scroll with Refresh
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Human-like auto scrolling with random pauses, upward nudges, and refresh cycles
// @author       You
// @match        https://x.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    function randInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    function randomScrollSession() {
        // Random session length between 25–60 seconds for more natural browsing
        const sessionLength = randInt(25000, 60000);
        const start = Date.now();

        function performBurstScroll() {
            // Simulate rapid skimming with 3-5 small scrolls
            const numSteps = randInt(3, 5);
            const stepDistance = randInt(300, 600);
            for (let i = 0; i < numSteps; i++) {
                setTimeout(() => {
                    window.scrollBy({ top: stepDistance, behavior: "auto" });
                }, i * randInt(100, 200));
            }
        }



        function simulateMouseMovement() {
            // Simulate human-like mouse movement during pauses
            const steps = randInt(5, 15);
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            let currentX = Math.random() * viewportWidth;
            let currentY = Math.random() * viewportHeight;

            for (let i = 0; i < steps; i++) {
                setTimeout(() => {
                    const targetX = Math.random() * viewportWidth;
                    const targetY = Math.random() * viewportHeight;
                    const event = new MouseEvent('mousemove', {
                        clientX: targetX,
                        clientY: targetY,
                        bubbles: true
                    });
                    document.dispatchEvent(event);
                    currentX = targetX;
                    currentY = targetY;
                }, i * randInt(50, 200)); // Variable timing for natural movement
            }
        }

        function step() {
            if (Date.now() - start > sessionLength) {
                // Natural pause before refreshing, varied
                const pauseBeforeRefresh = randInt(5000, 12000);
                setTimeout(() => location.reload(), pauseBeforeRefresh);
                return;
            }

            // Session fatigue: adjust behavior as session progresses
            const progress = (Date.now() - start) / sessionLength;
            const fatigueMultiplier = 1 + (progress * 0.5); // Up to 1.5x slower responses
            const fatigueRange = Math.min(28 + Math.floor(progress * 5), 33); // More choices later = more pauses

            // Expanded choices for more human-like behavior (1-33+)
            const actionChoice = randInt(1, fatigueRange);

            if (actionChoice <= 4) {
                // Reading pause - more common now
                console.log("Pausing to absorb content...");
                // Occasionally simulate mouse movement during thoughtful pauses
                if (Math.random() < 0.6) simulateMouseMovement();
                // No scroll
            } else if (actionChoice <= 6) {
                // Small upward adjustment (re-reading)
                const distance = -randInt(30, 150);
                const behavior = Math.random() < 0.6 ? "smooth" : "auto";
                window.scrollBy({ top: distance, behavior });
            } else if (actionChoice <= 10) {
                // Small downward scroll (careful reading)
                const distance = randInt(100, 300);
                window.scrollBy({ top: distance, behavior: "smooth" });
            } else if (actionChoice <= 16) {
                // Medium scroll (normal progress)
                const distance = randInt(500, 1500);
                const behavior = Math.random() < 0.8 ? "smooth" : "auto";
                window.scrollBy({ top: distance, behavior });
            } else if (actionChoice <= 20) {
                // Large scroll (skimming)
                const distance = randInt(1500, 4000);
                const behavior = Math.random() < 0.5 ? "smooth" : "auto";
                window.scrollBy({ top: distance, behavior });
            } else if (actionChoice <= 25) {
                // Skim burst - rapid movement
                performBurstScroll();
            } else if (actionChoice <= 28) {
                // Full screen scroll simulation (simulating page down with large scroll)
                window.scrollBy({ top: randInt(3000, 5000), behavior: "auto" });
            } else {
                // Intense scrolling burst: 5-10 consecutive full screen scrolls
                console.log("Intense scrolling mode...");
                const numPages = randInt(5, 10);
                for (let i = 0; i < numPages; i++) {
                    setTimeout(() => {
                        window.scrollBy({ top: randInt(3000, 5000), behavior: "auto" });
                    }, i * randInt(80, 150)); // Quick succession with slight variation
                }
            }

            // Random delay before next action - adjusted for more variability
            let delay = randInt(1500, 8000);
            delay *= fatigueMultiplier; // Longer delays as session fatigues

            // Increased chance of longer pauses (thinking or distracted) - more fatigue = more rests
            const restDenominator = Math.max(8, 15 - Math.floor(progress * 7)); // Down to 8 later
            const chanceOfRest = randInt(1, restDenominator);
            if (chanceOfRest <= 2) {
                delay = randInt(10000, 20000); // 10–20s pause
            }

            setTimeout(step, delay);
        }

        step();
    }

    // Run initial session
    randomScrollSession();

    // After each reload, start again with random delay or long human break
    window.addEventListener("load", () => {
        let delay = randInt(2000, 10000);
        // Simulate human breaks (snack, toilet, etc.) - occasionally take 5-15 minute pauses
        if (Math.random() < 0.1) { // 10% chance
            delay = randInt(300000, 900000); // 5-15 minutes
            console.log("Taking a human break (snack, toilet, etc.)...");
        }
        setTimeout(randomScrollSession, delay);
    });
})();
