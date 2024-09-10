export { REoptParametersView, REoptInputView };
import { REoptIntParameter, REoptFloatParameter, REoptBooleanParameter } from './model.js';
import { REoptParametersController } from './controller.js';
import { Modal, getTrashCanSvg, getCirclePlusSvg } from '../modal.js';

class REoptInputView {

    modal;
    controller;
    #id;
    #input;

    /**
     * @param {string} id - An id of the form "<microgrid name>:<REopt parameter namespace>:<REopt parameter name>"
     */
    constructor(reoptParametersController, id) {
        if (!(reoptParametersController instanceof REoptParametersController)) {
            throw TypeError('The "reoptParametersController" argument must be instanceof REoptParametersController.');
        }
        if (typeof id !== 'string') {
            throw TypeError('The "reoptParametersController" argument must be typeof "string".');
        }
        if (id.split(':').length !== 3) {
            throw Error(`The "id" argument "${id}" must contain exactly two ":" characters.`);
        }
        this.modal = null;
        this.#id = id;
        this.controller = reoptParametersController;
        this.renderContent();
    }

    renderContent() {
        const modal = new Modal();
        modal.divElement.classList.add('chunk');
        const label = document.createElement('label');
        label.classList.add('tooltip');
        const [microgridName, parameterNamespace, name] = this.#id.split(':');
        const reoptParameter = this.controller.model.getReoptParametersInstance('validationMg').getReoptParameter(`${parameterNamespace}:${name}`);
        label.htmlFor = reoptParameter.alias;
        label.textContent = reoptParameter.displayName;
        const span = document.createElement('span');
        span.classList.add('classic');
        //span.textContent = reoptParameter.tooltip;
        span.innerHTML = reoptParameter.tooltip;
        label.append(span);
        modal.divElement.append(label);
        const input = getInput.bind(this)(this.#id);
        this.#input = input;
        this.#input.id = reoptParameter.alias;
        this.#input.name = reoptParameter.alias;
        input.required = true;
        modal.divElement.append(input);
        if (input.type === 'checkbox' && !input.checked) {
            // - Must append a hidden input for unchecked checkboxes
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = reoptParameter.alias;
            hiddenInput.value = 'false';
            modal.divElement.prepend(hiddenInput);
        }
        if (this.modal === null) {
            this.modal = modal;
        }
        if (document.body.contains(this.modal.divElement)) {
            this.modal.divElement.replaceWith(modal.divElement);
            this.modal = modal;
        }
    }
}

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
        microgridDropdownInstructions.textContent = 'Select microgrid to override parameters for:';
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
    controller;     // - A REoptParametersController instance
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
        this.controller = controller;
        this.controller.model.getReoptParametersInstance(this.#observableId).registerObserver(this);
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
        // - Don't refresh the content because then other inputs that are showing an error statement will have their erroneous values cleared! */
        this.refreshContent();
    }

