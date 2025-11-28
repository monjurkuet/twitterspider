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
        // Random session length between 20–50 seconds
        const sessionLength = randInt(20000, 50000);
        const start = Date.now();

        function step() {
            if (Date.now() - start > sessionLength) {
                // Natural pause before refreshing
                const pauseBeforeRefresh = randInt(3000, 8000);
                setTimeout(() => location.reload(), pauseBeforeRefresh);
                return;
            }

            // Decide scroll behavior
            const actionChoice = randInt(1, 18);

            if (actionChoice === 1) {
                // Occasional "no scroll" pause
                console.log("Pausing to read...");
            } else if (actionChoice === 2) {
                // Occasional small upward scroll
                const distance = -randInt(50, 200);
                const behavior = Math.random() < 0.5 ? "smooth" : "auto";
                window.scrollBy({ top: distance, behavior });
            } else {
                // Downward scroll (dominant behavior)
                const distance = randInt(1000, 10000);
                const behavior = Math.random() < 0.7 ? "smooth" : "auto"; // vary speed
                window.scrollBy({ top: distance, behavior });
            }

            // Random delay before next action
            let delay = randInt(2000, 10000);

            // Occasionally insert a longer "rest" pause
            const chanceOfRest = randInt(1, 12);
            if (chanceOfRest === 1) {
                delay = randInt(8000, 15000); // 8–15s pause
            }

            setTimeout(step, delay);
        }

        step();
    }

    // Run initial session
    randomScrollSession();

    // After each reload, start again with random delay
    window.addEventListener("load", () => {
        const delay = randInt(2000, 10000);
        setTimeout(randomScrollSession, delay);
    });
})();
