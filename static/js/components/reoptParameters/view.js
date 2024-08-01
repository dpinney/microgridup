export { REoptParametersView };
import { REoptIntParameter, REoptFloatParameter, REoptBooleanParameter } from './model.js';
import { REoptParametersController } from './controller.js';
import { Modal, getTrashCanSvg, getCirclePlusSvg } from '../modal.js';

class REoptParametersView {

    modal;
    #controller;

    constructor(controller) {
        if (!(controller instanceof REoptParametersController)) {
            throw TypeError('The "controller" argument must be instanceof REoptParametersController.');
        }
        this.modal = null;
        this.#controller = controller;
        this.renderContent();
    }

    /**
     * - Render the modal for the first time
     * @returns {undefined}
     */
    renderContent() {
        const modal = new Modal();
        modal.divElement.id = 'reoptParametersModal';
        const microgridDropdownInstructions = document.createElement('p');
        microgridDropdownInstructions.style.fontWeight = 'bold';
        microgridDropdownInstructions.textContent = 'Select microgrid to override parameters for';
        modal.divElement.append(microgridDropdownInstructions);
        const microgridSelect = document.createElement('select');
        const option = document.createElement('option');
        option.label = '<Select Microgrid>';
        option.value = '<Select Microgrid>';
        microgridSelect.add(option);
        for (const name of Object.keys(this.#controller.model.reoptParametersInstances)) {
            const option = document.createElement('option');
            option.label = name;
            option.value = name;
            microgridSelect.add(option); 
        }
        modal.divElement.append(microgridSelect);
        const tableDiv = document.createElement('div');
        modal.divElement.append(tableDiv);
        const that = this;
        microgridSelect.addEventListener('change', function() {
            const microgridName = this[this.selectedIndex].value;
            if (microgridName !== '<Select Microgrid>') {
                const tableInstructions = document.createElement('p');
                tableInstructions.style.fontWeight = 'bold';
                tableInstructions.textContent = `Set parameters for microgrid "${microgridName}":`;
                const table = new REoptParametersTable(microgridName, that.#controller);
                tableDiv.replaceChildren(tableInstructions, table.modal.divElement);
            } else {
                tableDiv.replaceChildren();
            }
        });
        if (this.modal === null) {
            this.modal = modal;
        } 
        if (document.body.contains(this.modal.divElement)) {
            this.modal.divElement.replaceWith(modal.divElement);
            this.modal = modal;
        }
    }
}

/**
 * - This is a (private) helper class for the REoptParametersView class
 */
class REoptParametersTable {
       
    modal;          // - A Modal instance
    #controller;    // - A REoptParametersController instance
    #observableId;  // - The name of a microgrid
    #parameterSelect;

    constructor(observableId, controller) {
        if (typeof observableId !== 'string') {
            throw TypeError('The "observableId" argument must be typeof "string".');
        }
        if (!(controller instanceof REoptParametersController)) {
            throw TypeError('The "controller" argument must be instanceof REoptParametersController.');
        }
        this.modal = null;
        this.#observableId = observableId;
        this.#controller = controller;
        this.#controller.model.getReoptParametersInstance(this.#observableId).registerObserver(this);
        this.#parameterSelect = null;
        this.renderContent();
    }

    /**
     * @param {REoptParameters} reoptParameters - a REoptParameters instance.
     * @param {string} id - a string of the form "<microgrid name>:<REoptParameter namespace>:<REoptParameter name>"
     * @param {object} oldValue
     * @returns {undefined}
     */
    handleChangedProperty(reoptParameters, id, oldValue) {
        this.refreshContent();
    }

    /**
     * @returns {undefined}
     */
    renderContent() {
        const modal = new Modal();
        modal.divElement.id = 'parameterTableModal'
        modal.insertTBodyRow([this.#getPlusButton(), 'Parameter', 'Value'], 'append');
        for (const parameter of this.#controller.model.getReoptParametersInstance(this.#observableId).reoptParameters) {
            if (parameter.isSet()) {
                this.#insertParameterRow(modal, `${this.#observableId}:${parameter.parameterName}`);
            }
        }
        if (this.modal === null) {
            this.modal = modal;
        } 
        if (document.body.contains(this.modal.divElement)) {
            this.modal.divElement.replaceWith(modal.divElement);
            this.modal = modal;
        }
    }

    /**
     * - Only handles property deletions currently
     * @returns {undefined}
     */
    refreshContent() {
        for (const span of [...this.modal.divElement.querySelectorAll('span[data-reopt-parameter-parameter-name]')]) {
            const parameterName = span.dataset.reoptParameterParameterName;
            const reoptParameter = this.#controller.model.getReoptParametersInstance(this.#observableId).getReoptParameter(parameterName);
            if(!reoptParameter.isSet()) {
                let parentElement = span.parentElement;
                while (!(parentElement instanceof HTMLTableRowElement)) {
                    parentElement = parentElement.parentElement;
                }
                parentElement.remove();
            }
        }
        if (document.body.contains(this.#parameterSelect)) {
            const newParameterSelect = this.#getParameterSelect();
            this.#parameterSelect.replaceWith(newParameterSelect);
            this.#parameterSelect = newParameterSelect;
        }
    }
    
    /**
     * @returns {HTMLButtonElement}
     */
    #getPlusButton() {
        const button = document.createElement('button');
        button.append(getCirclePlusSvg());
        button.addEventListener('click', (e) => {
            if (!document.body.contains(this.#parameterSelect)) {
                const newParameterSelect = this.#getParameterSelect();
                this.modal.insertTBodyRow([this.#getUnsetParameterButton(''), newParameterSelect], 'append');
                this.#parameterSelect = newParameterSelect;
            }
            e.preventDefault();
        });
        return button;
    }

    /**
     * @returns {HTMLSelectElement}
     */
    #getParameterSelect() {
        const select = document.createElement('select');
        const option = document.createElement('option');
        option.label = '<Select Parameter>';
        option.value = '<Select Parameter>';
        select.add(option);
        for (const parameter of this.#controller.model.getReoptParametersInstance(this.#observableId).reoptParameters) {
            const existingRows = [...this.modal.divElement.querySelectorAll('span[data-reopt-parameter-parameter-name]')].map(span => span.dataset.reoptParameterParameterName);
            if (!existingRows.includes(parameter.parameterName)) {
                const option = document.createElement('option');
                option.label = parameter.displayName;
                option.value = parameter.parameterName;
                select.add(option); 
            }
        }
        const that = this;
        select.addEventListener('change', function() {
            const parameterName = this[this.selectedIndex].value;
            that.#insertParameterRow(that.modal, `${that.#observableId}:${parameterName}`);
            let parentElement = this.parentElement;
            while (!(parentElement instanceof HTMLTableRowElement)) {
                parentElement = parentElement.parentElement;
            }
            parentElement.remove();
        });
        return select;
    }

    /**
     * @param {string} id - a string of the form "<microgrid name>:<REopt parameter namespace>:<REopt parameter name>"
     * @returns {HTMLButtonElement} a button that can be clicked on to remove a property from a microgrid
     */
    #getUnsetParameterButton(id) {
        if (typeof id !== 'string') {
            throw TypeError('The "id" argument must be typeof "string".');
        }
        const button = document.createElement('button');
        button.classList.add('delete');
        button.appendChild(getTrashCanSvg());
        const that = this;
        button.addEventListener('click', function(e) {
            if (id !== '') {
                that.#controller.unsetParameter(id);
            }
            let parentElement = this.parentElement;
            while (!(parentElement instanceof HTMLTableRowElement)) {
                parentElement = parentElement.parentElement;
            }
            parentElement.remove();
            e.preventDefault();
        });
        return button;
    }

    /**
     * @param {Modal} modal - the modal that I'm setting up. It's not the same as this.#modal
     * @param {string} id - a string of the form "<microgrid name>:<REopt parameter namespace>:<REopt parameter name>"
     * @returns {undefined}
     */
    #insertParameterRow(modal, id) {
        if (typeof id !== 'string') {
            throw TypeError('The "id" argument must be typeof "string".');
        }
        const [microgridName, parameterNamespace, name] = id.split(':');
        const reoptParameter = this.#controller.model.getReoptParametersInstance(microgridName).getReoptParameter(`${parameterNamespace}:${name}`);
        const input = document.createElement('input');
        let oldValue = reoptParameter.value;
        if (reoptParameter instanceof REoptBooleanParameter) {
            input.type = 'checkbox';
            input.checked = oldValue;
        } else {
            input.value = oldValue;
        }
        const that = this;
        input.addEventListener('change', function() {
            try {
                let value;
                if (reoptParameter instanceof REoptBooleanParameter) {
                    value = this.checked;
                } else {
                    value = this.value.trim();
                    if (reoptParameter instanceof REoptIntParameter || reoptParameter instanceof REoptFloatParameter) {
                        value = this.value.trim();
                        if (isNaN(parseFloat(value)) || isNaN(Number(value))) {
                            throw Error(`The value given for "${reoptParameter.displayName}" must be a number.`);
                        } else {
                            value = +value;
                        }
                    }
                }
                that.#controller.setParameterValue(id, value);
                oldValue = reoptParameter.value;
                that.modal.setBanner('', ['hidden']);
            } catch (e) {
                if (reoptParameter instanceof REoptBooleanParameter) {
                    this.checked = oldValue;
                } else {
                    this.value = oldValue;
                }
                that.modal.setBanner(e.message, ['caution']);
            }
        });
        const span = document.createElement('span');
        span.textContent = reoptParameter.displayName;
        span.dataset.reoptParameterParameterName = reoptParameter.parameterName;
        modal.insertTBodyRow([this.#getUnsetParameterButton(id), span, input], 'append');
    }
}