    /**
     * @returns {undefined}
     */
    renderContent() {
        const modal = new Modal();
        modal.divElement.id = 'parameterTableModal'
        modal.insertTBodyRow([this.#getPlusButton(), 'Parameter', 'Value'], 'append');
        for (const parameter of this.controller.model.getReoptParametersInstance(this.#observableId).reoptParameters) {
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
     * - Handles property deletions and property updates
     * @returns {undefined}
     */
    refreshContent() {
        for (const span of [...this.modal.divElement.querySelectorAll('span[data-reopt-parameter-parameter-name]')]) {
            const parameterName = span.dataset.reoptParameterParameterName;
            const reoptParameter = this.controller.model.getReoptParametersInstance(this.#observableId).getReoptParameter(parameterName);
            let parentElement = span.parentElement;
            while (!(parentElement instanceof HTMLTableRowElement)) {
                parentElement = parentElement.parentElement;
            }
            if(!reoptParameter.isSet()) {
                parentElement.remove();
            } else {
                const inputOrSelect = parentElement.children[2].children[0].children[0];
                if (inputOrSelect instanceof HTMLInputElement) {
                    // - During a refresh, don't remove erroneous values from any inputs
                    //inputOrSelect.value = reoptParameter.value;
                } else {
                    for (const op of inputOrSelect.options) {
                        let value = op.value;
                        if (op.value === 'true') {
                            value = true;
                        } else if (op.value === 'false') {
                            value = false;
                        }
                        if (value === reoptParameter.value) {
                            op.selected = true;
                        }
                    }
                }
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
        for (const parameter of this.controller.model.getReoptParametersInstance(this.#observableId).reoptParameters) {
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
                that.controller.unsetParameter(id);
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
        const reoptParameter = this.controller.model.getReoptParametersInstance(microgridName).getReoptParameter(`${parameterNamespace}:${name}`);
        const span = document.createElement('span');
        span.textContent = reoptParameter.displayName;
        span.dataset.reoptParameterParameterName = reoptParameter.parameterName;
        const errorDiv = document.createElement('div');
        const input = getInput.bind(this)(id, errorDiv);
        modal.insertTBodyRow([this.#getUnsetParameterButton(id), span, input, errorDiv], 'append');
    }
}

/**
 * - This function must be used in such a way that "this" is bound to REoptParametersTable view or a REoptInputView view
 * - The controller is used to mutate the model for two different reasons. For the REopt parameter override widget, modifying the model actually
 *   changes what values are sent to the server for microgrid overrides. For REoptInputView widgets, modifying the model is done simply to perform
 *   validation. In this case, the "name" and "value" properties of each input/select still matter because I submit that information through FormData
 * @param {string} id - a string of the form "<microgrid name>:<REopt parameter namespace>:<REopt parameter name>"
 * @param {HTMLElement} errorElement - the element to display an error message in
 * @returns {HTMLInputElement | HTMLSelectElement}
 */
function getInput(id, errorElement=null) {
    if (id.split(':').length !== 3) {
        throw Error(`The "id" argument "${id}" must contain exactly two ":" characters.`);
    }
    const [microgridName, parameterNamespace, name] = id.split(':');
    const reoptParameter = this.controller.model.getReoptParametersInstance(microgridName).getReoptParameter(`${parameterNamespace}:${name}`);
    const that = this;
    let oldValue = reoptParameter.value;
    if (reoptParameter instanceof REoptBooleanParameter) {
        // - We use checkboxes instead of yes/no selects for selecting microgrid technologies
        if (name === 'mgu_enabled') {
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.value = 'true';
            if (oldValue === true) {
                input.checked = true;
            } else if (oldValue === null) {
                input.indeterminate = true;
            }
            // - Must append a hidden input for unchecked checkboxes
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = reoptParameter.alias;
            hiddenInput.value = 'false';
            input.addEventListener('change', function() {
                if (this.checked) {
                    that.controller.setParameterValue(id, true);
                    // - Remove this hiddenInput and a potential initial hidden input
                    [...that.modal.divElement.querySelectorAll(`input[type="hidden"][name="${reoptParameter.alias}"]`)].forEach(input => input.remove());
                } else {
                    that.controller.setParameterValue(id, false);
                    that.modal.divElement.prepend(hiddenInput);
                    // - What about an overridden parameter that is overridden, then unchecked, then deleted? Doesn't matter. There is no form
                    //   submission for the parameter override widget
                }
            });
            return input;
        }
        const select = document.createElement('select');
        // - When the user decides to override a boolean parameter, they haven't actually set the parameter in the model until they've select "yes" or
        //   "no" in the selection input. It's not clear that this is what's happening unless the select has a third initial starting value
        if (oldValue === null) {
            const selectionOption = document.createElement('option');
            selectionOption.label = '<Select value>';
            selectionOption.value = ''
            select.add(selectionOption);
            selectionOption.selected = true;
        }
        const yesOption = document.createElement('option');
        yesOption.label = 'Yes';
        yesOption.value = 'true';
        select.add(yesOption);
        const noOption = document.createElement('option');
        noOption.label = 'No';
        noOption.value = 'false';
        select.add(noOption);
        if (oldValue === true) {
            yesOption.selected = true;
        } else if (oldValue === false) {
            noOption.selected = true;
        }
        select.addEventListener('change', function() {
            let value = this[this.selectedIndex].value;
            if (value === 'true' || value === 'false') {
                // - Remove the initial starting option if it exists
                const options = [...select.options];
                if (options.length > 2) {
                    select.remove(options.filter(op => op.value === '')[0].index);
                }
                if (value === 'true') {
                    that.controller.setParameterValue(id, true);
                } else {
                    that.controller.setParameterValue(id, false);
                }
            }
        });
        return select;
    // - MACRS inputs get special treatment for some reason
    } else if (name === 'macrs_option_years') {
        const select = document.createElement('select');
        let ary;
        if (['PV', 'ElectricStorage', 'Wind'].includes(parameterNamespace)) {
            ary = [0, 5, 7];
        } else {
            ary = [0, 15, 20];
        }
        if (oldValue === null) {
            const selectionOption = document.createElement('option');
            selectionOption.label = '<Select value>';
            selectionOption.value = ''
            select.add(selectionOption);
            selectionOption.selected = true;
        }
        for (const num of ary) {
            const option = document.createElement('option');
            option.label = num;
            option.value = num;
            if (oldValue === num) {
                option.selected = true;
            }
            select.add(option);
        }
        select.addEventListener('change', function() {
            const value = this[this.selectedIndex].value;
            if (['0', '5', '7', '15', '20'].includes(value)) {
                // - Remove the initial starting option if it exists
                const options = [...select.options];
                if (options.length > 3) {
                    select.remove(options.filter(op => op.value === '')[0].index);
                }
                that.controller.setParameterValue(id, +value);
            }
        });
        return select;
    } else {
        const input = document.createElement('input');
        input.value = oldValue;
        input.addEventListener('change', function() {
            try {
                let value = this.value.trim();
                if (reoptParameter instanceof REoptIntParameter || reoptParameter instanceof REoptFloatParameter) {
                    if (isNaN(parseFloat(value)) || isNaN(Number(value))) {
                        throw Error(`"${reoptParameter.displayName}" must be a number.`);
                    } else {
                        value = +value;
                    }
                }
                that.controller.setParameterValue(id, value);
                oldValue = reoptParameter.value;
                if (errorElement === null) {
                    that.modal.setBanner('', ['hidden']);
                } else {
                    errorElement.textContent = '';
                    errorElement.classList.remove('caution');
                }
            } catch (e) {
                // - Keep the bad value in the input
                //this.value = oldValue;
                // - Make the error message shorter
                const message = e.message.replace(/"[^"]*"/, 'Value') + ' Please change the value.';
                if (errorElement === null) {
                    that.modal.setBanner(message, ['caution']);
                } else {
                    errorElement.textContent = message;
                    errorElement.classList.add('caution');
                }
            }
        });
        return input;
    }
}