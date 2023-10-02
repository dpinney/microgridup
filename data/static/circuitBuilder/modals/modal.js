export { Modal, getTrashCanSvg };

class Modal {
    
    divElement;             // - The divElement is the outermost div that contains the modal's content
    #bannerElement;         // - The bannerElement contains the banner text. It's usually empty unless the user needs to be notified of something
    #initialTablePosition;  // - Where the table element should be positioned relative to other elements when it is created for the first time. Can be "prepend" or "append"
    #tableElement;          // - The table element is an actual table
    #titleElement;          // - The title element contains the optional title text

    /**
     * @returns {undefined}
     * @param {string} [initialTablePosition='prepend']
     */
    constructor(initialTablePosition='prepend') {
        if (!['prepend', 'append'].includes(initialTablePosition)) {
            throw TypeError('"initialTablePosition" argument must be "prepend" or "append".');
        }
        this.divElement = document.createElement('div');
        this.divElement.classList.add('div--modal');
        this.#bannerElement = null;
        this.#initialTablePosition = initialTablePosition;
        this.#tableElement = null;
        this.#titleElement = null;
    }

    /******************/
    /* Public methods */
    /******************/

    /**
     * @param {(Node|string)} banner - the banner to display
     * @param {(Array|null)} [styles=null] - any styles that should be applied to the banner
     * @returns {undefined}
     */
    setBanner(banner, styles=null) {
        if (this.#bannerElement === null) {
            this.#bannerElement = document.createElement('div');
            this.#bannerElement.classList.add('div--modalBanner');
        }
        if (this.#titleElement === null) {
            this.divElement.prepend(this.#bannerElement);
        } else {
            this.#titleElement.after(this.#bannerElement);
        }
        if (typeof banner === 'string') {
            const span = document.createElement('span');
            span.textContent = banner;
            this.#bannerElement.replaceChildren(span);
        } else if (banner instanceof Node) {
            this.#bannerElement.replaceChildren(banner);
        } else {
            throw TypeError('The "banner" argument must be instanceof Node or typeof "string".');
        }
        if (!(styles instanceof Array) && styles !== null) {
            throw TypeError('The "styles" argument must be instanceof Array or null.');
        }
        if (styles !== null) {
            this.#bannerElement.classList.value = `div--modalBanner ${styles.join(' ')}`;
        } else {
            this.#bannerElement.classList.value = 'div--modalBanner';
        }
    }

    /**
     * @param {(string|Node)} title - the title to display
     * @param {Array} [styles=null] - any styles that should be applied to the title
     * @returns {undefined}
     */
    setTitle(title, styles=null) {
        if (this.#titleElement === null) {
            this.#titleElement = document.createElement('div');
            this.#titleElement.classList.add('div--modalTitle');
        }
        this.divElement.prepend(this.#titleElement);
        if (typeof title === 'string') {
            const span = document.createElement('span');
            span.textContent = title;
            this.#titleElement.replaceChildren(span);
        } else if (title instanceof Node) {
            this.#titleElement.replaceChildren(title);
        } else {
            throw TypeError('The "title" argument must be instanceof Node or typeof "string".');
        }
        if (!(styles instanceof Array) && styles !== null) {
            throw TypeError('The "styles" argument must be instanceof Array or null.');
        }
        if (styles !== null) {
            this.#titleElement.classList.value = `div--modalTitle ${styles.join(' ')}`;
        } else {
            this.#titleElement.classList.value = 'div--modalTitle';
        }
    }

    /**
     * @param {Array} elements - an array of elements that should occupy a table body row. null elements just append empty <td>/<td> elements
     * @param {string} [position='append'] - the location to insert the tBody row. Can be "prepend", "beforeEnd", or "append"
     * @param {(Array|null)} [styles=null] - any styles that should be applied to the row
     * @returns {undefined}
     */
    insertTBodyRow(elements, position='append', styles=null) {
        if (!(styles instanceof Array) && styles !== null) {
            throw TypeError('The "styles" argument must be instanceof Array or null.');
        }
        if (this.#tableElement === null) {
            this.#createTableElement();    
        }
        const tr = document.createElement('tr');
        if (styles !== null) {
            tr.classList.add(...styles);
        }
        elements.forEach(e => {
            const td = document.createElement('td');
            const div = document.createElement('div');
            if (typeof e === 'string') {
                const span = document.createElement('span');
                span.textContent = e;
                div.appendChild(span);
                td.appendChild(div)
            } else if (e instanceof Node) {
                div.appendChild(e);
                td.appendChild(div);
            } else if (e !== null) {
                throw TypeError(`Every element in the "elements" argument array must be null, instanceof Node, or typeof "string".`);
            }
            tr.appendChild(td);
        });
        if (position === 'prepend') {
            this.#tableElement.tBodies[0].prepend(tr);
        } else if (position === 'beforeEnd') {
            const lastNodeIndex = this.#tableElement.tBodies[0].children.length - 1;
            const lastNode = this.#tableElement.tBodies[0].children.item(lastNodeIndex);
            lastNode.before(tr);
        } else if (position === 'append') {
            this.#tableElement.tBodies[0].append(tr);
        } else {
            throw Error('The "position" argument must be "prepend", "beforeEnd", or "append".');
        }
    }

    /**
     * @param {Array} elements - an array of elements that should occupy a table header row. null elements just append empty <td>/<td> elements
     * @param {string} [position='append'] - the location to insert the tHead row. Can be "prepend", "beforeEnd", or "append"
     * @param {Array} [styles=null] - any styles that should be applied to the row
     * @returns {undefined}
     */
    insertTHeadRow(elements, position='append', styles=null) {
        if (!(styles instanceof Array) && styles !== null) {
            throw TypeError('The "styles" argument must be instanceof Array or null.');
        }
        if (this.#tableElement === null) {
            this.#createTableElement();
        }
        const tr = document.createElement('tr');
        if (styles !== null) {
            tr.classList.add(...styles);
        }
        elements.forEach(e => { 
            const th = document.createElement('th');
            const div = document.createElement('div');
            if (typeof e === 'string') {
                const span = document.createElement('span');
                span.textContent = e;
                div.appendChild(span);
                th.appendChild(div);
            } else if (e instanceof Node) {
                div.appendChild(e);
                th.appendChild(div);
            } else if (e !== null) {
                throw TypeError(`Every element in the "elements" argument array must be null, instanceof Node, or typeof "string".`);
            }
            tr.appendChild(th);
        });
        if (position === 'prepend') {
            this.#tableElement.tHead.prepend(tr);
        } else if (position === 'beforeEnd') {
            const lastNodeIndex = this.#tableElement.tHead.children.length - 1;
            const lastNode = this.#tableElement.tHead.children.item(lastNodeIndex);
            lastNode.before(tr);
        } else if (position === 'append') {
            this.#tableElement.tHead.append(tr);
        } else {
            throw Error('The "position" argument must be "prepend", "beforeEnd", or "append".');
        }
    }

    // - I got rid of the insertElement() method because it's way easier and more intutive to use the browser's built-in DOM manipulation methods for
    //   elements. Table rows are still a special case because they're annoying

    // - I got rid of the insertButtion() method because usually I want to wrap a button in a div so it's on its own line, but sometimes I don't. It's
    //   too complicated to specify whether to wrap the button in a div in this method

    // *********************
    // ** Private methods ** 
    // *********************

    #createTableElement() {
        this.#tableElement = document.createElement('table');
        this.#tableElement.appendChild(document.createElement('thead'));
        this.#tableElement.appendChild(document.createElement('tbody'));
        if (this.#initialTablePosition === 'prepend') {
            this.divElement.prepend(this.#tableElement);
        } else if (this.#initialTablePosition === 'append') {
            this.divElement.appendChild(this.#tableElement);
        }
    }
}

function getTrashCanSvg() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('width', '20px');
    svg.setAttribute('height', '20px');
    svg.setAttribute('viewBox', '2 0 20 20'); 
    svg.setAttribute('fill', 'none'); 
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M10 10V16M14 10V16M4 6H20M15 6V5C15 3.89543 14.1046 3 13 3H11C9.89543 3 9 3.89543 9 5V6M18 6V14M18 18C18 19.1046 17.1046 20 16 20H8C6.89543 20 6 19.1046 6 18V13M6 9V6');
    path.setAttribute('stroke', '#FFFFFF');
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(path);
    return svg;
}