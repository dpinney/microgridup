export { MicrogridParameterModel, MicrogridParameterController, MicrogridParameterView };
import { Modal, getTrashCanSvg, getCirclePlusSvg } from '../modal.js';

class MicrogridParameter {

    #displayName;
    #max;
    #min;
    #parameterName;
    #type;
    #value;

    constructor(displayName, max, min, parameterName, type) {
        if (typeof displayName !== 'string') {
            throw TypeError('The "displayName" argument must be typeof "string".');
        }
        if (typeof max !== 'number') {
            throw TypeError('The "max" argument must be typeof "number".');
        }
        if (typeof min !== 'number') {
            throw TypeError('The "min" argument must be typeof "number".');
        }
        if (typeof parameterName !== 'string') {
            throw TypeError('The "parameterName" argument must be typeof "string".');
        }
        if (typeof type !== 'string') {
            throw TypeError('The "type" argument must be typeof "string".');
        }
        this.#displayName = displayName;
        this.#max = max;
        this.#min = min;
        this.#parameterName = parameterName;
        this.#type = type;
        this.#value = null;
    }

    get displayName() {
        return this.#displayName;
    }

    set displayName(val) {
        this.#displayName = val;
    }

    get parameterName() {
        return this.#parameterName;
    }

    set parameterName(val) {
        this.#parameterName = val;
    }

    get value() {
        return this.#value;
    }

    set value(val) {
        const numVal = +val;
        if (isNaN(numVal) || val === null || isNaN(parseFloat(val))) {
            throw Error('The "val" argument must be parsable into a number.');
        }
        if (numVal > this.#max) {
            throw Error(`The "val" argument must be less than or equal to ${this.#max}.`);
        }
        if (numVal < this.#min) {
            throw Error(`The "val" argument must be greater than or equal to ${this.#min}.`);
        }
        this.#value = numVal;
    }
}

class Microgrid {

    #observers;
    #properties;

    constructor() {
        this.#observers = [];
        this.#properties = {};
    }

    deleteProperty(propertyKey) {
        if (this.#properties.hasOwnProperty(propertyKey)) {
            const oldPropertyValue = this.getProperty(propertyKey);
            delete this.#properties[propertyKey];
            this.updatePropertyOfObservers(propertyKey, oldPropertyValue);
        } else {
            throw ReferenceError(`The Microgrid does not have the property "${propertyKey}".`);
        }
    }

    hasProperty(propertyKey) {
        return this.#properties.hasOwnProperty(propertyKey);
    }
    
    getProperties() {
        return this.#properties;
    }

    getProperty(propertyKey) {
        if (this.#properties.hasOwnProperty(propertyKey)) {
            return this.#properties[propertyKey];
        } else {
            throw ReferenceError(`The Microgrid does not have the property "${propertyKey}".`);
        }
    }

    registerObserver(observer) {
        this.#observers.push(observer);
    }

    removeObserver(observer) {
        const index = this.#observers.indexOf(observer);
        if (index > -1) {
            this.#observers.splice(index, 1);
        }
    }

    setProperty(propertyKey, propertyValue) {
        if (typeof propertyKey !== 'string') {
            throw TypeError('The "propertyKey" argument must be typeof "string".');
        }
        if (!(propertyValue instanceof MicrogridParameter)) {
            throw TypeError('The "propertyValue" argument must be instanceof MicrogridParameter.');
        }
        this.#properties[propertyKey] = propertyValue;
    }

    updatePropertyOfObservers(propertyKey, oldPropertyValue) {
        this.#observers.forEach(ob => ob.handleUpdatedProperty(this, propertyKey, oldPropertyValue));
    }
}

class MicrogridParameterModel {
    
    static microgridParameters = {
        'solar': {
            'solarMax': () => new MicrogridParameter('Solar Power Max (kW-DC)', 1.0e9, 0, 'solarMax', 'float'),
            'solarMin': () => new MicrogridParameter('Solar Power Min (kW-DC)', 1.0e9, 0, 'solarMin', 'float')
        },
        'battery': {
            // - Technically, there's no max for batteryCapacityMax or batteryCapacityMin
            'batteryCapacityMax': () => new MicrogridParameter('Battery Capacity Max (kWh-AC)', 1.0e6, 0, 'batteryCapacityMax', 'float'),
            'batteryCapacityMin': () => new MicrogridParameter('Battery Capacity Min (kWh-AC)', 1.0e6, 0, 'batteryCapacityMin', 'float'),
            'batteryPowerMax': () => new MicrogridParameter('Battery Power Max (kW-AC)', 1.0e9, 0, 'batteryPowerMax', 'float'),
            'batteryPowerMin': () => new MicrogridParameter('Battery Power Min (kW-AC)', 1.0e9, 0, 'batteryPowerMin', 'float')
        },
        'fossil': {
            'dieselMax': () => new MicrogridParameter('Genset Max (kW)', 1.0e9, 0, 'dieselMax', 'float'),
            'dieselMin': () => new MicrogridParameter('Genset Min (kW)', 1.0e9, 0, 'dieselMin', 'float'),
            'fuelAvailable': () => new MicrogridParameter('Fuel Available (Gal)', 1.0e9, 0, 'fuelAvailable', 'float')
        },
        'wind': {
            'windMax': () => new MicrogridParameter('Wind Power Max (kW)', 1.0e9, 0, 'windMax', 'float'),
            'windMin': () => new MicrogridParameter('Wind Power Min (kW)', 1.0e9, 0, 'windMin', 'float')
        }
    }
    #microgrids;
    
