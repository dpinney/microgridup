"use strict";

main();

function setupSideNav() {
    // - Set up the side nav
    // - Add side nav expansion 
    for (let div of document.getElementsByClassName('js-div--buttonContainer')) {
        const button = div.previousElementSibling
        const svg = button.getElementsByTagName('svg')[0];
        button.addEventListener('click', function() {
            div.classList.toggle('expanded');
            svg.classList.toggle('rotated');
            if (!div.classList.contains('expanded')) {
                for (let innerDiv of div.getElementsByClassName('js-div--buttonContainer')) {
                    innerDiv.classList.remove('expanded');
                }
                for (let innerSvg of div.getElementsByTagName('svg')) {
                    innerSvg.classList.remove('rotated');
                }
            }
        });
    }
    // - Connect side nav buttons to sections
    const sections = document.getElementsByTagName('section');
    for (let btn of document.getElementsByClassName('js-nav--sideNav')[0].getElementsByTagName('button')) {
        const section = document.querySelector(`section[data-content='${btn.dataset.content}']`)
        if (section !== null) {
            btn.addEventListener('click', function() {
                for (let sec of sections) {
                    if (sec !== section && !sec.classList.contains('hidden')) {
                        sec.classList.add('hidden');
                    }
                    section.classList.remove('hidden');
                }
            });
        }
    }
}

function setupTopNav() {
    // - Set up the top nav
    const hamburger = document.getElementsByClassName('js-nav--topNav')[0].getElementsByTagName('button')[0];
    const sideNav = document.getElementsByClassName('js-nav--sideNav')[0];
    const sideNavCover = document.getElementsByClassName('js-div--sideNavCover')[0];
    const article = document.getElementsByTagName('article')[0];
    hamburger.addEventListener('click', function () {
        sideNav.classList.toggle('open');
        sideNavCover.classList.toggle('open');
        if (sideNav.classList.contains('open') && !article.classList.contains('compressed')) {
            article.classList.add('compressed');
        } else {
            article.classList.remove('compressed');
        }
    });
    sideNavCover.addEventListener('click', function() {
        sideNav.classList.remove('open');
        sideNavCover.classList.remove('open');
    });
}

function loadPage() {
    // - Load the page
    window.onload = function() {
        const sideNavCover = document.getElementsByClassName('js-div--sideNavCover')[0];
        sideNavCover.getElementsByTagName('span')[0].remove();
        sideNavCover.classList.remove('loading');
        document.getElementsByTagName('body')[0].classList.remove('loading');
        document.getElementsByTagName('main')[0].classList.remove('loading');
        // - Section start with visibility: hidden; to load, then switch to display: none; to only show one section at a time
        const overviewSection = document.querySelector('section[data-content=overview]');
        for (let sec of document.getElementsByTagName('section')) {
            if (sec !== overviewSection) {
                sec.classList.add('hidden');
                sec.classList.remove('loading');
            }
        }
    }
}

function main() {
    setupSideNav();
    setupTopNav();
    loadPage();
}