    constructor(microgridNames) {
        if (new Set(microgridNames).size !== microgridNames.length) {
            throw Error('The "microgridNames" argument must contain unique values.');
        }
        this.#microgrids = {};
        microgridNames.forEach(name => {
            this.#microgrids[name] = new Microgrid();
        });
    }
    
    getExportData() {
        const data = {};
        for (const [name, mg] of Object.entries(this.#microgrids)) {
            data[name] = {};
            for (const [key, param] of Object.entries(mg.getProperties())) {
                data[name][key] = param.value;
            }
        }
        return data;
    }

    getMicrogrid(name) {
        if (this.#microgrids.hasOwnProperty(name)) {
            return this.#microgrids[name];
        } else {
            throw ReferenceError(`The microgrid ${name} does not exist.`);
        }
    }

    getMicrogrids() {
        return this.#microgrids;
    }
}

class MicrogridParameterController {

    model; // - A MicrogridParameterModel instance

    constructor(model) {
        if (!(model instanceof MicrogridParameterModel)) {
            throw TypeError('The "model" argument must be instance of MicrogridParameterModel.');
        }
        this.model = model;
    }

    deleteProperty(observables, propertyKey) {
        if (!(observables instanceof Array)) {
            throw TypeError('The "observables" argument must be instanceof Array.');
        }
        if (typeof propertyKey !== 'string') {
            throw TypeError('The "propertyKey" argument must be typeof "string".');
        }
        observables.forEach(ob => {
            if (ob.hasProperty(propertyKey)) {
                ob.deleteProperty(propertyKey);
            }
        });
    }
    
    setProperty(observables, propertyKey, propertyValue) {
        if (!(observables instanceof Array)) {
            throw TypeError('The "observables" argument must be instanceof Array.');
        }
        if (typeof propertyKey !== 'string') {
            throw TypeError('The "propertyKey" argument must be typeof "string".');
        }
        if (!(propertyValue instanceof MicrogridParameter)) {
            throw TypeError('The "propertyValue" argument must be instanceof MicrogridParameter.');
        }
        observables.forEach(ob => {
            ob.setProperty(propertyKey, propertyValue); 
        });
    }
}

class MicrogridParameterView {

    modal;          // - A Modal instance
    #controller;    // - A MicrogridParameterController instance

    constructor(controller) {
        if (!(controller instanceof MicrogridParameterController)) {
            throw TypeError('The "controller" argument must be instanceof MicrogridParameterController.');
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
        const microgridDropdownInstructions = document.createElement('p');
        microgridDropdownInstructions.style.fontWeight = 'bold';
        microgridDropdownInstructions.textContent = 'Select microgrid to override parameters for';
        modal.divElement.append(microgridDropdownInstructions);
        const microgridSelect = document.createElement('select');
        microgridSelect.classList.add('rounded-md', 'py-1');
        microgridSelect.classList.add('mt-5');
        const option = document.createElement('option');
        option.label = '<Select Microgrid>';
        option.value = '<Select Microgrid>';
        microgridSelect.add(option);
        for (const name of Object.keys(this.#controller.model.getMicrogrids())) {
            const option = document.createElement('option');
            option.label = name;
            option.value = name;
            microgridSelect.add(option);
        }
        modal.divElement.append(microgridSelect);
        const tableDiv = document.createElement('div');
        tableDiv.classList.add('pt-5');
        modal.divElement.append(tableDiv);
        const that = this;
        microgridSelect.addEventListener('change', function() {
            const name = this[this.selectedIndex].value;
            if (name !== '<Select Microgrid>') {
                const tableInstructions = document.createElement('p');
                tableInstructions.style.fontWeight = 'bold';
                tableInstructions.textContent = `Set parameters for microgrid "${name}":`;
                const table = new MicrogridParameterTable(that.#controller.model.getMicrogrid(name), that.#controller);
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

class MicrogridParameterTable {
    
    modal;          // - A Modal instance
    #controller;    // - A MicrogridParameterController instance
    #observable;    // - A Microgrid instance
    #parameterSelect;

    constructor(observable, controller) {
        if (!(observable instanceof Microgrid)) {
            throw TypeError('The "observable" argument must be instanceof Microgrid.');
        }
        if (!(controller instanceof MicrogridParameterController)) {
            throw TypeError('The "controller" argument must be instanceof MicrogridParameterController.');
        }
        this.modal = null;
        this.#controller = controller;
        this.#observable = observable;
        this.#observable.registerObserver(this);
        this.#parameterSelect = null;
        this.renderContent();
    }

    handleUpdatedProperty(observable, propertyKey, oldPropertyValue) {
        this.renderContent();
    }

    renderContent() {
        const modal = new Modal();
        modal.divElement.id = 'parameterTableModal'
        modal.divElement.classList.add('bg-slate-100', 'py-5', 'rounded-md', 'border-2', 'border-solid');
        modal.insertTBodyRow([this.#getPlusButton(), 'Parameter', 'Value'], 'append');
        const that = this;
        for (const [key, param] of Object.entries(this.#observable.getProperties())) {
            that.#insertPropertyRow(modal, key, param);
        }
        if (this.modal === null) {
            this.modal = modal;
        } 
        if (document.body.contains(this.modal.divElement)) {
            this.modal.divElement.replaceWith(modal.divElement);
            this.modal = modal;
        }
    }
    
    #getPlusButton() {
        const button = document.createElement('button');
        button.classList.add('bg-green-700', 'hover:bg-green-600');
        button.append(getCirclePlusSvg());
        button.addEventListener('click', (e) => {
            if (!document.body.contains(this.#parameterSelect)) {
                this.modal.insertTBodyRow([this.#getDeletePropertyButton(''), this.#getParameterSelect()], 'append');
            }
            e.preventDefault();
        });
        return button;
    }

    /**
     * @param {string} propertyKey
     * @returns {HTMLButtonElement} a button that can be clicked on to remove a property from a microgrid
     */
    #getDeletePropertyButton(propertyKey) {
        if (typeof propertyKey !== 'string') {
            throw TypeError('The "propertyKey" argument must be typeof "string".');
        }
        const button = document.createElement('button');
        button.classList.add('delete');
        button.appendChild(getTrashCanSvg());
        const that = this;
        button.addEventListener('click', function(e) {
            that.#controller.deleteProperty([that.#observable], propertyKey);
            // - Delete button for property select also needs to remove its table row
            that.renderContent();
            //let parentElement = this.parentElement;
            //while (!(parentElement instanceof HTMLTableRowElement)) {
            //    parentElement = parentElement.parentElement;
            //}
            //parentElement.remove();
            e.stopPropagation();
        });
        return button;
    }

    #getParameterSelect() {
        const select = document.createElement('select');
        select.classList.add('rounded-md', 'py-1');
        const option = document.createElement('option');
        option.label = '<Select Parameter>';
        option.value = '<Select Parameter>';
        select.add(option);
        for (const id of ['solar', 'battery', 'fossil', 'wind']) {
            for (const [key, param] of Object.entries(MicrogridParameterModel.microgridParameters[id])) {
                const existingRows = [...document.querySelectorAll('span[data-microgrid-property-parameter-name]')].map(span => span.dataset.microgridPropertyParameterName);
                if (!existingRows.includes(key)) {
                    const option = document.createElement('option');
                    option.label = param().displayName;
                    option.value = `${id}:${key}`;
                    select.add(option); 
                }
            }
        }
        const that = this;
        select.addEventListener('change', function() {
            const [id, key] = this[this.selectedIndex].value.split(':');
            const param = MicrogridParameterModel.microgridParameters[id][key]();
            that.#insertPropertyRow(that.modal, key, param);
            let parentElement = this.parentElement;
            while (!(parentElement instanceof HTMLTableRowElement)) {
                parentElement = parentElement.parentElement;
            }
            parentElement.remove();
        });
        this.#parameterSelect = select;
        return select;
    }

    #insertPropertyRow(modal, paramKey, microgridParameter) {
        const input = document.createElement('input');
        input.classList.add('border-2', 'border-black', 'rounded-md');
        let oldVal = microgridParameter.value;
        input.value = oldVal;
        const that = this;
        input.addEventListener('change', function() {
            try {
                microgridParameter.value = this.value.trim();
                that.#controller.setProperty([that.#observable], paramKey, microgridParameter);
                oldVal = microgridParameter.value;
                that.modal.setBanner('', ['hidden']);
            } catch (e) {
                this.value = oldVal;
                that.modal.setBanner(e.message, ['caution']);
            }
        });
        const span = document.createElement('span');
        span.textContent = microgridParameter.displayName;
        span.dataset.microgridPropertyParameterName = microgridParameter.parameterName;
        modal.insertTBodyRow([this.#getDeletePropertyButton(paramKey), span, input], 'append');
    }
}